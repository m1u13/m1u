FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# システムレベルの最適化とPlaywrightブラウザの確実なインストール
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# 必要な依存関係をコピーしてインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwrightブラウザを明示的にインストール
RUN playwright install firefox
RUN playwright install-deps firefox

# アプリケーションソースをコピー
COPY . .

# 永続化ディスクのマウントポイントを作成
RUN mkdir -p /app/data

# 環境変数でパフォーマンス最適化
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms/playwright

# ポート設定（Render.comが環境変数PORTを自動設定するため）
EXPOSE 10000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1 --loop asyncio"]
