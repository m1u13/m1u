import asyncio
from playwright.async_api import Page, Error as PlaywrightError

# cookie_managerのimportは不要になったので削除

async def get_html_after_5s(page: Page, url: str) -> str:
    """
    既存のPageオブジェクトを使い、URLにアクセスして5秒後のHTMLを取得する。
    Cookieの管理はこの関数の外部で行われる。
    """
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
    
    # ブラウザの終了やCookieの保存処理はここから削除
    
    return html_content
