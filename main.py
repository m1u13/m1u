from fastapi import FastAPI, HTTPException, Body, Query
from fastapi.responses import HTMLResponse, JSONResponse
from typing import List
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright, Browser, Page, Playwright

# local imports
import scraper
import cookie_manager

# --- グローバル変数としてブラウザインスタンスを保持 ---
# アプリケーションの状態を管理するための辞書
# サーバー起動時にPlaywrightのオブジェクトが格納されます
app_state = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- サーバー起動時の処理 ---
    print("サーバーを起動します...")
    p = await async_playwright().start()
    browser = await p.firefox.launch(headless=True)
    context = await browser.new_context()
    
    # 永続化されているCookieを読み込んで設定
    saved_cookies = cookie_manager.load_cookies()
    if saved_cookies:
        await context.add_cookies(saved_cookies)
        print(f"{len(saved_cookies)}個のCookieを読み込みました。")
    
    page = await context.new_page()
    
    # 他のエンドポイントから参照できるように状態を保存
    app_state["playwright"] = p
    app_state["browser"] = browser
    app_state["context"] = context
    app_state["page"] = page
    
    yield  # ここでアプリケーションがリクエストを処理します
    
    # --- サーバー終了時の処理 ---
    print("サーバーをシャットダウンします...")
    # 最終的なCookieを保存
    final_cookies = await app_state["context"].cookies()
    cookie_manager.add_or_update_cookies(final_cookies)
    print("最新のCookieをファイルに保存しました。")
    
    await app_state["browser"].close()
    await app_state["playwright"].stop()


app = FastAPI(
    title="Playwright Scraping Server",
    description="動的ウェブページをスクレイピングし、Cookieを管理するAPIサーバーです。",
    lifespan=lifespan  # ライフサイクルイベントを登録
)

class CookieModel(BaseModel):
    name: str
    value: str
    domain: str
    path: str
    expires: float
    httpOnly: bool
    secure: bool
    sameSite: str = Field(..., pattern="^(Strict|Lax|None)$")


@app.get("/", response_class=HTMLResponse, summary="サーバー状態確認")
async def read_root():
    """サーバーが正常に動作しているか確認します。"""
    return "<h1>Scraping Server is running 🚀</h1>"

@app.get("/scrape", response_class=HTMLResponse, summary="URLをスクレイピング")
async def scrape_url(url: str):
    """
    指定されたURLにアクセスし、5秒後のHTMLコンテンツを返します。
    アクセス中に取得・更新されたCookieはサーバーに保存されます。
    """
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="無効なURL形式です。http:// または https:// で始まる必要があります。")
    
    # 起動時に作成されたpageオブジェクトを再利用
    page = app_state.get("page")
    if not page:
        raise HTTPException(status_code=503, detail="ブラウザの準備ができていません。")

    try:
        html_content = await scraper.get_html_after_5s(page, url)
        
        # スクレイピング後の最新のCookieを取得してファイルに保存
        current_cookies = await app_state["context"].cookies()
        cookie_manager.add_or_update_cookies(current_cookies)
        
        return HTMLResponse(content=html_content)
    except Exception as e:
        print(f"An error occurred during scraping: {e}")
        raise HTTPException(status_code=500, detail=f"内部エラーが発生しました: {str(e)}")

# --- Cookie管理エンドポイント ---

@app.get("/cookies", response_model=List[CookieModel], summary="全Cookieを取得")
async def get_all_cookies():
    """サーバーに保存されているすべてのCookieを取得します。"""
    # ファイルからではなく、メモリ上の最新のコンテキストから取得
    context = app_state.get("context")
    if context:
        return await context.cookies()
    return []

@app.post("/cookies", summary="Cookieを追加・更新")
async def add_or_update_user_cookies(cookies: List[CookieModel] = Body(...)):
    """
    新しいCookieを追加するか、既存のCookieを名前で上書きします。
    CookieのリストをリクエストボディとしてJSON形式で送信してください。
    """
    context = app_state.get("context")
    if not context:
        raise HTTPException(status_code=503, detail="ブラウザコンテキストが利用できません。")
        
    try:
        # Pydanticモデルを辞書のリストに変換
        cookies_dict_list = [cookie.dict() for cookie in cookies]
        
        # まずファイルに保存
        cookie_manager.add_or_update_cookies(cookies_dict_list)
        
        # メモリ上のコンテキストも更新
        # 一旦クリアしてから全て追加し直すのが確実
        all_cookies = cookie_manager.load_cookies()
        await context.clear_cookies()
        if all_cookies:
            await context.add_cookies(all_cookies)
            
        return JSONResponse(content={"status": "success", "message": "Cookieが更新されました。"})
    except Exception as e:
        print(f"Error updating cookies: {e}")
        raise HTTPException(status_code=500, detail="Cookieの更新に失敗しました。")


@app.delete("/cookies", summary="Cookieを削除")
async def delete_user_cookies(names: List[str] = Query(..., description="削除したいCookieの名前のリスト。例: /cookies?names=session_id&names=user_token")):
    """
    指定された名前を持つCookieを削除します。
    """
    context = app_state.get("context")
    if not context:
        raise HTTPException(status_code=503, detail="ブラウザコンテキストが利用できません。")
    if not names:
        raise HTTPException(status_code=400, detail="削除するCookieの名前が指定されていません。")
        
    try:
        # まずファイルから削除
        cookie_manager.delete_cookies_by_name(names)
        
        # メモリ上のコンテキストも更新
        all_cookies = cookie_manager.load_cookies()
        await context.clear_cookies()
        if all_cookies:
            await context.add_cookies(all_cookies)

        return JSONResponse(content={"status": "success", "message": f"Cookie {names} が削除されました。"})
    except Exception as e:
        print(f"Error deleting cookies: {e}")
        raise HTTPException(status_code=500, detail="Cookieの削除に失敗しました。")
