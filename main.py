import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import HTMLResponse, JSONResponse
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

#--- グローバル変数 ---
#Render.comの永続ディスクのパス `/data` を利用してCookieファイルを保存
#ローカル環境でテストする場合は、プロジェクトルートに `cookie_storage.json` が作成されます。
COOKIE_FILE_PATH = Path("/data/cookie_storage.json" if Path("/data").is_dir() else "cookie_storage.json")

#Playwrightのインスタンスを格納する変数
playwright_instance = None
browser: Browser | None = None
context: BrowserContext | None = None

#--- ヘルパー関数 ---
async def save_cookies_to_file():
	"""現在のブラウザコンテキストのCookieをファイルに永続化します。"""
	if context:
		cookies = await context.cookies()
		#保存先ディレクトリがなければ作成
		COOKIE_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
		with open(COOKIE_FILE_PATH, 'w') as f:
			json.dump(cookies, f, indent=2)
		print(f"Cookieを {COOKIE_FILE_PATH} に保存しました。")

async def load_cookies_from_file() -> list:
	"""ファイルからCookieを読み込みます。"""
	if COOKIE_FILE_PATH.exists():
		with open(COOKIE_FILE_PATH, 'r') as f:
			try:
				return json.load(f)
			except json.JSONDecodeError:
				return []
	return []

#--- FastAPIのライフサイクル管理 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
	"""アプリケーション起動時にPlaywrightを初期化し、終了時にクリーンアップします。"""
	global playwright_instance, browser, context

	#起動処理
	print("サーバーを起動します...")
	playwright_instance = await async_playwright().start()
	browser = await playwright_instance.firefox.launch(headless=True)
	
	#ファイルからCookieを読み込んでコンテキストを作成
	initial_cookies = await load_cookies_from_file()
	context = await browser.new_context(
		storage_state={"cookies": initial_cookies} if initial_cookies else None
	)
	print("✅ PlaywrightとFirefoxの起動が完了しました。")
	
	yield #ここでアプリケーションが実行される
	
	#終了処理
	print("サーバーをシャットダウンします...")
	await save_cookies_to_file()
	if context: await context.close()
	if browser: await browser.close()
	if playwright_instance: await playwright_instance.stop()
	print("✅ Playwrightを正常に終了しました。")

#--- FastAPIアプリケーションのインスタンス化 ---
app = FastAPI(lifespan=lifespan, title="Playwright Scraping Server")

#--- APIエンドポイント定義 ---

@app.get("/", response_class=HTMLResponse, summary="APIの基本情報")
async def root():
	"""APIの簡単な説明とエンドポイント一覧を返します。"""
	return """
	<html><head><title>Playwright Scraper API</title></head><body>
	<h1>Playwright Scraper API 🚀</h1>
	<p>指定された動的ページのHTMLやCookieを取得・操作するAPIです。</p>
	<h2>エンドポイント</h2>
	<ul>
		<li><b>GET /scrape?url=...</b>: URLにアクセスし、5秒後のHTMLを取得します。</li>
		<li><b>GET /cookies</b>: 現在保存されている全てのCookieをJSON形式で取得します。</li>
		<li><b>POST /cookies</b>: 新しいCookieを追加または上書きします。</li>
		<li><b>DELETE /cookies</b>: 指定した名前のCookieを削除します。</li>
	</ul>
	</body></html>
	"""

@app.get("/scrape", response_class=HTMLResponse, summary="ページのHTMLを取得")
async def scrape_url(url: str):
	"""
	指定されたURLにアクセスし、ナビゲーション開始から5秒後の時点でのHTMLを返します。
	ページの読み込み完了は待ちません。
	"""
	if not context:
		raise HTTPException(status_code=503, detail="ブラウザが準備できていません。")
	if not url or not (url.startswith("http://") or url.startswith("https://")):
		raise HTTPException(status_code=400, detail="有効なURLを'url'クエリパラメータで指定してください。")

	page: Page | None = None
	try:
		page = await context.new_page()
		#`wait_until="commit"`: HTMLドキュメントの受信が始まったら待機を終了し、次の処理へ進む
		await page.goto(url, wait_until="commit", timeout=15000)
		
		#5秒間待機
		await page.wait_for_timeout(5000)
		
		html_content = await page.content()
		return HTMLResponse(content=html_content)
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"スクレイピング中にエラーが発生しました: {e}")
	finally:
		if page:
			await page.close()

@app.get("/cookies", response_class=JSONResponse, summary="全Cookieを取得")
async def get_all_cookies():
	"""現在ブラウザに保存されている全てのCookieを返します。"""
	if not context:
		raise HTTPException(status_code=503, detail="ブラウザが準備できていません。")
	return await context.cookies()

@app.post("/cookies", status_code=201, summary="Cookieを追加/上書き")
async def add_or_update_cookies(cookies: list = Body(..., examples=[[{"name": "sessionid", "value": "xyz...", "domain": ".example.com", "path": "/"}]])):
	"""
	新しいCookieを追加、または同名のCookieを上書きします。
	リクエストボディにはPlaywrightのCookieフォーマットのリストを指定します。
	"""
	if not context:
		raise HTTPException(status_code=503, detail="ブラウザが準備できていません。")
	try:
		await context.add_cookies(cookies)
		await save_cookies_to_file() #変更を即時ファイルに保存
		return {"message": f"{len(cookies)}個のCookieを追加/更新しました。"}
	except Exception as e:
		raise HTTPException(status_code=400, detail=f"Cookieの形式が不正か、追加に失敗しました: {e}")

@app.delete("/cookies", summary="指定したCookieを削除")
async def delete_cookies(payload: dict = Body(..., examples=[{"names": ["sessionid", "csrftoken"]}])):
	"""
	リクエストボディで指定された名前のCookieを削除します。
	{"names": ["cookie_name_1", "cookie_name_2"]} の形式で指定します。
	"""
	if not context:
		raise HTTPException(status_code=503, detail="ブラウザが準備できていません。")
	
	names_to_delete = payload.get("names", [])
	if not isinstance(names_to_delete, list):
		raise HTTPException(status_code=400, detail="ボディは {'names': ['cookie1', ...]} の形式でなければなりません。")

	all_cookies = await context.cookies()
	remaining_cookies = [c for c in all_cookies if c.get("name") not in names_to_delete]
	
	await context.clear_cookies()
	if remaining_cookies:
		await context.add_cookies(remaining_cookies)
	
	await save_cookies_to_file() #変更を即時ファイルに保存
	
	deleted_count = len(all_cookies) - len(remaining_cookies)
	return {"message": f"{deleted_count}個のCookieを削除しました。"}

