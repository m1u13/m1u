FROM python:3.11-slim

# 必須ライブラリをインストール
RUN apt-get update && apt-get install -y \
    wget curl gnupg \
    libnss3 libatk-bridge2.0-0 libxkbcommon0 libgtk-3-0 libasound2 \
    libdrm2 libdbus-1-3 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libcups2 \
    && rm -rf /var/lib/apt/lists/*

# Pythonパッケージをインストール
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# PlaywrightブラウザをRenderの推奨パスにインストール
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN python -m playwright install --with-deps firefox

# 作業ディレクトリはRender推奨パス
WORKDIR /opt/render/project/src

# アプリをコピー
COPY . .

# Renderで公開するポート
EXPOSE 10000

# FastAPIサーバー起動 (server.py の app を指定)
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "10000"]
