"""
live_signal.py — محرّك إشارة BTC الحي (4h عبر Coinbase)
بديل TradingView. يطابق اختبار Coinbase 4h (PF 1.43).
يعمل من GitHub Actions، يحفظ حالته في state_BTC.json
"""

import numpy as np, pandas as pd, json, os, time, urllib.request, urllib.parse

TOKEN   = os.environ["TG_TOKEN"]
CHAT_ID = os.environ["TG_CHAT"]
ASSET   = "BTC"
STATE_FILE = "state_BTC.json"

LEN_BO, ATR_LEN, ATR_MULT = 20, 14, 2.0
R1, R2 = 1.5, 3.0
USE_TREND, ALLOW_SHORT = True, True
T1_FRACTION, BE_AFTER_T1 = 0.50, True


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def fetch_coinbase_4h(product="BTC-USD", days=120):
    """يجلب آخر ~120 يومًا فريم ساعة من Coinbase ويجمّعه 4h. يكفي لـEMA200 على 4h."""
    base = f"https://api.exchange.coinbase.com/products/{product}/candles"
    gran, step = 3600, 3600*300
    t_end = int(pd.Timestamp.now(tz="UTC").timestamp())
    t0 = t_end - days*86400
    rows, s = [], t0
    while s < t_end:
        e = min(s+step, t_end)
        try:
            batch = _get(f"{base}?granularity={gran}&start={s}&end={e}")
            if batch: rows += batch
        except Exception as ex:
            print(f"خطأ جلب: {ex}")
        s = e; time.sleep(0.35)
    if not rows: return None
    h = pd.DataFrame(rows, columns=["t","low","high","open","close","v"]).astype(float)
    h["t"] = pd.to_datetime(h["t"], unit="s")
    h = h.drop_duplicates("t").set_index("t").sort_index()
    df = pd.DataFrame({
        "open": h["open"].resample("4h").first(),
        "high": h["high"].resample("4h").max(),
        "low":  h["low"].resample("4h").min(),
        "close":h["close"].resample("4h").last(),
    }).dropna()
    return df


def atr(df,n):
    h,l,c=df["high"],df["low"],df["close"]; pc=c.shift(1)
    tr=pd.concat([h-l,(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1)
    return tr.rolling(n).mean()


def load_state():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE))
    return {"pos":0,"entry":None,"stop":None,"tp1":None,"tp2":None,
            "t1done":False,"last_bar":None}


def save_state(s):
    json.dump(s, open(STATE_FILE,"w"), ensure_ascii=False, indent=2)


def send(text):
    url=f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data=urllib.parse.urlencode({"chat_id":CHAT_ID,"text":text,
          "parse_mode":"HTML","disable_web_page_preview":"true"}).encode()
    urllib.request.urlopen(urllib.request.Request(url,data=data),timeout=30).read()


def f(x): return f"{x:,.2f}"
def p(x): return f"{'+' if x>=0 else ''}{x:.2f}%"
def pnl(px,e,pos): return (px-e)/e*100 if pos==1 else (e-px)/e*100


def main():
    df = fetch_coinbase_4h("BTC-USD")
    if df is None or len(df) < 210:
        print("بيانات غير كافية"); return
    s = load_state()

    # الشمعة قبل الأخيرة = آخر شمعة 4h مكتملة
    bar = df.iloc[-2]
    bar_time = str(df.index[-2])
    if s.get("last_bar") == bar_time:
        print(f"الشمعة {bar_time} عولجت — تخطّي"); return

    a = atr(df, ATR_LEN).iloc[-2]
    ema = df["close"].ewm(span=200, adjust=False).mean().iloc[-2]
    upBO = df["high"].rolling(LEN_BO).max().shift(1).iloc[-2]
    dnBO = df["low"].rolling(LEN_BO).min().shift(1).iloc[-2]
    hi,lo,cl = bar["high"], bar["low"], bar["close"]

    msg = None

    if s["pos"] != 0:
        pos=s["pos"]; e,stp,tp1,tp2=s["entry"],s["stop"],s["tp1"],s["tp2"]
        hs = lo<=stp if pos==1 else hi>=stp
        h1 = hi>=tp1 if pos==1 else lo<=tp1
        h2 = hi>=tp2 if pos==1 else lo<=tp2
        d = "شراء 🟩" if pos==1 else "بيع 🟥"
        if hs:
            be = s["t1done"] and BE_AFTER_T1
            msg=(("🟨 <b>خروج بالتعادل" if be else "🔴 <b>ضرب وقف الخسارة")+
                 f" — {ASSET}</b>\n🧭 {d}\n✅ الدخول: {f(e)}\n🔻 الخروج: {f(stp)}\n"
                 f"📉 النتيجة: {p(pnl(stp,e,pos))}")
            s={"pos":0,"entry":None,"stop":None,"tp1":None,"tp2":None,"t1done":False}
        elif h2:
            msg=(f"🏁 <b>تحقق الهدف 2 — خروج كامل — {ASSET}</b>\n🧭 {d}\n"
                 f"✅ الدخول: {f(e)}\n🏆 الخروج: {f(tp2)}\n🟢 الربح: {p(pnl(tp2,e,pos))} (3R)")
            s={"pos":0,"entry":None,"stop":None,"tp1":None,"tp2":None,"t1done":False}
        elif h1 and not s["t1done"]:
            s["t1done"]=True
            if BE_AFTER_T1: s["stop"]=e
            msg=(f"🎯 <b>تحقق الهدف 1 — {ASSET}</b>\n🟢 الربح: {p(pnl(tp1,e,pos))}\n"
                 f"🔻 الوقف الجديد: {f(s['stop'])} (تعادل)\n🎯 المتبقي: {f(tp2)}\n💡 خفّف نصف المركز")

    if s["pos"] == 0 and msg is None:
        lg = cl>upBO and ((not USE_TREND) or cl>ema)
        sh = ALLOW_SHORT and cl<dnBO and ((not USE_TREND) or cl<ema)
        if lg or sh:
            pos = 1 if lg else -1
            stp = cl-ATR_MULT*a if pos==1 else cl+ATR_MULT*a
            R = abs(cl-stp)
            tp1 = cl+R1*R if pos==1 else cl-R1*R
            tp2 = cl+R2*R if pos==1 else cl-R2*R
            d = "شراء 🟩" if pos==1 else "بيع 🟥"
            s = {"pos":pos,"entry":cl,"stop":stp,"tp1":tp1,"tp2":tp2,"t1done":False}
            msg=(f"🚨 <b>إشارة دخول — {ASSET} | {d}</b>\n\n✅ الدخول: {f(cl)}\n"
                 f"🎯 الهدف 1: {f(tp1)} (1.5R)\n🎯 الهدف 2: {f(tp2)} (3R)\n"
                 f"🛑 الوقف: {f(stp)}\n⚖️ المخاطرة: {p(-abs(cl-stp)/cl*100)}")

    s["last_bar"] = bar_time
    save_state(s)
    if msg:
        send(msg); print("أُرسلت رسالة")
    else:
        print(f"لا إشارة للشمعة {bar_time}")


if __name__ == "__main__":
    main()
