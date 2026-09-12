import os
import sys
import datetime as dt
import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
FMP_API_KEY = os.environ.get("FMP_API_KEY", "")

# مصادر RSS موثوقة نسبيًا (عناوين عامة للأسواق)
RSS_FEEDS = [
    ("CNBC Markets",     "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839135"),
    ("CNBC Economy",     "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258"),
    ("MarketWatch Mkts", "https://feeds.content.dowjones.io/public/rss/mw_marketpulse"),
    ("MarketWatch Top",  "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
]

# كلمات مفتاحية تُبقي العناوين المؤثّرة على السوق وتحذف الضجيج
KEYWORDS = [
    "fed", "federal reserve", "fomc", "powell", "rate", "rates", "interest",
    "inflation", "cpi", "pce", "gdp", "jobs", "payroll", "unemployment", "labor",
    "earnings", "guidance", "revenue", "profit", "stocks", "market", "markets",
    "s&p", "nasdaq", "dow", "yields", "treasury", "bond", "recession", "economy",
    "gold", "oil", "tariff", "trade", "dollar", "chip", "semiconductor", "ai",
    "nvidia", "apple", "microsoft", "tesla", "amazon", "meta",
]

# دول تهمّنا (تأثير على الأسهم الأمريكية والذهب)
COUNTRIES = {"US", "United States", "EA", "Euro Zone", "GB", "United Kingdom"}


def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("[X] BOT_TOKEN / CHAT_ID غير مضبوطين.")
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": text,
                                     "parse_mode": "HTML", "disable_web_page_preview": True},
                          timeout=15)
        if r.status_code == 200:
            print("[OK] أُرسلت الرسالة.")
            return True
        print(f"[X] رفض تليجرام: {r.status_code} {r.text[:200]}")
        return False
    except Exception as e:
        print(f"[X] خطأ تليجرام: {e}")
        return False


def get_economic_events():
    """أحداث اليوم عالية/متوسطة الأهمية من FMP. يُعيد قائمة أسطر جاهزة."""
    if not FMP_API_KEY:
        return ["⚠️ FMP_API_KEY غير مضبوط — تخطّي التقويم الاقتصادي."]
    today = dt.date.today().isoformat()
    url = ("https://financialmodelingprep.com/api/v3/economic_calendar"
           f"?from={today}&to={today}&apikey={FMP_API_KEY}")
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return [f"⚠️ تعذّر جلب التقويم (HTTP {r.status_code})."]
        data = r.json()
    except Exception as e:
        return [f"⚠️ خطأ جلب التقويم: {e}"]

    out = []
    for ev in data:
        country = str(ev.get("country", ""))
        impact = str(ev.get("impact", "")).lower()
        if country not in COUNTRIES:
            continue
        if impact not in ("high", "medium"):
            continue
        name = ev.get("event", "?")
        time_ = str(ev.get("date", ""))[-8:-3] if ev.get("date") else "--:--"
        prev = ev.get("previous", "")
        fcst = ev.get("estimate", ev.get("forecast", ""))
        dot = "🔴" if impact == "high" else "🟠"
        extra = []
        if fcst not in ("", None):
            extra.append(f"توقّع {fcst}")
        if prev not in ("", None):
            extra.append(f"سابق {prev}")
        tail = f"  ({' · '.join(extra)})" if extra else ""
        out.append(f"{dot} <code>{time_}</code> {country} — {name}{tail}")
    if not out:
        out = ["🟢 لا أحداث اقتصادية كبيرة اليوم."]
    return out[:12]


def get_headlines(limit=8):
    """عناوين مفلترة بكلمات مفتاحية (اقتصاد كلّي/أسواق)، بلا ضجيج، بلا تكرار."""
    try:
        import feedparser
    except Exception:
        return ["⚠️ feedparser غير مثبّت — تخطّي العناوين."]
    seen = set()
    heads = []
    for src, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
        except Exception:
            continue
        for entry in feed.entries[:15]:
            title = entry.get("title", "").strip()
            if not title:
                continue
            low = title.lower()
            # فلترة: يجب أن يحوي العنوان كلمة مفتاحية واحدة على الأقل
            if not any(k in low for k in KEYWORDS):
                continue
            # منع التكرار (عنوان متشابه من مصدرين)
            key = low[:50]
            if key in seen:
                continue
            seen.add(key)
            heads.append(f"• {title}  <i>({src})</i>")
            if len(heads) >= limit:
                break
        if len(heads) >= limit:
            break
    return heads if heads else ["🟢 لا عناوين مؤثّرة بارزة الآن."]


def build_message():
    now = dt.datetime.now(dt.timezone.utc)
    # التقويم الاقتصادي مُعطّل (لا مصدر مجاني موثوق) — عناوين فقط
    heads = get_headlines()
    lines = [
        "🌅 <b>ملخّص ما قبل الافتتاح</b>",
        f"🗓 {now.date()}",
        "",
        "📰 <b>أبرز عناوين الأسواق</b>",
    ]
    lines += heads
    lines += [
        "",
        "━━━━━━━━━━━━━",
        "ℹ️ <i>حقائق وعناوين للوعي فقط — لا تحليل ولا توصية.</i>",
        "⚠️ <i>لا تدع الأخبار تكسر انضباط استراتيجية الزخم الشهرية.</i>",
    ]
    return "\n".join(lines)


def main():
    print("بناء ملخّص ما قبل الافتتاح ...")
    msg = build_message()
    print("\n--- الرسالة ---")
    print(msg.replace("<b>", "").replace("</b>", "").replace("<i>", "")
             .replace("</i>", "").replace("<code>", "").replace("</code>", ""))
    print("---------------\n")
    if "--print_only" in sys.argv:
        print("(--print_only) لم تُرسل.")
        return
    send_telegram(msg)


if __name__ == "__main__":
    main()
