from fastapi import FastAPI
from pydantic import BaseModel
from playwright.async_api import async_playwright, Playwright, Browser, Error as PlaywrightError
import os
import json
from contextlib import asynccontextmanager

# --- グローバル変数と設定 ---
COOKIE_FILE = "cookies.json"

# PlaywrightとBrowserのインスタンスをアプリケーション全体で共有
playwright: Playwright = None
browser: Browser = None

# --- FastAPIのライフサイクル管理 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    アプリケーション起動時にPlaywrightとブラウザを一度だけ初期化し、
    終了時に安全に閉じることでパフォーマンスを向上させます。
    """
    global playwright, browser
    print("アプリケーションを起動します...")
    playwright = await async_playwright().start()
    browser = await playwright.firefox.launch(headless=True)
    yield
    print("アプリケーションを終了します...")
    await browser.close()
    await playwright.stop()

app = FastAPI(lifespan=lifespan)

# --- モデル定義 ---
class URLRequest(BaseModel):
	url: str

class CookiesRequest(BaseModel):
	cookies: list

# --- ヘルパー関数 ---
def load_cookies():
	if os.path.exists(COOKIE_FILE):
		with open(COOKIE_FILE, "r") as f:
			return json.load(f)
	return []

def save_cookies(cookies):
	with open(COOKIE_FILE, "w") as f:
		json.dump(cookies, f)

# --- APIエンドポイント ---
@app.post("/scrape")
async def scrape(request: URLRequest):
    """
    指定されたURLの読み込みを開始し、5秒間待機してからHTMLを取得します。
    """
    context = await browser.new_context()
    try:
        # Cookieをロード
        cookies = load_cookies()
        if cookies:
            await context.add_cookies(cookies)
        
        page = await context.new_page()
        
        # ★変更点: ページの読み込み完了を待たずに、ナビゲーションが開始されたら次に進む
        await page.goto(request.url, wait_until="commit")
        
        # 読み込み処理と並行して5秒間待機
        await page.wait_for_timeout(5000)
        
        # 5秒経過した時点でのHTMLを取得
        html = await page.content()
        
        # Cookieを取得・保存
        current_cookies = await context.cookies()
        save_cookies(current_cookies)
        
        return {"html": html}
        
    except PlaywrightError as e:
        return {"error": f"Playwright Error: {e}"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}
    finally:
        # 各リクエストの完了時にコンテキストを閉じる
        await context.close()

@app.get("/cookies")
async def get_cookies():
	cookies = load_cookies()
	return {"cookies": cookies}

@app.post("/cookies")
async def set_cookies(req: CookiesRequest):
	save_cookies(req.cookies)
	return {"status": "saved"}

@app.delete("/cookies")
async def delete_cookies():
	if os.path.exists(COOKIE_FILE):
		os.remove(COOKIE_FILE)
	return {"status": "deleted"}
