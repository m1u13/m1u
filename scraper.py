import asyncio
import time
import os
from playwright.async_api import async_playwright, Browser, BrowserContext, Error as PlaywrightError
from typing import Optional
import atexit
import logging

# local import
import cookie_manager

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BrowserPool:
    """ブラウザインスタンスを再利用するためのプール"""
    
    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self._lock = asyncio.Lock()
        self._last_used = 0
        self.IDLE_TIMEOUT = 300  # 5分間使用されなければブラウザを閉じる
        self._initialization_attempted = False
        
    async def _initialize_playwright(self):
        """Playwrightを初期化"""
        if not self.playwright:
            try:
                self.playwright = await async_playwright().start()
                logger.info("Playwright初期化完了")
            except Exception as e:
                logger.error(f"Playwright初期化エラー: {e}")
                raise
        
    async def _create_browser(self):
        """新しいブラウザインスタンスを作成"""
        if not self.playwright:
            await self._initialize_playwright()
            
        try:
            # Firefoxブラウザを起動（フォールバック付き）
            browser_args = [
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-web-security',
                '--memory-pressure-off',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding'
            ]
            
            try:
                self.browser = await self.playwright.firefox.launch(
                    headless=True,
                    args=browser_args
                )
                logger.info("Firefoxブラウザ起動完了")
            except Exception as firefox_error:
                logger.warning(f"Firefox起動失敗、Chromiumにフォールバック: {firefox_error}")
                # Firefoxが失敗した場合はChromiumを試す
                self.browser = await self.playwright.chromium.launch(
                    headless=True,
                    args=browser_args
                )
                logger.info("Chromiumブラウザ起動完了")
                
        except Exception as e:
            logger.error(f"ブラウザ起動エラー: {e}")
            raise
        
    async def get_browser_context(self):
        """ブラウザコンテキストを取得（必要に応じて新規作成）"""
        async with self._lock:
            current_time = time.time()
            
            # 初回初期化チェック
            if not self._initialization_attempted:
                self._initialization_attempted = True
                await self._initialize_playwright()
            
            # アイドル状態が長い場合は既存のブラウザを閉じる
            if (self.browser and 
                current_time - self._last_used > self.IDLE_TIMEOUT):
                logger.info("アイドルタイムアウトによりブラウザを再起動")
                await self._close_browser()
            
            # ブラウザが存在しない場合は新規作成
            if not self.browser:
                await self._create_browser()
                
            # コンテキストを新規作成（毎回新しいコンテキストを使用してセッション分離）
            if self.context:
                await self.context.close()
                
            # 保存されたCookieを読み込み
            saved_cookies = cookie_manager.load_cookies()
            
            # コンテキスト作成オプション
            context_options = {
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'viewport': {'width': 1920, 'height': 1080},
                'accept_downloads': False,
                'bypass_csp': True,
                'java_script_enabled': True
            }
            
            self.context = await self.browser.new_context(**context_options)
            
            if saved_cookies:
                try:
                    await self.context.add_cookies(saved_cookies)
                    logger.info(f"{len(saved_cookies)}個のCookieを読み込みました")
                except Exception as e:
                    logger.warning(f"Cookie読み込みエラー（無視して続行）: {e}")
                
            self._last_used = current_time
            return self.context
    
    async def _close_browser(self):
        """ブラウザを閉じる"""
        try:
            if self.context:
                await self.context.close()
                self.context = None
                logger.info("ブラウザコンテキストを閉じました")
                
            if self.browser:
                await self.browser.close()
                self.browser = None
                logger.info("ブラウザを閉じました")
        except Exception as e:
            logger.error(f"ブラウザクローズエラー: {e}")
    
    async def cleanup(self):
        """リソースをクリーンアップ"""
        try:
            await self._close_browser()
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
                logger.info("Playwrightリソースをクリーンアップしました")
        except Exception as e:
            logger.error(f"クリーンアップエラー: {e}")

# グローバルブラウザプールインスタンス
_browser_pool = BrowserPool()

# アプリケーション終了時のクリーンアップ
def cleanup_browser_pool():
    try:
        # イベントループが存在する場合のみタスクを作成
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(_browser_pool.cleanup())
        else:
            asyncio.run(_browser_pool.cleanup())
    except Exception as e:
        logger.error(f"終了時クリーンアップエラー: {e}")

atexit.register(cleanup_browser_pool)

async def get_html_after_wait(url: str, wait_seconds: float = 2.0) -> str:
    """
    URLにアクセスし、指定秒数後のHTMLを取得する。
    Cookieは自動で読み込み・保存更新される。
    ブラウザインスタンスを再利用してパフォーマンスを向上。
    """
    context = None
    page = None
    
    try:
        logger.info(f"スクレイピング開始: {url}")
        
        # ブラウザコンテキストを取得
        context = await _browser_pool.get_browser_context()
        page = await context.new_page()
        
        # ページ設定
        await page.set_extra_http_headers({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # タイムアウト設定
        page.set_default_navigation_timeout(30000)
        page.set_default_timeout(30000)
        
        # ページに移動
        logger.info(f"ページにアクセス中: {url}")
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        
        # 指定時間待機
        logger.info(f"{wait_seconds}秒間待機中...")
        await asyncio.sleep(wait_seconds)
        
        # 追加の読み込み完了を待つ（オプション）
        try:
            await page.wait_for_load_state('networkidle', timeout=3000)
            logger.info("ネットワークアイドル状態を確認")
        except asyncio.TimeoutError:
            logger.info("ネットワークアイドル待機タイムアウト（正常継続）")
        
        # HTMLコンテンツを取得
        html_content = await page.content()
        logger.info(f"HTML取得完了: {len(html_content)}文字")
        
        # 最新のCookieを保存
        try:
            current_cookies = await context.cookies()
            if current_cookies:
                cookie_manager.add_or_update_cookies(current_cookies)
                logger.info(f"{len(current_cookies)}個のCookieを保存しました")
        except Exception as e:
            logger.warning(f"Cookie保存エラー（無視して続行）: {e}")
        
        return html_content
        
    except Exception as e:
        error_msg = f"スクレイピング中にエラーが発生しました: {e}"
        logger.error(error_msg)
        return f"<html><body><h1>Error</h1><p>{error_msg}</p></body></html>"
    
    finally:
        # ページのみを閉じる（コンテキストとブラウザは再利用）
        if page:
            try:
                await page.close()
                logger.info("ページを閉じました")
            except Exception as e:
                logger.warning(f"ページクローズエラー: {e}")

# 後方互換性のためのエイリアス
async def get_html_after_5s(url: str) -> str:
    """旧関数名との後方互換性を保つ"""
    return await get_html_after_wait(url, 2.0)  # 5秒から2秒に短縮

# ヘルスチェック用の軽量スクレイピング
async def quick_scrape(url: str) -> str:
    """高速スクレイピング（待機時間1秒）"""
    return await get_html_after_wait(url, 1.0)

# ブラウザプールの状態確認
async def get_browser_pool_status():
    """ブラウザプールの状態を取得"""
    return {
        "browser_active": _browser_pool.browser is not None,
        "context_active": _browser_pool.context is not None,
        "last_used": _browser_pool._last_used,
        "idle_timeout": _browser_pool.IDLE_TIMEOUT
    }
