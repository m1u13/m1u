# Playwrightの公式Pythonイメージを使用します。
# 必要な依存関係やブラウザがプリインストールされています。
FROM mcr.microsoft.com/playwright/python:v1.55.0-jammy

# コンテナ内の作業ディレクトリを設定
WORKDIR /app

# 依存関係ファイルをコピーしてインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションのソースコードをコピー
COPY . .

# render.comは自動でPORT環境変数を設定します。
# uvicornがこのポートをリッスンするように設定します。
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]

