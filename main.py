from fastapi import FastAPI
from pydantic import BaseModel
from playwright.async_api import async_playwright
import os
import json

app = FastAPI()
COOKIE_FILE = "cookies.json"

class URLRequest(BaseModel):
    url: str

class CookiesRequest(BaseModel):
    cookies: list

def load_cookies():
    if os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE, "r") as f:
            return json.load(f)
    return []

def save_cookies(cookies):
    with open(COOKIE_FILE, "w") as f:
        json.dump(cookies, f)

@app.on_event("startup")
async def startup():
    """
    アプリ起動時に Playwright を立ち上げ、context を作成
    """
    global playwright, browser, context
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context()

    # 保存済みクッキーがあれば読み込む
    cookies = load_cookies()
    if cookies:
        await context.add_cookies(cookies)

@app.on_event("shutdown")
async def shutdown():
    """
    アプリ終了時にブラウザをクローズ
    """
    await browser.close()
    await playwright.stop()

@app.post("/scrape")
async def scrape_url(data: dict):
    url = data["url"]
    page = await context.new_page()
    try:
        # 最大5秒待機
        await page.goto(url, wait_until="networkidle", timeout=5000)
    except Exception:
        # タイムアウトした場合もその時点のHTMLを取得
        pass
    html = await page.content()
    await page.close()
    return {"html": html}

@app.get("/cookies")
async def get_cookies():
    cookies = await context.cookies()
    return {"cookies": cookies}

@app.post("/cookies")
async def set_cookies(req: CookiesRequest):
    await context.add_cookies(req.cookies)
    save_cookies(req.cookies)  # ファイルにも保存
    return {"status": "saved"}

@app.delete("/cookies")
async def delete_cookies():
    await context.clear_cookies()
    if os.path.exists(COOKIE_FILE):
        os.remove(COOKIE_FILE)
    return {"status": "deleted"}
