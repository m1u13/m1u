from fastapi import FastAPI, HTTPException, Body, Query
from fastapi.responses import HTMLResponse, JSONResponse
from typing import List, Optional
from pydantic import BaseModel, Field
import asyncio
import logging

# local imports
import scraper
import cookie_manager

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="High Performance Playwright Scraping Server",
    description="高性能な動的ウェブページスクレイピングサーバー。ブラウザインスタンスを再利用してパフォーマンスを最適化。",
    version="2.0.0"
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
    logger.info("アプリケーション終了処理開始")
    await scraper._browser_pool.cleanup()
    logger.info("アプリケーション終了処理完了")

@app.get("/", response_class=HTMLResponse, summary="サーバー状態確認")
async def read_root():
    """サーバーが正常に動作しているか確認します。"""
    return """
    <html>
        <head><title>Scraping Server</title></head>
        <body>
            <h1>High Performance Scraping Server is running 🚀</h1>
            <h2>Available Endpoints:</h2>
            <ul>
                <li><a href="/docs">API Documentation</a></li>
                <li><a href="/health">Health Check</a></li>
                <li><a href="/debug">Debug Info</a></li>
            </ul>
        </body>
    </html>
    """

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
        logger.info(f"スクレイピングリクエスト: {url}, 待機時間: {wait}秒")
        html_content = await scraper.get_html_after_wait(url, wait)
        logger.info("スクレイピング正常完了")
        return HTMLResponse(content=html_content)
    except Exception as e:
        error_msg = f"スクレイピング中にエラーが発生しました: {e}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

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
        logger.info(f"高速スクレイピングリクエスト: {url}")
        html_content = await scraper.quick_scrape(url)
        logger.info("高速スクレイピング正常完了")
        return HTMLResponse(content=html_content)
    except Exception as e:
        error_msg = f"高速スクレイピング中にエラーが発生しました: {e}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

# --- Cookie管理エンドポイント ---

@app.get("/cookies", response_model=List[CookieModel], summary="全Cookieを取得")
async def get_all_cookies():
    """サーバーに保存されているすべてのCookieを取得します。"""
    return cookie_manager.load_cookies()

@app.post("/cookies", summary="Cookieを追加・更新")
async def add_or_update_user_cookies(cookies: List[CookieModel] = Body(...)):
    """新しいCookieを追加するか、既存のCookieを名前で上書きします。"""
    try:
        cookies_dict_list = [cookie.dict() for cookie in cookies]
        cookie_manager.add_or_update_cookies(cookies_dict_list)
        return JSONResponse(
            content={"status": "success", "message": "Cookieが更新されました。"}
        )
    except Exception as e:
        logger.error(f"Cookie更新エラー: {e}")
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
        logger.error(f"Cookie削除エラー: {e}")
        raise HTTPException(status_code=500, detail="Cookieの削除に失敗しました。")

# ヘルスチェックとデバッグエンドポイント
@app.get("/health", summary="ヘルスチェック")
async def health_check():
    """サーバーとブラウザプールの状態を確認します。"""
    try:
        browser_status = await scraper.get_browser_pool_status()
        return JSONResponse(content={
            "status": "healthy",
            "browser_pool": browser_status,
            "timestamp": asyncio.get_event_loop().time()
        })
    except Exception as e:
        logger.error(f"ヘルスチェックエラー: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "unhealthy", "error": str(e)}
        )

@app.get("/debug", summary="デバッグ情報")
async def debug_info():
    """システムのデバッグ情報を取得します。"""
    import os
    import sys
    try:
        browser_status = await scraper.get_browser_pool_status()
        return JSONResponse(content={
            "python_version": sys.version,
            "working_directory": os.getcwd(),
            "environment_variables": {
                "PLAYWRIGHT_BROWSERS_PATH": os.getenv("PLAYWRIGHT_BROWSERS_PATH"),
                "PORT": os.getenv("PORT", "未設定"),
                "PYTHONUNBUFFERED": os.getenv("PYTHONUNBUFFERED", "未設定")
            },
            "browser_pool_status": browser_status,
            "available_files": os.listdir("/app") if os.path.exists("/app") else [],
            "playwright_browsers": os.listdir("/ms/playwright") if os.path.exists("/ms/playwright") else []
        })
    except Exception as e:
        logger.error(f"デバッグ情報取得エラー: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )
