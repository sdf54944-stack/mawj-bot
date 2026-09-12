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
    prices = px.iloc[-1]  # آخر سعر متاح لكل سهم
    return end, winners, mom, prices
 
 
def build_message(end, winners, mom, prices, hold, top, lookback, capital):
    weight = 100.0 / len(winners)
    per_stock = capital * weight / 100.0
    lines = [
        "📊 <b>قائمة الزخم الشهرية</b>",
        f"🗓 {end}  ·  محفظة ${capital:,.0f}  ·  {top} أسهم",
        "",
    ]
    # كتلة monospace: أعمدة مصطفّة (إنجليزية/أرقام فقط لتفادي تشتّت RTL)
    block = []
    block.append(f"{'#':<2} {'SYM':<5}{'MOM':>6}{'PRICE':>9}{'QTY':>5}")
    block.append("─" * 27)
    total_cost = 0.0
    for i, tk in enumerate(winners, 1):
        px_now = float(prices.get(tk, float("nan")))
        ok = px_now == px_now and px_now > 0
        shares = int(per_stock // px_now) if ok else 0
        total_cost += shares * px_now if ok else 0
        pxs = f"{px_now:,.2f}" if ok else "—"
        block.append(f"{i:<2} {tk:<5}{mom[tk]*100:>+5.0f}%{pxs:>9}{shares:>5}")
    lines.append("<pre>" + "\n".join(block) + "</pre>")
    lines.append(f"💰 إجمالي التكلفة التقريبية: ${total_cost:,.0f}")
 
    if hold:
        cur = set(h.strip().upper() for h in hold)
        target = set(winners)
        sell = sorted(cur - target)
        buy = sorted(target - cur)
        keep = sorted(cur & target)
        lines += [
            "",
            "🔄 <b>إعادة الموازنة</b>",
            f"🔴 بِع: <code>{', '.join(sell) if sell else '—'}</code>",
            f"🟢 اشترِ: <code>{', '.join(buy) if buy else '—'}</code>",
            f"⚪️ أبقِ: <code>{', '.join(keep) if keep else '—'}</code>",
        ]
        if not sell and not buy:
            lines.append("✅ محفظتك مطابقة — لا تغيير")
 
    lines += [
        "",
        "💡 <i>السعر للتنفيذ لا للتوقيت — اشترِ بسعر السوق فورًا.</i>",
        "⚠️ <i>تطبيق ورقي أولًا · ليس نصيحة مالية.</i>",
    ]
    return "\n".join(lines)
 
 
def main():
    ap = argparse.ArgumentParser(description="قائمة الزخم -> تليجرام")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--lookback", type=int, default=126)
    ap.add_argument("--skip", type=int, default=21)
    ap.add_argument("--hold", default="")
    ap.add_argument("--capital", type=float, default=10000, help="حجم المحفظة بالدولار لحساب عدد الأسهم")
    ap.add_argument("--print_only", action="store_true", help="اطبع الرسالة بلا إرسال (للتجربة)")
    args = ap.parse_args()
 
    print(f"حساب قائمة الزخم (top={args.top}, lookback={args.lookback}) ...")
    try:
        end, winners, mom, prices = compute(args.top, args.lookback, args.skip)
    except Exception as e:
        print(f"[X] فشل الحساب: {e}")
        sys.exit(1)
 
    hold = [h for h in args.hold.split(",") if h.strip()]
    msg = build_message(end, winners, mom, prices, hold, args.top, args.lookback, args.capital)
 
    print("\n--- الرسالة ---")
    # اطبع نسخة بلا وسوم HTML للعرض في الطرفية
    print(msg.replace("<b>","").replace("</b>","").replace("<pre>","").replace("</pre>","").replace("<code>","").replace("</code>","").replace("<i>","").replace("</i>",""))
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
