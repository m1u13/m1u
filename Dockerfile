FROM python:3.11-slim

# 必須ライブラリをインストール
RUN apt-get update && apt-get install -y \
    libnss3 libatk-bridge2.0-0 libxkbcommon0 libgtk-3-0 libasound2 \
    wget curl gnupg && \
    rm -rf /var/lib/apt/lists/*

# Pythonパッケージ
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Playwrightブラウザバイナリ取得
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN python -m playwright install firefox --with-deps

WORKDIR /opt/render/project/src
COPY . .

EXPOSE 10000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
