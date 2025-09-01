import asyncio
import json
import os
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from playwright.async_api import async_playwright

COOKIE_FILE = "cookies.json"

app = FastAPI()

# Cookieの読み込み
def load_cookies():
    if os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# Cookieの保存
def save_cookies(cookies):
    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2, ensure_ascii=False)

# ページを取得する関数
async def fetch_html(url: str):
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context()

        # 既存Cookieをロード
        stored_cookies = load_cookies()
        if stored_cookies:
            await context.add_cookies(stored_cookies)

        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=10000)
        except Exception:
            pass  # タイムアウトしても続行

        await page.wait_for_timeout(5000)  # 最大5秒待機
        content = await page.content()

        # Cookieを保存
        cookies = await context.cookies()
        save_cookies(cookies)

        await browser.close()
        return content


@app.get("/fetch")
async def fetch(url: str = Query(..., description="取得するURL")):
    html = await fetch_html(url)
    return PlainTextResponse(html)


@app.get("/cookies")
def get_cookies():
    return JSONResponse(load_cookies())


@app.post("/cookies")
def add_or_update_cookie(cookie: dict):
    cookies = load_cookies()
    # 既存のcookieを上書き
    cookies = [c for c in cookies if not (c["name"] == cookie["name"] and c.get("domain") == cookie.get("domain"))]
    cookies.append(cookie)
    save_cookies(cookies)
    return {"status": "updated", "cookie": cookie}


@app.delete("/cookies")
def delete_cookie(name: str, domain: str = None):
    cookies = load_cookies()
    new_cookies = [c for c in cookies if not (c["name"] == name and (domain is None or c.get("domain") == domain))]
    save_cookies(new_cookies)
    return {"status": "deleted", "name": name, "domain": domain}
