import base64
import os
import random
import re
import unicodedata
from difflib import SequenceMatcher

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

API_ROOT = os.getenv("GOHAKKA_API_ROOT", "https://api.gohakka.org/v3/pro")
API_TOKEN = os.getenv("GOHAKKA_API_TOKEN", "")
TIMEOUT = int(os.getenv("API_TIMEOUT_SECONDS", "45"))
DIALECTS = {"sixian", "hailu", "dapu", "raoping", "zhaoan", "nansixian"}

# A small, editable starter set of Hakka culture questions. Keep the answer
# concise because the speech endpoint accepts at most 300 characters.
QUESTIONS = [
    {"id": "round_house", "category": "建築", "question": "客家傳統圓樓或土樓，常見的主要用途是什麼？", "answer": "圓樓通常兼具居住與防禦功能，許多家族成員住在同一座圍合式建築裡。"},
    {"id": "lei_cha", "category": "飲食", "question": "客家擂茶通常會把哪些材料研磨後沖泡？", "answer": "擂茶常把茶葉、芝麻、花生和穀物等材料研磨，再沖入熱水飲用。"},
    {"id": "blue_dye", "category": "工藝", "question": "客家藍衫傳統上常使用哪一類染色工藝？", "answer": "客家藍衫常使用藍染工藝，以植物染料把布料染成藍色。"},
    {"id": "mountain_song", "category": "音樂", "question": "客家山歌常見的演唱方式有什麼特色？", "answer": "客家山歌常以山野生活為題材，運用高亢悠揚的曲調對唱或獨唱。"},
    {"id": "salted_pork", "category": "飲食", "question": "客家鹹豬肉的傳統保存方式通常會用到什麼？", "answer": "客家鹹豬肉會用鹽和香料醃漬，幫助保存並增加風味。"},
    {"id": "spring_festival", "category": "節慶", "question": "客家義民祭主要是為了紀念或感謝什麼？", "answer": "義民祭主要是紀念保衛地方、守護鄉里的義民先賢，並表達感念之意。"},
    {"id": "language", "category": "語言", "question": "臺灣客語常見的四縣腔和海陸腔，名稱主要來自什麼？", "answer": "四縣腔和海陸腔的名稱，主要來自早期客家移民原鄉的地名。"},
    {"id": "oil_paper", "category": "工藝", "question": "客家花布常見的圖案特色是什麼？", "answer": "客家花布常見色彩鮮明的花卉圖案，也常搭配紅、藍等亮麗色彩。"},
]


def api_headers():
    if not API_TOKEN:
        raise RuntimeError("尚未設定 GOHAKKA_API_TOKEN。請在部署環境加入 API 金鑰。")
    return {"Authorization": f"Bearer {API_TOKEN}"}


def api_call(path, *, data=None, files=None):
    response = requests.post(
        f"{API_ROOT}{path}", headers=api_headers(), data=data, files=files, timeout=TIMEOUT
    )
    try:
        payload = response.json()
    except ValueError:
        response.raise_for_status()
        raise RuntimeError("客語 API 回傳無法辨識的內容。")
    if not response.ok or not payload.get("success"):
        detail = (payload.get("error") or {}).get("message") or f"API 請求失敗（{response.status_code}）"
        raise RuntimeError(detail)
    return payload.get("data") or {}


def dialect(value):
    value = (value or "sixian").lower()
    if value not in DIALECTS:
        raise ValueError("請選擇有效的客語腔調。")
    return value


def translate_to_hakka(text, accent):
    data = api_call("/text/translations", data={
        "text": text, "dialectCode": accent, "targetCode": "hak", "engine": "model"
    })
    parts = data.get("hak") or []
    if not parts:
        raise RuntimeError("翻譯服務沒有回傳客語文字。")
    return "".join(parts)


def normalize(text):
    text = unicodedata.normalize("NFKC", text or "").lower()
    return "".join(c for c in text if c.isalnum() or "\u3400" <= c <= "\u9fff")


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "api_key_configured": bool(API_TOKEN)})


@app.get("/api/question")
def question():
    item = random.choice(QUESTIONS)
    return jsonify({"id": item["id"], "category": item["category"], "question": item["question"], "answer": item["answer"]})


@app.post("/api/speech")
def speech():
    body = request.get_json(force=True)
    accent = dialect(body.get("dialect"))
    answer = body.get("answer", "").strip()
    if not answer or len(answer) > 300:
        return jsonify({"error": "參考答案需為 1 至 300 個字。"}), 400
    try:
        hak_text = translate_to_hakka(answer, accent)
        audio = api_call("/audio/speech", data={
            "text": hak_text[:300], "dialectCode": accent, "sourceCode": "hak"
        })
        return jsonify({"text": hak_text, "audio": audio.get("audioBase64")})
    except (RuntimeError, requests.RequestException) as exc:
        return jsonify({"error": str(exc)}), 502


@app.post("/api/score")
def score():
    audio = request.files.get("audio")
    question_id = request.form.get("questionId", "")
    if audio is None:
        return jsonify({"error": "請先錄下你的回答。"}), 400
    item = next((q for q in QUESTIONS if q["id"] == question_id), None)
    if item is None:
        return jsonify({"error": "找不到這道題目，請重新抽題。"}), 404
    try:
        accent = dialect(request.form.get("dialect"))
        expected = translate_to_hakka(item["answer"], accent)
        recognized = api_call("/audio/transcriptions", data={"dialectCode": accent}, files={
            "audioFile": (audio.filename or "answer.webm", audio.stream, audio.mimetype or "audio/webm")
        }).get("text", "")
        ref, said = normalize(expected), normalize(recognized)
        score_value = round(SequenceMatcher(None, ref, said).ratio() * 100) if ref else 0
        return jsonify({"recognized": recognized, "expected": expected, "score": score_value,
                        "feedback": "回答很接近參考答案！" if score_value >= 80 else "再聽一次參考答案，試著把重點說完整。"})
    except (RuntimeError, requests.RequestException, ValueError) as exc:
        return jsonify({"error": str(exc)}), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
