# -*- coding: utf-8 -*-
"""
============================================================================
قائمة الزخم الشهرية -> تليجرام مباشرة
============================================================================
يحسب أعلى N سهمًا بالزخم ويرسل القائمة لبوت تليجرام (نفس بوت MAWJ).
شغّله شهريًا (أو اجدوِله لاحقًا). تصلك القائمة كرسالة عربية أنيقة.

الأسرار من متغيّرات البيئة (لا تُكتب في الكود):
  BOT_TOKEN , CHAT_ID    (نفس قيم بوت MAWJ السابق)

التثبيت:  pip install yfinance pandas numpy requests
التشغيل (ويندوز PowerShell): مرّر الأسرار مؤقتًا في نفس الجلسة ثم شغّل:
  $env:BOT_TOKEN="ضع_التوكن";  $env:CHAT_ID="ضع_المعرّف"
  py -X utf8 momentum_telegram.py --top 10 --lookback 126 --hold "AAPL,MSFT"

ملاحظة صدق: قائمة مبنية على بيانات تاريخية؛ الأداء الماضي لا يضمن المستقبل.
هذا ليس نصيحة مالية — القرار والمسؤولية لك.
============================================================================
"""

import argparse
import os
import sys
import datetime as dt
import numpy as np
import pandas as pd
import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

UNIVERSE = [
    "AAPL","MSFT","AMZN","GOOGL","META","NVDA","JPM","JNJ","V","PG",
    "HD","MA","BAC","DIS","ADBE","CRM","NFLX","XOM","CVX","KO",
    "PEP","WMT","CSCO","INTC","VZ","T","PFE","MRK","ABT","NKE",
    "MCD","COST","TMO","ORCL","ACN","DHR","TXN","QCOM","AMD","HON",
    "UNH","LLY","AVGO","CAT","GS","MS","BA","GE","IBM","MMM",
]


def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("[X] متغيّرا البيئة BOT_TOKEN / CHAT_ID غير مضبوطين.")
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": text,
                                     "parse_mode": "HTML"}, timeout=15)
        if r.status_code == 200:
            print("[OK] أُرسلت الرسالة لتليجرام.")
            return True
        print(f"[X] رفض تليجرام: {r.status_code} {r.text[:200]}")
        return False
    except Exception as e:
        print(f"[X] خطأ اتصال تليجرام: {e}")
        return False


def compute(top, lookback, skip):
    import yfinance as yf
    end = dt.date.today()
    start = end - dt.timedelta(days=500)
    data = yf.download(UNIVERSE, start=str(start), end=str(end),
                       interval="1d", auto_adjust=True, progress=False)
    px = data["Close"] if isinstance(data.columns, pd.MultiIndex) else data
    px = px.dropna(how="all")
    good = [c for c in px.columns if px[c].notna().mean() > 0.9]
    px = px[good].ffill()
    if len(px) < lookback + skip + 1:
        raise RuntimeError(f"بيانات غير كافية ({len(px)} يوم).")
    p_end = px.iloc[-1 - skip]
    p_start = px.iloc[-1 - skip - lookback]
    mom = ((p_end / p_start) - 1.0).dropna().sort_values(ascending=False)
    winners = list(mom.head(top).index)
    return end, winners, mom


def build_message(end, winners, mom, hold, top, lookback):
    weight = 100.0 / len(winners)
    lines = [
        "📊 <b>قائمة الزخم الشهرية</b>",
        f"🗓 {end}",
        f"أعلى {top} أسهم · نافذة {lookback} يوم",
        "",
        "<pre>",
        f"{'#':<3}{'السهم':<7}{'الزخم':>8}{'الوزن':>8}",
        "─" * 26,
    ]
    for i, tk in enumerate(winners, 1):
        lines.append(f"{i:<3}{tk:<7}{mom[tk]*100:>+7.0f}%{weight:>7.0f}%")
    lines.append("</pre>")

    if hold:
        cur = set(h.strip().upper() for h in hold)
        target = set(winners)
        sell = sorted(cur - target)
        buy = sorted(target - cur)
        keep = sorted(cur & target)
        lines += [
            "",
            "🔄 <b>إعادة الموازنة</b>",
            f"🔴 بِيع: <code>{', '.join(sell) if sell else '—'}</code>",
            f"🟢 اشترِ: <code>{', '.join(buy) if buy else '—'}</code>",
            f"⚪️ انتظر: <code>{', '.join(keep) if keep else '—'}</code>",
        ]
        if not sell and not buy:
            lines.append("✅ محفظتك مطابقة — لا تغيير")

    lines += [
        "",
        "⚠️ <i>تنبيه· ليست نصيحة مالية</i>",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="قائمة الزخم -> تليجرام")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--lookback", type=int, default=126)
    ap.add_argument("--skip", type=int, default=21)
    ap.add_argument("--hold", default="")
    ap.add_argument("--print_only", action="store_true", help="اطبع الرسالة بلا إرسال (للتجربة)")
    args = ap.parse_args()

    print(f"حساب قائمة الزخم (top={args.top}, lookback={args.lookback}) ...")
    try:
        end, winners, mom = compute(args.top, args.lookback, args.skip)
    except Exception as e:
        print(f"[X] فشل الحساب: {e}")
        sys.exit(1)

    hold = [h for h in args.hold.split(",") if h.strip()]
    msg = build_message(end, winners, mom, hold, args.top, args.lookback)

    print("\n--- الرسالة ---")
    # اطبع نسخة بلا وسوم HTML للعرض في الطرفية
    print(msg.replace("<b>", "").replace("</b>", ""))
    print("---------------\n")

    # حفظ سجلّ
    pd.DataFrame({"date": [str(end)]*len(winners), "ticker": winners,
                  "momentum_%": [round(mom[t]*100,1) for t in winners]}
                 ).to_csv(f"signal_{end}.csv", index=False, encoding="utf-8-sig")

    if args.print_only:
        print("(--print_only) لم تُرسل. احذف الوسم للإرسال الفعلي.")
        return
    send_telegram(msg)


if __name__ == "__main__":
    main()
