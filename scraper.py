# scraper.py

import asyncio
from playwright.async_api import Browser, Error as PlaywrightError # 変更点: Browserをインポート

#local import
import cookie_manager

# --- 変更点: 関数名を変更し、引数にBrowserオブジェクトを追加 ---
async def get_page_html(browser: Browser, url: str) -> str:
	"""
	既存のブラウザインスタンスを使用してURLにアクセスし、5秒後のHTMLを取得する。
	リクエストごとに新しいコンテキストとページが作成される。
	"""
    # --- 削除: Playwrightの起動処理は不要 ---
	# async with async_playwright() as p:
		# browser = await p.firefox.launch(headless=True)
		
	# 既存のCookieを読み込んでコンテキストを作成
	saved_cookies = cookie_manager.load_cookies()
	# --- 変更点: 引数のbrowserからコンテキストを作成 ---
	context = await browser.new_context()
	if saved_cookies:
		await context.add_cookies(saved_cookies)

	page = await context.new_page()

	html_content = ""
	try:
		# ページへの移動をバックグラウンドタスクとして開始
		goto_task = asyncio.create_task(page.goto(url, wait_until="load", timeout=60000))

		# 5秒間待機
		await asyncio.sleep(5)
		
		# 5秒経過時点でのHTMLを取得
		html_content = await page.content()

		# ナビゲーションタスクがまだ実行中の場合はキャンセル
		if not goto_task.done():
			goto_task.cancel()
		else:
			# 完了している場合、エラーが発生していないか確認(エラーは無視)
			try:
				await goto_task
			except PlaywrightError as e:
				print(f"Background navigation task finished with an error (ignored): {e}")

	except Exception as e:
		print(f"An error occurred during scraping process: {e}")
		html_content = f"<html><body>An error occurred: {e}</body></html>"
	finally:
		# 処理が成功しても失敗しても、最新のCookieを取得して保存
		current_cookies = await context.cookies()
		cookie_manager.add_or_update_cookies(current_cookies)
		# --- 変更点: ブラウザは閉じずに、コンテキストのみ閉じる ---
		await context.close() # ページとコンテキストをクリーンアップ
	
	return html_content
