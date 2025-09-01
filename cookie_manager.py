import json
import os
from typing import List, Dict

#Render.comの永続ディスクのマウントパス
COOKIE_DIR = "/app/data"
COOKIE_FILE = os.path.join(COOKIE_DIR, "cookies.json")

def _ensure_dir():
	"""Cookie保存用のディレクトリが存在することを確認・作成する"""
	os.makedirs(COOKIE_DIR, exist_ok=True)

def load_cookies() -> List[Dict]:
	"""保存されたCookieをファイルから読み込む"""
	_ensure_dir()
	if not os.path.exists(COOKIE_FILE):
		return []
	try:
		with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
			return json.load(f)
	except (json.JSONDecodeError, FileNotFoundError):
		return []

def save_cookies(cookies: List[Dict]):
	"""Cookieのリストをファイルに上書き保存する"""
	_ensure_dir()
	with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
		json.dump(cookies, f, indent=2, ensure_ascii=False)

def add_or_update_cookies(new_cookies: List[Dict]):
	"""既存のCookieリストに新しいCookieを追加または上書きする"""
	existing_cookies = load_cookies()
	#新しいCookieを効率的に検索できるよう辞書に変換
	new_cookies_dict = {cookie['name']: cookie for cookie in new_cookies}
	
	updated_cookies = []
	#既存のCookieをループし、新しいものがあれば更新
	for cookie in existing_cookies:
		if cookie['name'] in new_cookies_dict:
			#更新するCookieを追加し、辞書から削除
			updated_cookies.append(new_cookies_dict.pop(cookie['name']))
		else:
			#更新がないものはそのまま追加
			updated_cookies.append(cookie)
			
	#辞書に残ったCookie(=完全な新規Cookie)を追加
	updated_cookies.extend(new_cookies_dict.values())
	
	save_cookies(updated_cookies)

def delete_cookies_by_name(names_to_delete: List[str]):
	"""指定された名前のリストに一致するCookieを削除する"""
	cookies = load_cookies()
	updated_cookies = [cookie for cookie in cookies if cookie['name'] not in names_to_delete]
	save_cookies(updated_cookies)

