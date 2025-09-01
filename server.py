from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from playwright.async_api import async_playwright
import os, json

app = FastAPI()
COOKIE_FILE = "cookies.json"

class URLRequest(BaseModel):
    url: str

class Cookie(BaseModel):
    name: str
    value: str
    domain: Optional[str] = None
    path: Optional[str] = "/"

class CookiesRequest(BaseModel):
    cookies: List[Cookie]

def load_cookies():
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []

def save_cookies(cookies):
    tmp_file = COOKIE_FILE + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2, ensure_ascii=False)
    os.replace(tmp_file, COOKIE_FILE)

@app.post("/scrape")
async def scrape(request: URLRequest):
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context()

        # Cookieロード
        cookies = load_cookies()
        if cookies:
            await context.add_cookies(cookies)

        page = await context.new_page()
        try:
            await page.goto(request.url, wait_until="domcontentloaded", timeout=10000)
            await page.wait_for_timeout(5000)
            html = await page.content()

            # Cookie取得・保存
            cookies = await context.cookies()
            save_cookies(cookies)

            return {"html": html}
        except Exception as e:
            return {"error": str(e)}
        finally:
            await browser.close()

@app.get("/cookies")
async def get_cookies():
    return {"cookies": load_cookies()}

@app.post("/cookies")
async def set_cookies(req: CookiesRequest):
    save_cookies([cookie.dict() for cookie in req.cookies])
    return {"status": "saved"}

@app.delete("/cookies")
async def delete_cookies():
    if os.path.exists(COOKIE_FILE):
        os.remove(COOKIE_FILE)
    return {"status": "deleted"}
