from fastapi import FastAPI, Request
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
            await page.goto(request.url)
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
