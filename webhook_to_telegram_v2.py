# -*- coding: utf-8 -*-
# ============================================================================
# MAWJ v2 Webhook -> Telegram
# يستقبل تنبيهات TradingView (JSON من المؤشر) لأحداث: entry / tp1 / tp2 / tp3 / sl
# التشغيل: pip install flask requests  ثم:  python webhook_to_telegram_v2.py
# ============================================================================
from flask import Flask, request
import requests
import json
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "ضع_توكن_البوت_هنا")     # من @BotFather
CHAT_ID   = os.environ.get("CHAT_ID",   "ضع_معرّف_المحادثة_هنا")  # من @userinfobot
SECRET    = os.environ.get("SECRET",    "كلمة_سر_اختَرها")         # لمنع الإشعارات المزيّفة

app = Flask(__name__)


def send(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(
            url,
            json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        return r.status_code == 200
    except Exception as e:
        print("Telegram error:", e)
        return False


def fmt_entry(d):
    side = "🟢 شراء" if d.get("side") == "BUY" else "🔴 بيع"
    gamma_map = {"pos": "جاما موجبة (تثبيت)", "neg": "جاما سالبة (اتجاه)", "na": "—"}
    copp_map = {"up": "صاعد ▲", "down": "هابط ▼", "flat": "محايد"}
    gamma = gamma_map.get(d.get("gamma", "na"), "—")
    copp = copp_map.get(d.get("coppock", "flat"), "—")
    harmonic = d.get("harmonic") or "—"
    return (
        f"<b>⚡ إشارة دخول MAWJ</b>\n"
        f"━━━━━━━━━━━━━\n"
        f"الرمز: <b>{d.get('symbol','?')}</b>  |  الفريم: {d.get('tf','?')}\n"
        f"الاتجاه: <b>{side}</b>\n"
        f"الدخول: <code>{d.get('price','?')}</code>\n"
        f"وقف الخسارة: <code>{d.get('sl','?')}</code>\n"
        f"🎯 TP1: <code>{d.get('tp1','?')}</code>\n"
        f"🎯 TP2: <code>{d.get('tp2','?')}</code>\n"
        f"🎯 TP3: <code>{d.get('tp3','?')}</code>\n"
        f"درجة الثقة: {d.get('score','?')}/5  |  التحيّز: {d.get('bias','?')}\n"
        f"هارمونيك: {harmonic}  |  Coppock: {copp}\n"
        f"نظام GEX: {gamma}\n"
        f"━━━━━━━━━━━━━\n"
        f"⚠️ تنفيذ يدوي — راجع الشارت قبل الدخول"
    )


def fmt_event(d):
    ev = d.get("event")
    labels = {
        "tp1": "🎯 تحقّق الهدف الأول TP1",
        "tp2": "🎯 تحقّق الهدف الثاني TP2",
        "tp3": "🏁 تحقّق الهدف الثالث TP3",
        "sl":  "🛑 ضرب وقف الخسارة SL",
    }
    title = labels.get(ev, "تحديث")
    pct = d.get("pct", "?")
    sign = "+" if isinstance(pct, (int, float)) and pct >= 0 else ""
    return (
        f"<b>{title}</b>\n"
        f"الرمز: <b>{d.get('symbol','?')}</b>  |  الفريم: {d.get('tf','?')}\n"
        f"السعر: <code>{d.get('price','?')}</code>  ({sign}{pct}%)"
    )


@app.route("/hook", methods=["POST"])
def hook():
    if request.args.get("key") != SECRET:
        return "forbidden", 403

    raw = request.data.decode("utf-8").strip()
    try:
        d = json.loads(raw)
    except Exception:
        send(f"⚡ MAWJ:\n{raw}")
        return "ok-text", 200

    if d.get("event") == "entry":
        send(fmt_entry(d))
    elif d.get("event") in ("tp1", "tp2", "tp3", "sl"):
        send(fmt_event(d))
    else:
        send(f"⚡ MAWJ:\n{json.dumps(d, ensure_ascii=False)}")
    return "ok", 200


@app.route("/", methods=["GET"])
def health():
    return "MAWJ v2 webhook alive", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
