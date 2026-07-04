import os
import sqlite3
import threading
import requests
import csv
import io
import time
from datetime import datetime
import flet as ft

# ── BHOOVALAYA CONSTANTS ───────────────────────────────────────────────────────
AKSHARA_VALS = {
    'अ': 1, 'आ': 2, 'इ': 3, 'ई': 4, 'उ': 5, 'ऊ': 6, 'ए': 7, 'ऐ': 8, 'ओ': 9, 'औ': 10,
    'क': 11, 'ख': 12, 'ग': 13, 'घ': 14, 'ङ': 15, 'च': 16, 'छ': 17, 'ज': 18, 'झ': 19, 'ञ': 20,
    'ट': 21, 'ठ': 22, 'ड': 23, 'ढ': 24, 'ण': 25, 'त': 26, 'थ': 27, 'द': 28, 'ध': 29, 'न': 30,
    'प': 31, 'फ': 32, 'ब': 33, 'भ': 34, 'म': 35, 'य': 36, 'र': 37, 'ल': 38, 'व': 39, 'श': 40,
    'ष': 41, 'स': 42, 'ह': 43, 'ि': 2, 'ा': 2, 'े': 7, 'ै': 8, 'ो': 9, 'ौ': 10, '्': 0, 'ं': 1
}

SUTRA_MAP = {
    0: "अनंत (Ananta)", 1: "शक्ति (Shakti)", 2: "ज्ञान (Gnana)",
    3: "धर्म (Dharma)", 4: "वैराग्य (Vairagya)", 5: "ऐश्वर्य (Aishwarya)",
    6: "यश (Yashas)", 7: "श्री (Shree)", 8: "वीर्य (Veerya)"
}

# ── FINANCIAL ASTROLOGY ORACLE ─────────────────────────────────────────────────
GRAHA_DATA = {
    0: {"graha": "मंगल (Mars)", "symbol": "♂", "nature": "उग्र / Aggressive",
        "market_bias": "BULLISH", "bias_hi": "तेजी", "strength": 4,
        "sectors": "धातु, रक्षा, ऊर्जा / Metals · Defence · Energy",
        "trend": "Short-term sharp upward momentum. High volatility possible.",
        "trend_hi": "अल्पकालिक तीव्र ऊपरी गति। उच्च अस्थिरता संभव।",
        "holding": "1–7 दिन / Intraday to Weekly",
        "caution": "Sudden reversal risk after spike. Use strict stop-loss.",
        "nakshatra": "मृगशिरा, चित्रा, धनिष्ठा", "favorable_days": "मंगलवार (Tuesday)"},
    1: {"graha": "सूर्य (Sun)", "symbol": "☀", "nature": "सात्विक / Sattvic",
        "market_bias": "BULLISH", "bias_hi": "तेजी", "strength": 5,
        "sectors": "PSU, सरकारी, ऊर्जा / Govt PSU · Energy · Gold",
        "trend": "Strong steady uptrend. Leadership stocks outperform.",
        "trend_hi": "मजबूत स्थिर ऊपरी रुझान। नेतृत्व स्टॉक बेहतर।",
        "holding": "1–4 सप्ताह / Weekly to Monthly",
        "caution": "Avoid entry on Sunday. Best entry Monday morning.",
        "nakshatra": "कृत्तिका, उत्तराफाल्गुनी, उत्तराषाढ़ा", "favorable_days": "रविवार (Sunday)"},
    2: {"graha": "चंद्र (Moon)", "symbol": "☽", "nature": "चंचल / Volatile",
        "market_bias": "NEUTRAL-VOLATILE", "bias_hi": "अस्थिर", "strength": 2,
        "sectors": "FMCG, डेयरी, खुदरा / FMCG · Dairy · Retail",
        "trend": "Erratic short-term moves. Sentiment-driven. Watch lunar phase.",
        "trend_hi": "अनिश्चित अल्पकालिक चाल। भावना-आधारित।",
        "holding": "1–3 दिन / Intraday to 3 days",
        "caution": "Full moon / new moon weeks highly volatile. Avoid overnight.",
        "nakshatra": "रोहिणी, हस्त, श्रवण", "favorable_days": "सोमवार (Monday)"},
    3: {"graha": "गुरु (Jupiter)", "symbol": "♃", "nature": "शुभ / Auspicious",
        "market_bias": "STRONGLY BULLISH", "bias_hi": "प्रबल तेजी", "strength": 5,
        "sectors": "बैंक, शिक्षा, विस्तार / Banking · Education · Expansion",
        "trend": "Sustained bull run. Fundamentally strong companies shine.",
        "trend_hi": "दीर्घकालिक तेजी। मौलिक रूप से मजबूत कंपनियां चमकती हैं।",
        "holding": "1–6 माह / Monthly to Quarterly",
        "caution": "Jupiter retrograde periods may pause the rally temporarily.",
        "nakshatra": "पुनर्वसु, विशाखा, पूर्वाभाद्रपद", "favorable_days": "गुरुवार (Thursday)"},
    4: {"graha": "राहु (Rahu)", "symbol": "☊", "nature": "मायावी / Illusory",
        "market_bias": "SPECULATIVE", "bias_hi": "सट्टा / जोखिम", "strength": 3,
        "sectors": "तकनीक, फार्मा / Technology · Pharma · Foreign Capital",
        "trend": "Sudden unexpected gains OR losses. News-driven sharp moves.",
        "trend_hi": "अचानक अप्रत्याशित लाभ या हानि। समाचार-आधारित।",
        "holding": "सावधानी से / With Caution",
        "caution": "High risk. Avoid leveraged positions. Magnifies wins and losses.",
        "nakshatra": "आर्द्रा, स्वाति, शतभिषा", "favorable_days": "शनिवार (Saturday)"},
    5: {"graha": "बुध (Mercury)", "symbol": "☿", "nature": "व्यापारिक / Commercial",
        "market_bias": "BULLISH", "bias_hi": "तेजी", "strength": 4,
        "sectors": "IT, दूरसंचार, मीडिया / IT · Telecom · Trade · Media",
        "trend": "Gradual uptrend with minor corrections. Good for swing trades.",
        "trend_hi": "छोटे सुधारों के साथ क्रमिक ऊपरी रुझान।",
        "holding": "1–3 सप्ताह / Weekly to Bi-weekly",
        "caution": "Mercury retrograde (3x/year) causes confusion. Avoid new entries.",
        "nakshatra": "आश्लेषा, ज्येष्ठा, रेवती", "favorable_days": "बुधवार (Wednesday)"},
    6: {"graha": "शुक्र (Venus)", "symbol": "♀", "nature": "ऐश्वर्यशाली / Prosperous",
        "market_bias": "BULLISH", "bias_hi": "तेजी", "strength": 4,
        "sectors": "FMCG, विलासिता, होटल / FMCG · Luxury · Hotels · Entertainment",
        "trend": "Smooth upward movement. Consumer demand drives price.",
        "trend_hi": "सुचारू ऊपरी गति। उपभोक्ता मांग मूल्य बढ़ाती है।",
        "holding": "2–8 सप्ताह / Bi-weekly to 2 months",
        "caution": "Overvaluation risk at peaks. Book partial profits at highs.",
        "nakshatra": "भरणी, पूर्वाफाल्गुनी, पूर्वाषाढ़ा", "favorable_days": "शुक्रवार (Friday)"},
    7: {"graha": "केतु (Ketu)", "symbol": "☋", "nature": "रहस्यमय / Mystical",
        "market_bias": "BEARISH-CAUTION", "bias_hi": "मंदी / सावधानी", "strength": 2,
        "sectors": "पुरानी अर्थव्यवस्था / Old Economy · Exit zones",
        "trend": "Sudden reversals and corrections likely. Wait and watch.",
        "trend_hi": "अचानक उलटफेर और सुधार संभव। प्रतीक्षा करें।",
        "holding": "बाहर रहें / Avoid Fresh Entry",
        "caution": "Ketu causes unexpected losses. Reduce position size.",
        "nakshatra": "अश्विनी, मघा, मूल", "favorable_days": "मंगलवार (Tuesday)"},
    8: {"graha": "शनि (Saturn)", "symbol": "♄", "nature": "कर्मफल / Karmic",
        "market_bias": "SLOW BULLISH", "bias_hi": "धीमी तेजी", "strength": 3,
        "sectors": "इन्फ्रा, धातु, निर्माण / Infra · Metals · Coal · Construction",
        "trend": "Slow but steady long-term accumulation zone. Patience rewarded.",
        "trend_hi": "धीमा लेकिन स्थिर दीर्घकालिक संचय क्षेत्र।",
        "holding": "3–12 माह / Quarterly to Yearly",
        "caution": "Short-term pain is common. Do not panic sell. SIP approach best.",
        "nakshatra": "पुष्य, अनुराधा, उत्तराभाद्रपद", "favorable_days": "शनिवार (Saturday)"},
}

NAKSHATRA_LIST = [
    "अश्विनी", "भरणी", "कृत्तिका", "रोहिणी", "मृगशिरा", "आर्द्रा",
    "पुनर्वसु", "पुष्य", "आश्लेषा", "मघा", "पूर्वाफाल्गुनी", "उत्तराफाल्गुनी",
    "हस्त", "चित्रा", "स्वाति", "विशाखा", "अनुराधा", "ज्येष्ठा",
    "मूल", "पूर्वाषाढ़ा", "उत्तराषाढ़ा", "श्रवण", "धनिष्ठा", "शतभिषा",
    "पूर्वाभाद्रपद", "उत्तराभाद्रपद", "रेवती"
]

STRENGTH_BARS = {1: "▓░░░░", 2: "▓▓░░░", 3: "▓▓▓░░", 4: "▓▓▓▓░", 5: "▓▓▓▓▓"}
BIAS_ARROW = {
    "STRONGLY BULLISH":  "🚀 ↑↑↑",
    "BULLISH":           "📈 ↑↑",
    "SLOW BULLISH":      "🐢 ↑",
    "NEUTRAL-VOLATILE":  "〰️ ↕",
    "SPECULATIVE":       "🎲 ?↕",
    "BEARISH-CAUTION":   "📉 ↓↓",
}

CURATED_HINDI_NAMES = {
    "SBIN": "भारतीय स्टेट बैंक", "HDFCBANK": "एचडीएफसी बैंक",
    "ICICIBANK": "आईसीआईसीआई बैंक", "AXISBANK": "एक्सिस बैंक",
    "KOTAKBANK": "कोटक महिंद्रा बैंक", "BANKBARODA": "बैंक ऑफ बड़ौदा",
    "PNB": "पंजाब नेशनल बैंक", "CANBK": "केनरा बैंक",
    "UNIONBANK": "यूनियन बैंक ऑफ इंडिया", "YESBANK": "यस बैंक",
    "RELIANCE": "रिलायंस इंडस्ट्रीज", "ONGC": "तेल और प्राकृतिक गैस निगम",
    "IOC": "इंडियन ऑयल कॉर्पोरेशन", "BPCL": "भारत पेट्रोलियम कॉर्पोरेशन",
    "GAIL": "गेल इंडिया", "NTPC": "राष्ट्रीय ताप विद्युत निगम",
    "POWERGRID": "पावर ग्रिड कॉर्पोरेशन", "ADANIGREEN": "अदानी ग्रीन एनर्जी",
    "ADANIPORTS": "अदानी पोर्ट्स", "ADANIENT": "अदानी एंटरप्राइजेज",
    "TCS": "टाटा कंसल्टेंसी सर्विसेज", "INFY": "इन्फोसिस",
    "WIPRO": "विप्रो", "HCLTECH": "एचसीएल टेक्नोलॉजीज",
    "TECHM": "टेक महिंद्रा", "MARUTI": "मारुति सुजुकी इंडिया",
    "TATAMOTORS": "टाटा मोटर्स", "M&M": "महिंद्रा एंड महिंद्रा",
    "BAJAJ-AUTO": "बजाज ऑटो", "HEROMOTOCO": "हीरो मोटोकॉर्प",
    "TATASTEEL": "टाटा स्टील", "JSWSTEEL": "जेएसडब्ल्यू स्टील",
    "HINDALCO": "हिंडाल्को इंडस्ट्रीज", "COALINDIA": "कोल इंडिया",
    "SAIL": "स्टील अथॉरिटी ऑफ इंडिया", "NMDC": "राष्ट्रीय खनिज विकास निगम",
    "SUNPHARMA": "सन फार्मास्युटिकल", "DRREDDY": "डॉ रेड्डीज लेबोरेटरीज",
    "CIPLA": "सिप्ला", "DIVISLAB": "दिविस लेबोरेटरीज",
    "BIOCON": "बायोकॉन", "LUPIN": "ल्यूपिन",
    "HINDUNILVR": "हिंदुस्तान यूनिलीवर", "ITC": "आईटीसी",
    "NESTLEIND": "नेस्ले इंडिया", "BRITANNIA": "ब्रिटानिया इंडस्ट्रीज",
    "DABUR": "डाबर इंडिया", "MARICO": "मेरिको",
    "LT": "लार्सन एंड टुब्रो", "ULTRACEMCO": "अल्ट्राटेक सीमेंट",
    "GRASIM": "ग्रासिम इंडस्ट्रीज", "AMBUJACEM": "अंबुजा सीमेंट",
    "ACC": "एसोसिएटेड सीमेंट कंपनी", "DLF": "डीएलएफ",
    "BHARTIARTL": "भारती एयरटेल", "ZEEL": "जी एंटरटेनमेंट",
    "DMART": "एवेन्यू सुपरमार्ट्स", "ZOMATO": "जोमैटो",
    "PAYTM": "वन97 कम्युनिकेशंस", "NYKAA": "एफएसएन ई-कॉमर्स",
    "ASIANPAINT": "एशियन पेंट्स", "TITAN": "टाइटन कंपनी",
    "HAVELLS": "हैवेल्स इंडिया", "IRCTC": "भारतीय रेलवे खानपान एवं पर्यटन",
    "HAL": "हिंदुस्तान एयरोनॉटिक्स", "BEL": "भारत इलेक्ट्रॉनिक्स",
    "BHEL": "भारत हेवी इलेक्ट्रिकल्स", "LICI": "भारतीय जीवन बीमा निगम",
    "BAJFINANCE": "बजाज फाइनेंस", "BAJAJFINSV": "बजाज फिनसर्व",
    "HDFCLIFE": "एचडीएफसी लाइफ इंश्योरेंस", "SBILIFE": "एसबीआई लाइफ इंश्योरेंस",
    "APOLLOHOSP": "अपोलो हॉस्पिटल्स", "FORTIS": "फोर्टिस हेल्थकेयर",
    "TATAPOWER": "टाटा पावर", "ADANIPOWER": "अदानी पावर",
    "CONCOR": "कंटेनर कॉर्पोरेशन ऑफ इंडिया", "VEDL": "वेदांता",
    "HINDPETRO": "हिंदुस्तान पेट्रोलियम", "PETRONET": "पेट्रोनेट एलएनजी",
    "IGL": "इंद्रप्रस्थ गैस", "MGL": "महानगर गैस",
}

WORD_TRANSLATIONS = {
    "LIMITED": "लिमिटेड", "LTD": "लिमिटेड", "INDUSTRIES": "इंडस्ट्रीज",
    "INDUSTRY": "उद्योग", "BANK": "बैंक", "STEEL": "स्टील",
    "INFRASTRUCTURE": "इन्फ्रास्ट्रक्चर", "FINANCE": "फाइनेंस",
    "INDIA": "इंडिया", "INDIAN": "इंडियन", "ENTERPRISES": "एंटरप्राइजेज",
    "POWER": "पावर", "ENERGY": "एनर्जी", "MOTORS": "मोटर्स", "MOTOR": "मोटर",
    "TECHNOLOGIES": "टेक्नोलॉजीज", "TECHNOLOGY": "टेक्नोलॉजी",
    "SERVICES": "सर्विसेज", "CORPORATION": "कॉर्पोरेशन",
    "NATIONAL": "नेशनल", "INTERNATIONAL": "इंटरनेशनल",
    "PHARMA": "फार्मा", "PHARMACEUTICALS": "फार्मास्युटिकल्स",
    "CHEMICALS": "केमिकल्स", "CEMENT": "सीमेंट",
    "SOLUTIONS": "सॉल्यूशंस", "SYSTEMS": "सिस्टम्स",
    "PRODUCTS": "प्रोडक्ट्स", "HOLDINGS": "होल्डिंग्स",
    "CAPITAL": "कैपिटल", "INSURANCE": "इंश्योरेंस",
    "HOUSING": "हाउसिंग", "REALTY": "रियल्टी",
    "MEDIA": "मीडिया", "TELECOM": "टेलीकॉम",
    "LABORATORIES": "लेबोरेटरीज", "HEALTHCARE": "हेल्थकेयर",
    "HOSPITAL": "हॉस्पिटल", "HOSPITALS": "हॉस्पिटल्स",
    "PETROLEUM": "पेट्रोलियम", "OIL": "ऑयल", "GAS": "गैस",
    "SOLAR": "सोलर", "RENEWABLE": "रिन्यूएबल",
    "AUTO": "ऑटो", "AUTOMOBILE": "ऑटोमोबाइल",
    "PAINTS": "पेंट्स", "ENGINEERING": "इंजीनियरिंग",
    "ELECTRIC": "इलेक्ट्रिक", "ELECTRONICS": "इलेक्ट्रॉनिक्स",
    "FOODS": "फूड्स", "BEVERAGES": "बेवरेजेज",
    "TEXTILE": "टेक्सटाइल", "FERTILIZERS": "फर्टिलाइजर्स",
    "CONSTRUCTION": "कंस्ट्रक्शन", "INVESTMENTS": "इन्वेस्टमेंट्स",
    "SECURITIES": "सिक्योरिटीज", "TRADING": "ट्रेडिंग",
    "EXPORTS": "एक्सपोर्ट्स", "GROUP": "ग्रुप",
    "GLOBAL": "ग्लोबल", "COMPANY": "कंपनी",
    "AND": "एंड", "&": "एंड",
}

PHONETIC_RULES = {
    'A': 'ए', 'B': 'ब', 'C': 'क', 'D': 'ड', 'E': 'इ', 'F': 'फ', 'G': 'ग', 'H': 'ह',
    'I': 'इ', 'J': 'ज', 'K': 'क', 'L': 'ल', 'M': 'म', 'N': 'न', 'O': 'ओ', 'P': 'प',
    'Q': 'क', 'R': 'र', 'S': 'स', 'T': 'ट', 'U': 'य', 'V': 'व', 'W': 'व',
    'X': 'क्स', 'Y': 'य', 'Z': 'ज'
}

NSE_CSV_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"


# ── HELPER FUNCTIONS ───────────────────────────────────────────────────────────

def parse_date_safely(date_str):
    if not date_str:
        return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%b-%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def google_translate(text):
    try:
        url = ("https://translate.googleapis.com/translate_a/single"
               f"?client=gtx&sl=en&tl=hi&dt=t&q={requests.utils.quote(text)}")
        resp = requests.get(url, timeout=6)
        resp.raise_for_status()
        data = resp.json()
        translated = "".join(part[0] for part in data[0] if part[0])
        if translated and translated != text:
            return translated.strip()
    except Exception:
        pass
    return None


def google_transliterate_word(word):
    try:
        url = (f"https://inputtools.google.com/request"
               f"?text={word}&ime=transliteration_en_hi&num=1")
        resp = requests.get(url, timeout=5).json()
        if resp[0] == "SUCCESS":
            return resp[1][0][1][0]
    except Exception:
        pass
    return "".join(PHONETIC_RULES.get(c, '') for c in word.upper()) or word


def word_translate(eng_name):
    words = eng_name.upper().split()
    result = []
    for word in words:
        clean = word.strip("&.,()-/")
        if clean in WORD_TRANSLATIONS:
            result.append(WORD_TRANSLATIONS[clean])
        else:
            result.append(google_transliterate_word(clean))
    return " ".join(result)


def get_hindi_name(symbol, eng_name):
    if symbol in CURATED_HINDI_NAMES:
        return CURATED_HINDI_NAMES[symbol], "curated"
    translated = google_translate(eng_name)
    if translated:
        time.sleep(0.2)
        return translated, "google_translate"
    return word_translate(eng_name), "word_translate"


def compute_akshara(hindi_name):
    a_sum = 0
    steps = []
    for char in hindi_name:
        w = AKSHARA_VALS.get(char, 0)
        a_sum += w
        if w > 0 or char == '्':
            steps.append(f"{char}({w})")
        elif char == " ":
            steps.append("[Space]")
    return a_sum, " + ".join(steps)


def fetch_nse_equity_list():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    resp = requests.get(NSE_CSV_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    text = resp.content.decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    return [
        {k.strip().upper(): (v.strip() if v else "") for k, v in row.items()}
        for row in reader
    ]


def get_astro_oracle(akshara_sum, temporal_val, listing_date):
    total_vib  = akshara_sum + temporal_val
    sutra_idx  = total_vib % 9
    navaank    = (akshara_sum % 9) or 9
    graha_idx  = (navaank - 1) % 9
    g          = GRAHA_DATA[graha_idx]
    today      = datetime.now()
    day_num    = today.timetuple().tm_yday
    nakshatra  = NAKSHATRA_LIST[day_num % 27]
    weekday    = ["सोमवार","मंगलवार","बुधवार","गुरुवार",
                  "शुक्रवार","शनिवार","रविवार"][today.weekday()]
    if listing_date:
        birth_day  = listing_date.timetuple().tm_yday
        tara_count = ((day_num - birth_day) % 27) + 1
        tara_names = ["जन्म","सम्पत","विपत्","क्षेम","प्रत्यरि",
                      "साधक","वध","मित्र","परम मित्र"]
        tara_name  = tara_names[(tara_count - 1) % 9]
        tara_good  = tara_count % 9 in (2, 4, 6, 8, 0)
        tara_str   = f"{tara_name} (#{tara_count % 9 or 9}) {'✅ शुभ' if tara_good else '⚠️ अशुभ'}"
    else:
        tara_str   = "N/A"
        tara_good  = False
    today_favorable = weekday in g["favorable_days"]
    day_mark   = "✅ आज शुभ दिन!" if today_favorable else "⚪ सामान्य दिन"
    strength_bar = STRENGTH_BARS.get(g["strength"], "░░░░░")
    arrow        = BIAS_ARROW.get(g["market_bias"], "—")
    sutra_name   = SUTRA_MAP.get(sutra_idx, "अज्ञात")
    SEP = "─" * 46
    return "\n".join([
        SEP,
        f"✨ सूत्र फल: {sutra_name}",
        f"🪐 ग्रह: {g['graha']} {g['symbol']}  |  {g['nature']}",
        SEP,
        "📈 MARKET MOVEMENT FORECAST",
        f"   दिशा    : {arrow}  {g['market_bias']} ({g['bias_hi']})",
        f"   शक्ति   : {strength_bar}  ({g['strength']}/5)",
        f"   क्षेत्र : {g['sectors']}",
        SEP,
        "🔭 PRICE TREND",
        f"   {g['trend']}",
        f"   {g['trend_hi']}",
        f"   ⏳ होल्डिंग : {g['holding']}",
        f"   ⚠️  सावधानी : {g['caution']}",
        SEP,
        f"🌟 VEDIC TIMING  ({weekday}, {today.strftime('%d-%m-%Y')})",
        f"   नक्षत्र  : {nakshatra}",
        f"   तारा बल : {tara_str}",
        f"   शुभ नक्षत्र : {g['nakshatra']}",
        f"   शुभ वार    : {g['favorable_days']}  {day_mark}",
        SEP,
        "⚖️  For study & research only. Not SEBI advice.",
        "   केवल शोध उद्देश्य। SEBI पंजीकृत सलाह नहीं।",
    ])


# ── MAIN APP ───────────────────────────────────────────────────────────────────

def main(page: ft.Page):
    page.title = "BHOOVALAYA PHONETIC ENGINE"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = "#FFFFFF"
    page.padding = 10
    page.scroll = ft.ScrollMode.ADAPTIVE

    app_storage = os.getenv("FLET_APP_STORAGE_DATA", ".")
    db_path = os.path.join(app_storage, "bhuvalaya_oracle.db")

    # ── DB INIT ────────────────────────────────────────────────────────────────
    def init_db():
        conn = sqlite3.connect(db_path)
        conn.execute('''CREATE TABLE IF NOT EXISTS stocks (
                        symbol TEXT PRIMARY KEY, eng_name TEXT, hindi_name TEXT,
                        listing_date TEXT, akshara_sum INTEGER, breakdown TEXT,
                        name_source TEXT)''')
        conn.commit()
        conn.close()

    def db_is_populated():
        try:
            conn = sqlite3.connect(db_path)
            count = conn.cursor().execute("SELECT COUNT(*) FROM stocks").fetchone()[0]
            conn.close()
            return count > 10
        except Exception:
            return False

    init_db()

    # ── WIDGETS ────────────────────────────────────────────────────────────────
    search_box   = ft.TextField(label="Enter Stock Name or Symbol",
                                value="RELIANCE", expand=True)
    output_text  = ft.Text(value="", size=14, selectable=True,
                           font_family="monospace")
    progress_bar = ft.ProgressBar(visible=False, color="blue", value=0)
    status_text  = ft.Text(value="", size=13, color="blue", italic=True)

    input_sym    = ft.TextField(label="Symbol ID")
    input_eng    = ft.TextField(label="English Name")
    input_hindi  = ft.TextField(label="Hindi Name")
    input_date   = ft.TextField(label="Listing Date (DD-MM-YYYY)")
    crud_status  = ft.Text(value="Status: Idle", italic=True, color="gray")

    data_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Symbol")),
            ft.DataColumn(ft.Text("Hindi Name")),
        ],
        rows=[]
    )

    # ── TABLE REFRESH ──────────────────────────────────────────────────────────
    def refresh_table():
        data_table.rows.clear()
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT symbol, hindi_name FROM stocks ORDER BY symbol ASC LIMIT 50")
            for row in cursor.fetchall():
                def make_handler(sym=row[0]):
                    return lambda e: populate_fields(sym)
                data_table.rows.append(ft.DataRow(
                    cells=[ft.DataCell(ft.Text(row[0])),
                           ft.DataCell(ft.Text(row[1]))],
                    on_select_changed=make_handler()
                ))
            conn.close()
            page.update()
        except Exception as ex:
            print("Table refresh warning:", ex)

    def populate_fields(symbol):
        conn = sqlite3.connect(db_path)
        res = conn.cursor().execute(
            "SELECT * FROM stocks WHERE symbol = ?", (symbol,)).fetchone()
        conn.close()
        if res:
            input_sym.value = res[0]
            input_sym.disabled = True
            input_eng.value   = res[1]
            input_hindi.value = res[2]
            input_date.value  = res[3]
            crud_status.value = f"Selected: {res[0]}"
            page.update()

    # ── SEARCH ─────────────────────────────────────────────────────────────────
    def perform_search(e):
        query = search_box.value.strip().upper()
        if not query:
            return
        if not db_is_populated():
            output_text.value = (
                "⚠️  Database is empty!\n"
                "Please tap 'Build Database' button first.\n"
                "It will download and process all NSE stocks.\n"
                "This takes 5–15 minutes on first use."
            )
            page.update()
            return

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM stocks WHERE symbol LIKE ? OR eng_name LIKE ?",
            (f'%{query}%', f'%{query}%'))
        res = cursor.fetchone()
        conn.close()

        if res:
            sym, eng, hindi, l_date_str, a_sum, breakdown, *_ = res
            today  = datetime.now()
            l_date = parse_date_safely(l_date_str)
            if l_date:
                days_diff = (today - l_date).days
                date_val  = days_diff % 730
            else:
                days_diff, date_val = 0, 0

            total_vib   = a_sum + date_val
            astro_report = get_astro_oracle(a_sum, date_val, l_date)

            output_text.value = "\n".join([
                f"📊 SYMBOL     : {sym}",
                f"🏢 COMPANY    : {eng}",
                f"🕉️  HINDI NAME : {hindi}",
                f"📅 LISTED     : {l_date_str}",
                "─" * 46,
                "🧮 AKSHARA CALCULATION:",
                f"   {breakdown}",
                f"   कुल अक्षर भार = {a_sum}",
                "",
                "⏳ TEMPORAL VIBRATION:",
                f"   Days elapsed : {days_diff}",
                f"   Temporal Mod : {date_val}",
                "",
                f"🌀 COMBINED VIBRATION = {a_sum} + {date_val} = {total_vib}",
                f"   नवांक (Navaank) = {(a_sum % 9) or 9}",
                "",
                astro_report,
            ])
        else:
            output_text.value = (
                f"'{query}' not found in database.\n"
                "Try the full company name or rebuild the database."
            )
        page.update()

    # ── DATABASE BUILD (runs on first launch or on demand) ────────────────────
    def build_database_logic(on_complete=None):
        try:
            status_text.value = "📡 Connecting to NSE India..."
            progress_bar.visible = True
            progress_bar.value = 0
            page.update()

            rows = fetch_nse_equity_list()
            total = len(rows)
            conn  = sqlite3.connect(db_path)
            cursor = conn.cursor()
            success = 0

            for idx, row in enumerate(rows):
                sym      = str(row.get('SYMBOL', '')).strip()
                eng_name = str(row.get('NAME OF COMPANY',
                                row.get('COMPANY NAME', ''))).strip()
                l_date   = str(row.get('DATE OF LISTING', '01-01-2000')).strip()
                if not sym or sym.lower() == 'symbol':
                    continue

                hindi_name, source = get_hindi_name(sym, eng_name)
                a_sum, breakdown   = compute_akshara(hindi_name)

                cursor.execute(
                    "INSERT OR REPLACE INTO stocks VALUES (?,?,?,?,?,?,?)",
                    (sym, eng_name, hindi_name, l_date, a_sum, breakdown, source))
                success += 1

                if idx % 25 == 0:
                    conn.commit()
                    pct = idx / total
                    progress_bar.value = pct
                    status_text.value  = (
                        f"🔄 Processing {idx}/{total} stocks... "
                        f"({int(pct*100)}%)\n"
                        f"   {sym} → {hindi_name}"
                    )
                    page.update()

            conn.commit()
            conn.close()
            progress_bar.value   = 1.0
            status_text.value    = (
                f"✅ Database built! {success} stocks processed.\n"
                "Now search any stock symbol or name."
            )
            page.update()
            refresh_table()
            if on_complete:
                on_complete()
        except Exception as ex:
            progress_bar.visible = False
            status_text.value    = (
                f"❌ Build Error: {str(ex)}\n"
                "Check internet connection and try again."
            )
            page.update()

    def start_build(e):
        status_text.value    = "Starting database build..."
        progress_bar.visible = True
        page.update()
        threading.Thread(
            target=build_database_logic, daemon=True).start()

    # ── FIRST LAUNCH AUTO-BUILD ────────────────────────────────────────────────
    def check_and_auto_build():
        if not db_is_populated():
            output_text.value = (
                "🙏 Welcome to Bhoovalaya Phonetic Engine!\n\n"
                "📥 First launch detected.\n"
                "Building NSE stock database automatically...\n"
                "Please keep app open. Takes 5–15 minutes.\n\n"
                "Progress shown below ↓"
            )
            page.update()
            build_database_logic()
        else:
            count = sqlite3.connect(db_path).execute(
                "SELECT COUNT(*) FROM stocks").fetchone()[0]
            output_text.value = (
                f"🙏 Welcome! Database ready with {count} stocks.\n"
                "Search any NSE stock symbol above."
            )
            page.update()
        refresh_table()

    # ── CRUD ───────────────────────────────────────────────────────────────────
    def db_add(e):
        sym   = input_sym.value.upper()
        eng   = input_eng.value
        hindi = input_hindi.value
        l_date = input_date.value
        if not (sym and eng and hindi):
            return
        a_sum, breakdown = compute_akshara(hindi)
        try:
            conn = sqlite3.connect(db_path)
            conn.cursor().execute(
                "INSERT INTO stocks VALUES (?,?,?,?,?,?,?)",
                (sym, eng, hindi, l_date or "01-01-2000",
                 a_sum, breakdown, "manual"))
            conn.commit()
            conn.close()
            crud_status.value = "✅ Record added!"
            clear_fields(None)
            refresh_table()
        except Exception as ex:
            crud_status.value = str(ex)
        page.update()

    def db_edit(e):
        sym   = input_sym.value
        eng   = input_eng.value
        hindi = input_hindi.value
        l_date = input_date.value
        if not sym:
            return
        a_sum, breakdown = compute_akshara(hindi)
        try:
            conn = sqlite3.connect(db_path)
            conn.cursor().execute(
                "UPDATE stocks SET eng_name=?, hindi_name=?, listing_date=?,"
                " akshara_sum=?, breakdown=? WHERE symbol=?",
                (eng, hindi, l_date, a_sum, breakdown, sym))
            conn.commit()
            conn.close()
            crud_status.value = "✅ Record updated!"
            clear_fields(None)
            refresh_table()
        except Exception as ex:
            crud_status.value = str(ex)
        page.update()

    def clear_fields(e):
        input_sym.disabled = False
        input_sym.value = input_eng.value = input_hindi.value = input_date.value = ""
        crud_status.value = "Form cleared."
        page.update()

    # ── LAYOUT ─────────────────────────────────────────────────────────────────
    engine_view = ft.Column([
        ft.Text("🔮 BHOOVALAYA ORACLE ENGINE", size=20, weight="bold"),
        ft.Row([
            search_box,
            ft.ElevatedButton("Search", on_click=perform_search,
                              bgcolor="green", color="white")
        ]),
        ft.ElevatedButton(
            "🔄 Build / Rebuild Database",
            on_click=start_build, bgcolor="red", color="white"),
        status_text,
        progress_bar,
        ft.Container(
            content=output_text,
            border=ft.Border(
                top=ft.BorderSide(1, "gray"), bottom=ft.BorderSide(1, "gray"),
                left=ft.BorderSide(1, "gray"), right=ft.BorderSide(1, "gray")
            ),
            padding=15, border_radius=10, bgcolor="#F5F5F5", expand=True
        )
    ], expand=True, scroll="adaptive")

    crud_view = ft.Row([
        ft.Column([
            ft.Text("Records (tap to select)"),
            data_table
        ], scroll="always", expand=True),
        ft.VerticalDivider(width=1),
        ft.Column([
            ft.Text("CRUD Workbench", size=16, weight="bold"),
            input_sym, input_eng, input_hindi, input_date,
            ft.Row([
                ft.ElevatedButton("➕ Add", on_click=db_add,
                                  bgcolor="blue", color="white"),
                ft.ElevatedButton("📝 Update", on_click=db_edit,
                                  bgcolor="orange", color="white"),
            ]),
            ft.ElevatedButton("🧹 Clear", on_click=clear_fields,
                              bgcolor="gray", color="white"),
            crud_status,
        ], width=320, scroll="always")
    ], expand=True)

    # Use NavigationBar instead of Tabs for better Android compatibility
    views = [engine_view, crud_view]
    current_view = ft.Ref[ft.Column]()

    view_container = ft.Container(
        content=engine_view,
        expand=True,
    )

    def on_nav_change(e):
        view_container.content = views[e.control.selected_index]
        page.update()

    nav_bar = ft.NavigationBar(
        selected_index=0,
        on_change=on_nav_change,
        destinations=[
            ft.NavigationBarDestination(
                icon=ft.icons.SEARCH,
                label="Oracle Engine",
            ),
            ft.NavigationBarDestination(
                icon=ft.icons.TABLE_ROWS,
                label="Database",
            ),
        ]
    )

    try:
        page.add(
            ft.Column(
                controls=[view_container, nav_bar],
                expand=True,
                spacing=0,
            )
        )
    except Exception as ex:
        page.add(ft.Text(f"Startup Error: {str(ex)}", color="red", size=16))
        page.update()
        return

    # Auto-build on first launch in background
    threading.Thread(target=check_and_auto_build, daemon=True).start()


ft.app(target=main)
