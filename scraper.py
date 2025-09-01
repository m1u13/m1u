import asyncio
import time
from playwright.async_api import async_playwright, Browser, BrowserContext, Error as PlaywrightError
from typing import Optional
import atexit

# local import
import cookie_manager

class BrowserPool:
    """ブラウザインスタンスを再利用するためのプール"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self._lock = asyncio.Lock()
        self._last_used = 0
        self.IDLE_TIMEOUT = 300  # 5分間使用されなければブラウザを閉じる
        
    async def get_browser_context(self):
        """ブラウザコンテキストを取得（必要に応じて新規作成）"""
        async with self._lock:
            current_time = time.time()
            
            # アイドル状態が長い場合は既存のブラウザを閉じる
            if (self.browser and 
                current_time - self._last_used > self.IDLE_TIMEOUT):
                await self._close_browser()
            
            # ブラウザが存在しない場合は新規作成
            if not self.browser:
                playwright = await async_playwright().start()
                self.browser = await playwright.firefox.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-web-security',
                        '--memory-pressure-off',
                    ]
                )
                
            # コンテキストを新規作成（毎回新しいコンテキストを使用してセッション分離）
            if self.context:
                await self.context.close()
                
            # 保存されたCookieを読み込み
            saved_cookies = cookie_manager.load_cookies()
            self.context = await self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            
            if saved_cookies:
                await self.context.add_cookies(saved_cookies)
                
            self._last_used = current_time
            return self.context
    
    async def _close_browser(self):
        """ブラウザを閉じる"""
        if self.context:
            await self.context.close()
            self.context = None
        if self.browser:
            await self.browser.close()
            self.browser = None
    
    async def cleanup(self):
        """リソースをクリーンアップ"""
        await self._close_browser()

# グローバルブラウザプールインスタンス
_browser_pool = BrowserPool()

# アプリケーション終了時のクリーンアップ
atexit.register(lambda: asyncio.create_task(_browser_pool.cleanup()))

async def get_html_after_wait(url: str, wait_seconds: float = 2.0) -> str:
    """
    URLにアクセスし、指定秒数後のHTMLを取得する。
    Cookieは自動で読み込み・保存更新される。
    ブラウザインスタンスを再利用してパフォーマンスを向上。
    """
    context = None
    page = None
    
    try:
        # ブラウザコンテキストを取得
        context = await _browser_pool.get_browser_context()
        page = await context.new_page()
        
        # ページ読み込み完了イベントを待機するPromise
        load_promise = page.wait_for_load_state('networkidle', timeout=30000)
        
        # ページに移動
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        
        # 指定時間待機（デフォルト2秒に短縮）
        await asyncio.sleep(wait_seconds)
        
        # ネットワークアイドル状態を待つか、タイムアウトまで待つ
        try:
            await asyncio.wait_for(load_promise, timeout=3.0)
        except asyncio.TimeoutError:
            # ネットワークアイドルにならない場合はそのまま続行
            pass
        
        # HTMLコンテンツを取得
        html_content = await page.content()
        
        # 最新のCookieを保存
        current_cookies = await context.cookies()
        cookie_manager.add_or_update_cookies(current_cookies)
        
        return html_content
        
    except Exception as e:
        print(f"スクレイピング中にエラーが発生しました: {e}")
        return f"<html><body><h1>Error</h1><p>An error occurred: {str(e)}</p></body></html>"
    
    finally:
        # ページのみを閉じる（コンテキストとブラウザは再利用）
        if page:
            await page.close()

# 後方互換性のためのエイリアス
async def get_html_after_5s(url: str) -> str:
    """旧関数名との後方互換性を保つ"""
    return await get_html_after_wait(url, 2.0)  # 5秒から2秒に短縮

# ヘルスチェック用の軽量スクレイピング
async def quick_scrape(url: str) -> str:
    """高速スクレイピング（待機時間1秒）"""
    return await get_html_after_wait(url, 1.0)
