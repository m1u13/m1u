import asyncio
from playwright.async_api import async_playwright, Error as PlaywrightError

#local import
import cookie_manager

async def get_html_after_5s(url: str) -> str:
	"""
	URLにアクセスし、5秒後のHTMLを取得する。
	Cookieは自動で読み込み・保存更新される。
	"""
	async with async_playwright() as p:
		#ヘッドレスのFirefoxを起動
		browser = await p.firefox.launch(headless=True)
		
		#既存のCookieを読み込んでコンテキストを作成
		saved_cookies = cookie_manager.load_cookies()
		context = await browser.new_context()
		if saved_cookies:
			await context.add_cookies(saved_cookies)

		page = await context.new_page()

		html_content = ""
		try:
			#ページへの移動をバックグラウンドタスクとして開始
			#ページの読み込み完了を待たずに次の処理へ進む
			goto_task = asyncio.create_task(page.goto(url, wait_until="load", timeout=60000))

			#5秒間待機
			await asyncio.sleep(5)
			
			#5秒経過時点でのHTMLを取得
			html_content = await page.content()

			#ナビゲーションタスクがまだ実行中の場合はキャンセル
			if not goto_task.done():
				goto_task.cancel()
			else:
				#完了している場合、エラーが発生していないか確認(エラーは無視)
				try:
					await goto_task
				except PlaywrightError as e:
					print(f"Background navigation task finished with an error (ignored): {e}")

		except Exception as e:
			print(f"An error occurred during scraping process: {e}")
			html_content = f"<html><body>An error occurred: {e}</body></html>"
		finally:
			#処理が成功しても失敗しても、最新のCookieを取得して保存
			current_cookies = await context.cookies()
			cookie_manager.add_or_update_cookies(current_cookies)
			await browser.close()
		
		return html_content

