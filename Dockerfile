FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# システムレベルの最適化
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 永続化ディスクのマウントポイントを作成
RUN mkdir -p /app/data

# 環境変数でパフォーマンス最適化
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms/playwright

# ポート設定をより柔軟に
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000", "--workers", "1", "--loop", "asyncio"]
