FROM python:3.10-slim

# 必要なツール
RUN apt-get update && apt-get install -y wget curl libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# playwrightのfirefoxインストール
RUN playwright install --with-deps firefox

COPY . .

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "10000"]
