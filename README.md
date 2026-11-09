# 客家文化知識平台

以客家文化題庫練習聽說：抽取文化問題、將參考答案轉成所選腔調並合成語音、錄下回答後透過客語 ASR 辨識，最後以字元相似度提供練習分數。

## 本機啟動

1. 安裝 Python 3.10 或更新版本。
2. 安裝依賴：`pip install -r requirements.txt`
3. 設定環境變數 `GOHAKKA_API_TOKEN`（請使用新輪替的金鑰）。
4. 啟動：`python app.py`，再開啟 `http://localhost:10000`。

## Render 部署

此專案含 `render.yaml`。在 Render 選擇 **New + → Blueprint**，連結 GitHub 上的 `Hakka-culture` repository，並在建立服務時設定 `GOHAKKA_API_TOKEN`。其餘建置與啟動命令由 Blueprint 提供。

## API 範圍

Gohakka Pro 文件目前提供 `/v3/pro/text/translations`、`/v3/pro/audio/speech` 與 `/v3/pro/audio/transcriptions`。文件未列出 HakkaGPT 題目生成 API，所以目前題目取自 `app.py` 內建的繁體中文文化題庫；語音答案和 ASR 評分使用文件中的客語 API。取得生成 API 的規格後，可將題庫抽題改接生成端點。

腔調選項遵循 API 文件：`sixian`、`hailu`、`dapu`、`raoping`、`zhaoan`、`nansixian`。目前分數是 ASR 結果與參考客語文字的字元相似度，適合作為練習提示，不是正式語言能力評鑑。

## 金鑰安全

金鑰只從 `GOHAKKA_API_TOKEN` 環境變數讀取，不要寫入原始碼、`.env.example` 或 Git。若金鑰曾貼在聊天或其他公開位置，請先在服務端撤銷並建立新金鑰。
