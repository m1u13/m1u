# main.py

from fastapi import FastAPI, HTTPException, Body, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from typing import List
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright, Browser

# local imports
import scraper
import cookie_manager

# --- 変更点: Lifespan Managerの追加 ---
# アプリケーションの起動時と終了時の処理を定義します。
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 起動時の処理
    print("Starting up... Launching browser.")
    p = await async_playwright().start()
    # 常に単一のブラウザインスタンスを保持します。
    browser = await p.firefox.launch(headless=True)
    # app.stateに保存することで、どのエンドポイントからでもアクセスできるようにします。
    app.state.browser = browser
    app.state.playwright = p
    
    yield # ここでアプリケーションが実行されます
    
    # 終了時の処理
    print("Shutting down... Closing browser.")
    await app.state.browser.close()
    await app.state.playwright.stop()


app = FastAPI(
    title="Playwright Scraping Server",
    description="動的ウェブページをスクレイピングし、Cookieを管理するAPIサーバーです。",
    lifespan=lifespan # 変更点: lifespanを登録
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
# --- 変更点: Requestオブジェクトを受け取る ---
async def scrape_url(url: str, request: Request):
	"""
	指定されたURLにアクセスし、5秒後のHTMLコンテンツを返します。
	アクセス中に取得・更新されたCookieはサーバーに保存されます。
	"""
	if not url.startswith(("http://", "https://")):
		raise HTTPException(status_code=400, detail="無効なURL形式です。http:// または https:// で始まる必要があります。")
	try:
        # --- 変更点: app.stateからブラウザインスタンスを取得して利用 ---
		browser: Browser = request.app.state.browser
		html_content = await scraper.get_page_html(browser, url)
		return HTMLResponse(content=html_content)
	except Exception as e:
		print(f"An error occurred during scraping: {e}")
		raise HTTPException(status_code=500, detail=f"内部エラーが発生しました: {str(e)}")

# --- Cookie管理エンドポイント (変更なし) ---

@app.get("/cookies", response_model=List[CookieModel], summary="全Cookieを取得")
async def get_all_cookies():
	"""サーバーに保存されているすべてのCookieを取得します。"""
	return cookie_manager.load_cookies()

@app.post("/cookies", summary="Cookieを追加・更新")
async def add_or_update_user_cookies(cookies: List[CookieModel] = Body(...)):
	"""
	新しいCookieを追加するか、既存のCookieを名前で上書きします。
	CookieのリストをリクエストボディとしてJSON形式で送信してください。
	"""
	try:
		cookies_dict_list = [cookie.dict() for cookie in cookies]
		cookie_manager.add_or_update_cookies(cookies_dict_list)
		return JSONResponse(content={"status": "success", "message": "Cookieが更新されました。"})
	except Exception as e:
		print(f"Error updating cookies: {e}")
		raise HTTPException(status_code=500, detail="Cookieの更新に失敗しました。")

@app.delete("/cookies", summary="Cookieを削除")
async def delete_user_cookies(names: List[str] = Query(..., description="削除したいCookieの名前のリスト。例: /cookies?names=session_id&names=user_token")):
	"""
	指定された名前を持つCookieを削除します。
	"""
	if not names:
		raise HTTPException(status_code=400, detail="削除するCookieの名前が指定されていません。")
	try:
		cookie_manager.delete_cookies_by_name(names)
		return JSONResponse(content={"status": "success", "message": f"Cookie {names} が削除されました。"})
	except Exception as e:
		print(f"Error deleting cookies: {e}")
		raise HTTPException(status_code=500, detail="Cookieの削除に失敗しました。")
