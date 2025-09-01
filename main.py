from fastapi import FastAPI, HTTPException, Body, Query
from fastapi.responses import HTMLResponse, JSONResponse
from typing import List, Optional
from pydantic import BaseModel, Field
import asyncio

# local imports
import scraper
import cookie_manager

app = FastAPI(
    title="High Performance Playwright Scraping Server",
    description="高性能な動的ウェブページスクレイピングサーバー。ブラウザインスタンスを再利用してパフォーマンスを最適化。"
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

# アプリケーション終了時のクリーンアップ
@app.on_event("shutdown")
async def shutdown_event():
    """アプリケーション終了時にブラウザリソースをクリーンアップ"""
    await scraper._browser_pool.cleanup()

@app.get("/", response_class=HTMLResponse, summary="サーバー状態確認")
async def read_root():
    """サーバーが正常に動作しているか確認します。"""
    return "<h1>High Performance Scraping Server is running 🚀</h1>"

@app.get("/scrape", response_class=HTMLResponse, summary="URLをスクレイピング（標準速度）")
async def scrape_url(
    url: str, 
    wait: Optional[float] = Query(2.0, ge=0.5, le=10.0, description="待機時間（秒）")
):
    """
    指定されたURLにアクセスし、指定秒数後のHTMLコンテンツを返します。
    ブラウザインスタンスを再利用してパフォーマンスを向上。
    """
    if not url.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=400, 
            detail="無効なURL形式です。http:// または https:// で始まる必要があります。"
        )
    
    try:
        html_content = await scraper.get_html_after_wait(url, wait)
        return HTMLResponse(content=html_content)
    except Exception as e:
        print(f"スクレイピング中にエラーが発生しました: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"内部エラーが発生しました: {str(e)}"
        )

@app.get("/scrape/quick", response_class=HTMLResponse, summary="高速スクレイピング")
async def quick_scrape_url(url: str):
    """
    指定されたURLに高速アクセスし、1秒後のHTMLコンテンツを返します。
    軽量な処理でより高速なレスポンスを提供。
    """
    if not url.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=400, 
            detail="無効なURL形式です。http:// または https:// で始まる必要があります。"
        )
    
    try:
        html_content = await scraper.quick_scrape(url)
        return HTMLResponse(content=html_content)
    except Exception as e:
        print(f"高速スクレイピング中にエラーが発生しました: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"内部エラーが発生しました: {str(e)}"
        )

# 複数URL同時スクレイピング
@app.post("/scrape/batch", summary="バッチスクレイピング")
async def batch_scrape(
    urls: List[str] = Body(..., description="スクレイピング対象URLのリスト"),
    wait: Optional[float] = Body(2.0, ge=0.5, le=10.0, description="待機時間（秒）")
):
    """
    複数のURLを並列でスクレイピングします。
    """
    # URL形式チェック
    for url in urls:
        if not url.startswith(("http://", "https://")):
            raise HTTPException(
                status_code=400,
                detail=f"無効なURL形式です: {url}"
            )
    
    if len(urls) > 10:
        raise HTTPException(
            status_code=400,
            detail="一度に処理できるURLは10個までです。"
        )
    
    try:
        # 並列実行
        tasks = [scraper.get_html_after_wait(url, wait) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 結果をフォーマット
        response_data = []
        for i, (url, result) in enumerate(zip(urls, results)):
            if isinstance(result, Exception):
                response_data.append({
                    "url": url,
                    "success": False,
                    "error": str(result),
                    "html": None
                })
            else:
                response_data.append({
                    "url": url,
                    "success": True,
                    "error": None,
                    "html": result
                })
        
        return JSONResponse(content={"results": response_data})
        
    except Exception as e:
        print(f"バッチスクレイピング中にエラーが発生しました: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"内部エラーが発生しました: {str(e)}"
        )

# --- Cookie管理エンドポイント ---

@app.get("/cookies", response_model=List[CookieModel], summary="全Cookieを取得")
async def get_all_cookies():
    """サーバーに保存されているすべてのCookieを取得します。"""
    return cookie_manager.load_cookies()

@app.post("/cookies", summary="Cookieを追加・更新")
async def add_or_update_user_cookies(cookies: List[CookieModel] = Body(...)):
    """
    新しいCookieを追加するか、既存のCookieを名前で上書きします。
    """
    try:
        cookies_dict_list = [cookie.dict() for cookie in cookies]
        cookie_manager.add_or_update_cookies(cookies_dict_list)
        return JSONResponse(
            content={"status": "success", "message": "Cookieが更新されました。"}
        )
    except Exception as e:
        print(f"Cookie更新エラー: {e}")
        raise HTTPException(status_code=500, detail="Cookieの更新に失敗しました。")

@app.delete("/cookies", summary="Cookieを削除")
async def delete_user_cookies(
    names: List[str] = Query(..., description="削除したいCookieの名前のリスト")
):
    """指定された名前を持つCookieを削除します。"""
    if not names:
        raise HTTPException(
            status_code=400, 
            detail="削除するCookieの名前が指定されていません。"
        )
    
    try:
        cookie_manager.delete_cookies_by_name(names)
        return JSONResponse(
            content={"status": "success", "message": f"Cookie {names} が削除されました。"}
        )
    except Exception as e:
        print(f"Cookie削除エラー: {e}")
        raise HTTPException(status_code=500, detail="Cookieの削除に失敗しました。")

# ヘルスチェックエンドポイント
@app.get("/health", summary="ヘルスチェック")
async def health_check():
    """サーバーとブラウザプールの状態を確認します。"""
    try:
        browser_active = scraper._browser_pool.browser is not None
        return JSONResponse(content={
            "status": "healthy",
            "browser_pool_active": browser_active,
            "timestamp": asyncio.get_event_loop().time()
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "unhealthy", "error": str(e)}
        )
