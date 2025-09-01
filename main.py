from fastapi import FastAPI, HTTPException, Body, Query
from fastapi.responses import HTMLResponse, JSONResponse
from typing import List
from pydantic import BaseModel, Field

#local imports
import scraper
import cookie_manager

app = FastAPI(
	title="Playwright Scraping Server",
	description="動的ウェブページをスクレイピングし、Cookieを管理するAPIサーバーです。"
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


@app.get("/", response_class=HTMLResponse, summary="サーバー状態確認")
async def read_root():
	"""サーバーが正常に動作しているか確認します。"""
	return "<h1>Scraping Server is running 🚀</h1>"

@app.get("/scrape", response_class=HTMLResponse, summary="URLをスクレイピング")
async def scrape_url(url: str):
	"""
	指定されたURLにアクセスし、5秒後のHTMLコンテンツを返します。
	アクセス中に取得・更新されたCookieはサーバーに保存されます。
	"""
	if not url.startswith(("http://", "https://")):
		raise HTTPException(status_code=400, detail="無効なURL形式です。http:// または https:// で始まる必要があります。")
	try:
		html_content = await scraper.get_html_after_5s(url)
		return HTMLResponse(content=html_content)
	except Exception as e:
		print(f"An error occurred during scraping: {e}")
		raise HTTPException(status_code=500, detail=f"内部エラーが発生しました: {str(e)}")

#--- Cookie管理エンドポイント ---

@app.get("/cookies", response_model=List[CookieModel], summary="全Cookieを取得")
async def get_all_cookies():
	"""サーバーに保存されているすべてのCookieを取得します。"""
	return cookie_manager.load_cookies()

@app.post("/cookies", summary="Cookieを追加・更新")
async def add_or_update_user_cookies(cookies: List[CookieModel] = Body(...)):
	"""
	新しいCookieを追加するか、既存のCookieを名前で上書きします。
	CookieのリストをリクエストボディとしてJSON形式で送信してください。
	"""
	try:
		cookies_dict_list = [cookie.dict() for cookie in cookies]
		cookie_manager.add_or_update_cookies(cookies_dict_list)
		return JSONResponse(content={"status": "success", "message": "Cookieが更新されました。"})
	except Exception as e:
		print(f"Error updating cookies: {e}")
		raise HTTPException(status_code=500, detail="Cookieの更新に失敗しました。")

@app.delete("/cookies", summary="Cookieを削除")
async def delete_user_cookies(names: List[str] = Query(..., description="削除したいCookieの名前のリスト。例: /cookies?names=session_id&names=user_token")):
	"""
	指定された名前を持つCookieを削除します。
	"""
	if not names:
		raise HTTPException(status_code=400, detail="削除するCookieの名前が指定されていません。")
	try:
		cookie_manager.delete_cookies_by_name(names)
		return JSONResponse(content={"status": "success", "message": f"Cookie {names} が削除されました。"})
	except Exception as e:
		print(f"Error deleting cookies: {e}")
		raise HTTPException(status_code=500, detail="Cookieの削除に失敗しました。")

