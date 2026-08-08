
import os
import sqlite3
import threading
import csv
import io
import time
import math
import json
import random
from datetime import datetime

try:
    import requests
    REQUESTS_OK = True
except Exception:
    REQUESTS_OK = False

import flet as ft
import flet.canvas as cv

# ── CONSTANTS ──────────────────────────────────────────────────────────────────
AKSHARA_VALS = {
    'अ':1,'आ':2,'इ':3,'ई':4,'उ':5,'ऊ':6,'ए':7,'ऐ':8,'ओ':9,'औ':10,
    'क':11,'ख':12,'ग':13,'ग':14,'ङ':15,'च':16,'छ':17,'ज':18,'झ':19,'ञ':20,
    'ट':21,'ठ':22,'ड':23,'ढ':24,'ण':25,'त':26,'थ':27,'द':28,'ध':29,'न':30,
    'प':31,'फ':32,'ब':33,'भ':34,'म':35,'य':36,'र':37,'ल':38,'व':39,'श':40,
    'ष':41,'स':42,'ह':43,'ि':2,'ा':2,'े':7,'ै':8,'ो':9,'ौ':10,'्':0,'ं':1
}
SUTRA_MAP = {
    0:"अनंत(Ananta)",1:"शक्ति(Shakti)",2:"ज्ञान(Gnana)",
    3:"धर्म(Dharma)",4:"वैराग्य(Vairagya)",5:"ऐश्वर्य(Aishwarya)",
    6:"यश(Yashas)",7:"श्री(Shree)",8:"वीर्य(Veerya)"
}
GRAHA = {
    0:("मंगल Mars","BULLISH",4,"Metals Defence Energy","1-7 Days","Strict stop-loss","Tuesday"),
    1:("सूर्य Sun","BULLISH",5,"PSU Govt Energy Gold","1-4 Weeks","Enter Monday","Sunday"),
    2:("चंद्र Moon","VOLATILE",2,"FMCG Dairy Retail","1-3 Days","Avoid overnight","Monday"),
    3:("गुरु Jupiter","STRONGLY BULLISH",5,"Banking Education","1-6 Months","Watch retrograde","Thursday"),
    4:("राहु Rahu","SPECULATIVE",3,"Tech Pharma Foreign","Caution","No leverage","Saturday"),
    5:("बुध Mercury","BULLISH",4,"IT Telecom Media","1-3 Weeks","Watch retrograde","Wednesday"),
    6:("शुक्र Venus","BULLISH",4,"FMCG Luxury Hotels","2-8 Weeks","Book at peaks","Friday"),
    7:("केतु Ketu","BEARISH",2,"Old Economy Exit","Avoid Entry","Reduce positions","Tuesday"),
    8:("शनि Saturn","SLOW BULLISH",3,"Infra Metals Coal","3-12 Months","No panic sell","Saturday"),
}
# Six classical Bandha (traversal/lock) patterns from the Siribhoovalaya tradition —
# each is a distinct way of reading/moving through the 27x27 akshara matrix.
# Mapped here from Navaank as a symbolic "food for thought" overlay on the market forecast.
# 4th field = directional tendency: UP / SIDEWAYS / CONTINUATION (reinforces whatever Graha says)
BANDHA = {
    0:("रथबंध Rathabandha", "Chariot — steady, linear forward motion", "Favors trend-following; hold through medium-term moves rather than chasing every tick", "UP"),
    1:("चक्रबंध Chakrabandha", "Wheel — cyclical, repeating loops", "Expect cyclical swings; better suited to swing-trade re-entries than a single hold", "SIDEWAYS"),
    2:("पद्मबंध Padmabandha", "Lotus — layered, unfolding petal by petal", "Gradual, layered build-up; consider accumulating in tranches rather than one lump sum", "UP"),
    3:("हंसबंध Hamsabandha", "Swan — graceful glide, discernment (neera-kshira)", "Favors selective, quality-over-quantity entries; be choosy about timing", "UP"),
    4:("मुक्तावली Muktavali", "Pearl-chain — linked, sequential continuity", "Moves may be linked to sector/peer stocks; watch correlated names before acting alone", "CONTINUATION"),
    5:("सर्वतोभद्र Sarvatobhadra", "All-auspicious square — balance in every direction", "A balanced/range-bound signature; often better to wait for a clear breakout than force an entry", "SIDEWAYS"),
}

GRAHA_DIRECTION = {
    "BULLISH": "UP", "STRONGLY BULLISH": "UP", "SLOW BULLISH": "UP",
    "BEARISH": "DOWN", "VOLATILE": "SIDEWAYS", "SPECULATIVE": "SIDEWAYS",
}

def combine_direction(graha_signal, bandha_dir):
    g_dir = GRAHA_DIRECTION.get(graha_signal, "SIDEWAYS")
    if bandha_dir == "CONTINUATION":
        return g_dir, "Bandha reinforces the Graha's own direction (trend continuation)"
    if g_dir == bandha_dir:
        return g_dir, "Graha and Bandha AGREE — higher-confidence signal"
    if g_dir == "SIDEWAYS" or bandha_dir == "SIDEWAYS":
        return "SIDEWAYS", "One signal points range-bound — lower conviction either way"
    return "MIXED", "Graha and Bandha CONFLICT — contradictory signals, avoid strong conviction"

DIR_ARROW = {"UP": "🔼 UP", "DOWN": "🔽 DOWN", "SIDEWAYS": "↔️ SIDEWAYS", "MIXED": "⚠️ MIXED"}

NAK = [
    "अश्विनी","भरणी","कृत्तिका","रोहिणी","मृगशिरा","आर्द्रा",
    "पुनर्वसु","पुष्य","आश्लेषा","मघा","पूर्वाफाल्गुनी","उत्तराफाल्गुनी",
    "हस्त","चित्रा","स्वाति","विशाखा","अनुराधा","ज्येष्ठा",
    "मूल","पूर्वाषाढ़ा","उत्तराषाढ़ा","श्रवण","धनिष्ठा","शतभिषा",
    "पूर्वाभाद्रपद","उत्तराभाद्रपद","रेवती"
]
# Sarvatobhadra Chakra Vedha (obstruction) pairs — classical Muhurta-shastra nakshatra
# pairing used to flag an afflicted/inauspicious combination. Indices are 0-based to
# match NAK above (0=Ashwini ... 26=Revati). Dhanishta (22) traditionally has no partner.
VEDHA_PAIRS = {
    0:17, 17:0,  1:16, 16:1,  2:15, 15:2,  3:14, 14:3,  4:13, 13:4,
    5:12, 12:5,  6:11, 11:6,  7:10, 10:7,  8:9,  9:8,
    18:26, 26:18, 19:25, 25:19, 20:24, 24:20, 21:23, 23:21,
    22: None,
}
# Classical Nakshatra Lord cycle (Vimshottari Dasha order) — this part IS standard,
# well-documented Vedic astrology, repeating 3x across all 27 nakshatras.
NAKSHATRA_LORD_CYCLE = ["Ke","Ve","Su","Mo","Ma","Ra","Ju","Sa","Me"]
PLANET_ABBR_TO_GRAHA_IDX = {"Ma":0,"Su":1,"Mo":2,"Ju":3,"Ra":4,"Me":5,"Ve":6,"Ke":7,"Sa":8}
def nak_lord_abbr(nak_idx):
    return NAKSHATRA_LORD_CYCLE[nak_idx % 9]
def nak_lord_graha(nak_idx):
    return GRAHA[PLANET_ABBR_TO_GRAHA_IDX[nak_lord_abbr(nak_idx)]]
CURATED = {
    "SBIN":"भारतीय स्टेट बैंक","HDFCBANK":"एचडीएफसी बैंक",
    "ICICIBANK":"आईसीआईसीआई बैंक","AXISBANK":"एक्सिस बैंक",
    "RELIANCE":"रिलायंस लिमिटेड","TCS":"टाटा कंसल्टेंसी सर्विसेज",
    "INFY":"इन्फोसिस","WIPRO":"विप्रो",
    "NTPC":"राष्ट्रीय ताप विद्युत निगम",
    "ONGC":"तेल और प्राकृतिक गैस निगम",
    "TATASTEEL":"टाटा स्टील","COALINDIA":"कोल इंडिया",
    "HINDUNILVR":"हिंदुस्तान यूनिलीवर","ITC":"आईटीसी",
    "LT":"लार्सन एंड टुब्रो","MARUTI":"मारुति सुजुकी",
    "TATAMOTORS":"टाटा मोटर्स","SUNPHARMA":"सन फार्मास्युटिकल",
    "BHARTIARTL":"भारती एयरटेल","BAJFINANCE":"बजाज फाइनेंस",
    "LICI":"भारतीय जीवन बीमा निगम","IRCTC":"भारतीय रेलवे खानपान",
    "HAL":"हिंदुस्तान एयरोनॉटिक्स","ASIANPAINT":"एशियन पेंट्स",
    "TITAN":"टाइटन कंपनी","ZOMATO":"जोमैटो",
    "PNB":"पंजाब नेशनल बैंक","BEL":"भारत इलेक्ट्रॉनिक्स",
    "HCLTECH":"एचसीएल टेक्नोलॉजीज","ADANIPORTS":"अदानी पोर्ट्स",
    "KOTAKBANK":"कोटक महिंद्रा बैंक","DRREDDY":"डॉ रेड्डीज",
    "CIPLA":"सिप्ला","M&M":"महिंद्रा एंड महिंद्रा",
    "ULTRACEMCO":"अल्ट्राटेक सीमेंट","BAJAJ-AUTO":"बजाज ऑटो",
    "POWERGRID":"पावर ग्रिड कॉर्पोरेशन","GAIL":"गेल इंडिया",
    "BPCL":"भारत पेट्रोलियम","IOC":"इंडियन ऑयल कॉर्पोरेशन",
    "BANKBARODA":"बैंक ऑफ बड़ौदा","CANBK":"केनरा बैंक",
    "UNIONBANK":"यूनियन बैंक ऑफ इंडिया","YESBANK":"यस बैंक",
    "IDFCFIRSTB":"आईडीएफसी फर्स्ट बैंक","FEDERALBNK":"फेडरल बैंक",
    "SAIL":"स्टील अथॉरिटी ऑफ इंडिया","NMDC":"एनएमडीसी",
    "HINDALCO":"हिंडाल्को निष्कर्ष","VEDL":"वेदांता",
    "TATAPOWER":"टाटा पावर","ADANIPOWER":"अदानी पावर",
    "ADANIENT":"अदानी एंटरप्राइजेज","ADANIGREEN":"अदानी ग्रीन配置",
    "DLF":"डीएलएफ","GODREJPROP":"गोदरेज प्रॉपर्टीज",
    "BRITANNIA":"ब्रिटानिया景气","DABUR":"डाबर इंडिया",
    "MARICO":"मेरिको","NESTLEIND":"नेस्ले इंडिया",
    "HEROMOTOCO":"हीरो मोटोकॉर्प","EICHERMOT":"आयशर मोटर्स",
    "ASHOKLEY":"अशोक लेलैंड","TVSMOTOR":"टीवीएस मोटर",
    "CONCOR":"कंटेनर कॉर्पोरेशन","BHEL":"भारत हेवी इलेक्ट्रिकल्स",
    "APOLLOHOSP":"अपोलो हॉस्पिटल्स","DIVISLAB":"दिविस लेबोरेटरीज",
    "BIOCON":"बायोकॉन","LUPIN":"ल्यूपिन",
    "AUROPHARMA":"ऑरोबिंदो फार्मा","TORNTPHARM":"टोरेंट फार्मा",
}
WD = {
    "LIMITED":"लिमिटेड","LTD":"लिमिटेड","BANK":"बैंक",
    "INDUSTRIES":"इंडस्ट्रीज","INDUSTRY":"उद्योग",
    "INDIA":"इंडिया","INDIAN":"इंडियन","POWER":"पावर",
    "ENERGY":"एनर्जी","FINANCE":"फाइनेंस","STEEL":"स्टील",
    "MOTORS":"मोटर्स","MOTOR":"मोटर",
    "TECHNOLOGIES":"टेक्नोलॉजीज","TECHNOLOGY":"टेक्नोलॉजी",
    "AND":"एंड","&":"एंड","SERVICES":"सर्विसेज","SERVICE":"सर्विस",
    "PHARMA":"फार्मा","PHARMACEUTICALS":"फार्मास्युटिकल्स",
    "CEMENT":"सीमेंट","OIL":"ऑयल","GAS":"गैस",
    "TELECOM":"टेलीकॉम","GROUP":"ग्रुप",
    "CHEMICALS":"केमिकल्स","NATIONAL":"नेशनल",
    "CORPORATION":"कॉर्पोरेशन","CORP":"कॉर्प",
    "MEDIA":"MEDIA","HEALTHCARE":"हेल्थकेयर",
    "CAPITAL":"कैपिटल","INSURANCE":"इंश्योरेंस",
    "REALTY":"रियल्टी","PROPERTIES":"प्रॉपर्टीज",
    "AUTO":"ऑटो","AUTOMOBILE":"ऑटोमोबाइल",
    "ELECTRIC":"इलेक्ट्रिक","ELECTRONICS":"इलेक्ट्रॉनिक्स",
    "CONSTRUCTION":"कंस्ट्रक्शन","INFRASTRUCTURE":"इन्फ्रास्ट्रक्चर",
    "ENTERPRISES":"एंटरप्राइजेज","ENTERPRISE":"एंटरप्राइज",
    "HOLDINGS":"होल्डिंग्स","INVESTMENTS":"इन्वेस्टमेंट्स",
    "LABORATORIES":"लेबोरेटरीज","LABS":"लैब्स",
    "HOSPITAL":"हॉस्पिटल","HOSPITALS":"हॉस्पिटल्स",
    "FOODS":"फूड्स","FOOD":"फूड","BEVERAGES":"बेवरेजेज",
    "TEXTILE":"टेक्सटाइल","TEXTILES":"टेक्सटाइल्स",
    "FERTILIZERS":"फर्टिलाइजर्स","AGRO":"एग्रो",
    "TRADING":"ट्रेडिंग","EXPORTS":"एक्सपोर्ट्स",
    "SOLUTIONS":"सॉल्यूशंस","SYSTEMS":"सिस्टम्स",
    "GLOBAL":"ग्लोबल","INTERNATIONAL":"इंटरनेशनल",
    "MANAGEMENT":"मैनेजमेंट","CONSULTING":"कंसULTING",
    "SECURITIES":"सिक्योरिटीज","PETROLEUM":"पेट्रोलियम",
    "COMPANY":"कंपनी","SOLAR":"सोलर","RENEWABLE":"रिन्यूएबल",
    "DIGITAL":"डिजिटल","NETWORK":"नेटवर्क","NETWORKS":"नेटवर्क्स",
}
PR = {
    'A':'ए','B':'ब','C':'क','D':'ड','E':'इ','F':'फ',
    'G':'ग','H':'ह','I':'इ','J':'ज','K':'क','L':'ल',
    'M':'म','N':'न','O':'ओ','P':'प','Q':'क','R':'र',
    'S':'स','T':'ट','U':'य','V':'व','W':'व','X':'क्स',
    'Y':'य','Z':'ज'
}
NSE_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"

def fetch_nse_quote(symbol):
    """Fetches live price info for a symbol from NSE's quote-equity API.
    Unlike the static archives.nseindia.com CSV above, this endpoint is behind
    NSE's anti-bot protection and needs a primed session (cookies from the
    homepage) plus browser-like headers, or it returns 401/403."""
    if not REQUESTS_OK:
        raise RuntimeError("The 'requests' library is not available in this build.")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/get-quotes/equity?symbol=" + symbol,
    }
    sess = requests.Session()
    sess.headers.update(headers)
    sess.get("https://www.nseindia.com", timeout=8)  # primes cookies against the anti-bot check
    resp = sess.get("https://www.nseindia.com/api/quote-equity?symbol=" + symbol, timeout=8)
    resp.raise_for_status()
    data = resp.json()
    pi = data.get("priceInfo", {}) or {}
    wk = pi.get("weekHighLow", {}) or {}
    return {
        "last_price": pi.get("lastPrice"),
        "change": pi.get("change"),
        "pchange": pi.get("pChange"),
        "prev_close": pi.get("previousClose"),
        "week_high": wk.get("max"),
        "week_low": wk.get("min"),
        "source": "NSE India",
    }

def fetch_yahoo_quote(symbol):
    """Fallback quote source when NSE blocks the request — Yahoo Finance's chart
    API (the same data source the popular 'yfinance' library uses under the hood).
    No API key needed, and far more permissive than NSE for simple lookups.
    NSE-listed stocks use the '.NS' suffix on Yahoo Finance."""
    if not REQUESTS_OK:
        raise RuntimeError("The 'requests' library is not available in this build.")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.NS"
    resp = requests.get(url, headers=headers, timeout=8)
    resp.raise_for_status()
    data = resp.json()
    result = (data.get("chart") or {}).get("result")
    if not result:
        raise RuntimeError("No data returned for this symbol on Yahoo Finance (it may not be listed under '.NS').")
    meta = result[0].get("meta", {}) or {}
    last_price = meta.get("regularMarketPrice")
    prev_close = meta.get("previousClose") or meta.get("chartPreviousClose")
    change = pchange = None
    try:
        if last_price is not None and prev_close:
            change = round(last_price - prev_close, 2)
            pchange = round((change / prev_close) * 100, 2)
    except (TypeError, ZeroDivisionError):
        pass
    return {
        "last_price": last_price, "change": change, "pchange": pchange,
        "prev_close": prev_close,
        "week_high": meta.get("fiftyTwoWeekHigh"), "week_low": meta.get("fiftyTwoWeekLow"),
        "source": "Yahoo Finance",
    }

def fetch_stock_quote(symbol):
    """Tries NSE first (primary source); if it's blocked or errors out, falls
    back to Yahoo Finance automatically for the same symbol. Raises only if
    BOTH sources fail, with both error reasons included."""
    try:
        return fetch_nse_quote(symbol)
    except Exception as nse_err:
        try:
            return fetch_yahoo_quote(symbol)
        except Exception as yahoo_err:
            raise RuntimeError(f"NSE failed ({nse_err}); Yahoo Finance fallback also failed ({yahoo_err})")

# ── COLORS ─────────────────────────────────────────────────────────────────────
C = {
    "bg":       "#FFFFFF",
    "primary":  "#0D47A1",
    "secondary":"#1565C0",
    "accent":   "#1976D2",
    "dark_txt": "#0D47A1",
    "black_txt":"#212121",
    "hint_txt": "#546E7A",
    "green":    "#1B5E20",
    "orange":   "#BF360C",
    "red":      "#B71C1C",
    "inp_bg":   "#F3F8FF",
    "res_bg":   "#EEF4FF",
    "row_odd":  "#F3F8FF",
    "row_even": "#FFFFFF",
    "divider":  "#90CAF9",
}

# ── HELPER FUNCTIONS ───────────────────────────────────────────────────────────
def parse_dt(s):
    if not s: return None
    for f in ("%d-%m-%Y","%Y-%m-%d","%d/%m/%Y","%d-%b-%Y"):
        try: return datetime.strptime(s.strip(), f)
        except: pass
    return None

def quick_verdict(asum, ldt_str):
    """Lightweight one-line Bhoovalaya + Sarvatobhadra summary for stock-list rows —
    same Navaank/Graha/Bandha/Vedha logic as the full Oracle report, condensed."""
    ldate = parse_dt(ldt_str)
    today = datetime.now()
    tval = ((today - ldate).days % 730) if ldate else 0
    nv = (asum % 9) or 9
    g = GRAHA[(nv - 1) % 9]
    b = BANDHA[(nv - 1) % 6]
    combined_dir, _ = combine_direction(g[1], b[3])
    has_vedha = False
    if ldate:
        today_nak_idx = today.timetuple().tm_yday % 27
        birth_nak_idx = ldate.timetuple().tm_yday % 27
        vedha_partner = VEDHA_PAIRS.get(today_nak_idx)
        has_vedha = (vedha_partner is not None) and (vedha_partner == birth_nak_idx)
    return combined_dir, has_vedha

# ── RAMAL PRASHNA (Arabic/Persian geomancy, cast at the moment of the question) ──
# The 16 Ramal Shakals mapped to binary tuples (Top to Bottom: Agni, Vayu, Jala, Prithvi)
# 1 = Single Dot (Odd/Fire/Air aspect), 0 = Double Dot or Line (Even/Water/Earth aspect)
RAMAL_DICTIONARY = {
    (1, 1, 1, 1): {"name": "Jamat (जमात)", "nature": "Mitrik (Inward)", "element": "Agni", "bias": "Strong Bullish"},
    (0, 0, 0, 0): {"name": "Tariq (तारीक़)", "nature": "Kharij (Outward)", "element": "Prithvi", "bias": "Bearish"},
    (1, 0, 0, 0): {"name": "Lahan (लहान)", "nature": "Mitrik (Inward)", "element": "Jala", "bias": "Bullish"},
    (0, 1, 1, 1): {"name": "Nafki (नफ़की)", "nature": "Kharij (Outward)", "element": "Vayu", "bias": "Bearish"},
    (1, 1, 0, 0): {"name": "Kajjul (कज्जुल)", "nature": "Mitrik (Inward)", "element": "Agni", "bias": "Bullish"},
    (0, 0, 1, 1): {"name": "Uqla (उक़ला)", "nature": "Nishasht (Neutral)", "element": "Prithvi", "bias": "Sideways"},
    (1, 0, 1, 0): {"name": "Nasrut-Kharij (नसरुत खारिज)", "nature": "Kharij (Outward)", "element": "Vayu", "bias": "Bearish"},
    (0, 1, 0, 1): {"name": "Nasrut-Dakhil (नसरुत दाखिल)", "nature": "Mitrik (Inward)", "element": "Jala", "bias": "Bullish"},
    (1, 0, 0, 1): {"name": "Humra (हुमरा)", "nature": "Kharij (Fire)", "element": "Agni", "bias": "Volatile / Bearish"},
    (0, 1, 1, 0): {"name": "Bayaz (बयाज़)", "nature": "Mitrik (Inward)", "element": "Jala", "bias": "Bullish"},
    (1, 1, 0, 1): {"name": "Nusra (नुसरा)", "nature": "Mitrik (Inward)", "element": "Vayu", "bias": "Bullish"},
    (0, 0, 1, 0): {"name": "Kosa (कोसा)", "nature": "Kharij (Outward)", "element": "Prithvi", "bias": "Bearish"},
    (1, 1, 1, 0): {"name": "Fath (फथ)", "nature": "Mitrik (Inward)", "element": "Agni", "bias": "Bullish"},
    (0, 1, 0, 0): {"name": "Rahu (राहु)", "nature": "Kharij (Outward)", "element": "Vayu", "bias": "Bearish"},
    (1, 0, 1, 1): {"name": "Munkis (मुंकिस)", "nature": "Kharij (Outward)", "element": "Prithvi", "bias": "Volatile / Bearish"},
    (0, 0, 0, 1): {"name": "Ijtima (इजतिमा)", "nature": "Mitrik (Inward)", "element": "Jala", "bias": "Bullish"},
}

def ramal_add(fig1, fig2):
    """Ramal Parity Addition (XOR equivalent): Odd+Odd=Even, Odd+Even=Odd."""
    return tuple((a + b) % 2 for a, b in zip(fig1, fig2))

def get_ramal_info(figure_tuple):
    return RAMAL_DICTIONARY.get(figure_tuple, {"name": f"Shakal {figure_tuple}", "nature": "Unknown", "element": "Mixed", "bias": "Neutral"})

RAMAL_HOUSE_DESC = [
    "1st House (Trader/Self)", "2nd House (Capital/Profit)", "3rd House (Trade Action)", "4th House (Stock Base)",
    "5th House (Speculation)", "6th House (Risks/Obstacles)", "7th House (Counter-party)", "8th House (Sudden Moves)",
    "9th House (Market Trend)", "10th House (Executive Flow)", "11th House (Net Gain/Target)", "12th House (Losses/Traps)",
    "13th House (Right Witness)", "14th House (Left Witness)", "15th House (The Judge)", "16th House (Final Outcome)",
]

def cast_ramal_chart():
    """Casts a fresh full 16-house Ramal Prashna chart for right now (random mother
    figures via disc-spin simulation): 4 Mothers -> 4 Daughters (transpose) -> 4
    Nephews -> 2 Witnesses -> Judge (15th) -> Final Outcome/Reconciler (16th)."""
    mothers = [tuple(random.choice([0, 1]) for _ in range(4)) for _ in range(4)]
    daughters = [tuple(mothers[col][row] for col in range(4)) for row in range(4)]
    nephews = [
        ramal_add(mothers[0], mothers[1]),
        ramal_add(mothers[2], mothers[3]),
        ramal_add(daughters[0], daughters[1]),
        ramal_add(daughters[2], daughters[3]),
    ]
    right_witness = ramal_add(nephews[0], nephews[1])
    left_witness  = ramal_add(nephews[2], nephews[3])
    judge = ramal_add(right_witness, left_witness)
    final_result = ramal_add(mothers[0], judge)

    grid = mothers + daughters + nephews + [right_witness, left_witness, judge, final_result]
    judge_info = get_ramal_info(judge)
    final_info = get_ramal_info(final_result)
    return {
        "grid": grid, "grid_desc": RAMAL_HOUSE_DESC,
        "house_1_trader": mothers[0], "house_2_capital": mothers[1],
        "house_3_trade_action": mothers[2], "house_4_stock_base": mothers[3],
        "house_5_speculation": daughters[0], "house_9_market_trend": nephews[0],
        "house_11_net_gain": nephews[2], "house_12_losses": nephews[3],
        "judge": judge, "judge_info": judge_info,
        "final_result": final_result, "final_info": final_info,
    }

def ramal_recommendation(judge_info, final_info):
    """Stricter than Judge-alone: requires Judge (15th) AND Final Outcome (16th) to
    AGREE on nature (Mitrik/Kharij) for a high-confidence call, matching the fuller
    16-house tradition. We still don't ask BUY/SELL intent, so both readings are given."""
    j_nature, f_nature = judge_info["nature"], final_info["nature"]
    if j_nature.startswith("Mitrik") and f_nature.startswith("Mitrik"):
        return ("BUY", "🟢 HIGH-PROBABILITY BUY (Strong Teji Alignment) — both Judge and Final Outcome show inward energy accumulation. Favors BUY; avoid fresh SELL here.")
    elif j_nature.startswith("Kharij"):
        return ("SELL", "🔴 AVOID BUYING (Mandi Warning) — Judge shows outward energy depletion, a potential price dump or trap. Favors SELL/short over fresh BUY.")
    else:
        return ("NEUTRAL", "⚪ NEUTRAL / WAIT FOR CONFIRMATION — mixed or non-agreeing Shakal signature; avoid trading without price-action support.")

def get_hindi(sym, eng):
    if sym in CURATED: return CURATED[sym]
    if not REQUESTS_OK:
        out = []
        for w in eng.upper().split():
            cw = w.strip("&.,()-/")
            out.append(WD.get(cw, "".join(PR.get(c,"") for c in cw)))
        return " ".join(out)
    try:
        url = ("https://translate.googleapis.com/translate_a/single"
               "?client=gtx&sl=en&tl=hi&dt=t&q=" + requests.utils.quote(eng))
        d = requests.get(url, timeout=5).json()
        t = "".join(p[0] for p in d[0] if p[0]).strip()
        if t and t != eng:
            time.sleep(0.15)
            return t
    except: pass
    out = []
    for w in eng.upper().split():
        cw = w.strip("&.,()-/")
        if cw in WD: out.append(WD[cw]); continue
        try:
            r = requests.get(
                "https://inputtools.google.com/request?text=" + cw + "&ime=transliteration_en_hi&num=1",
                timeout=4).json()
            out.append(r[1][0][1][0] if r[0]=="SUCCESS" else "".join(PR.get(c,"") for c in cw))
        except: out.append("".join(PR.get(c,"") for c in cw))
    return " ".join(out)

def calc(name):
    total, steps = 0, []
    for c in name:
        w = AKSHARA_VALS.get(c, 0)
        total += w
        if w > 0 or c == "्":
            steps.append(c + "=" + str(w))
        elif c == " ":
            steps.append("|")
    return total, " ".join(steps)

def make_report(asum, tval, ldate):
    nv    = (asum % 9) or 9
    g     = GRAHA[(nv - 1) % 9]
    b     = BANDHA[(nv - 1) % 6]
    combined_dir, combined_note = combine_direction(g[1], b[3])
    total = asum + tval
    sutra = SUTRA_MAP.get(total % 9, "")
    today = datetime.now()
    today_nak_idx = today.timetuple().tm_yday % 27
    nak   = NAK[today_nak_idx]
    wday  = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][today.weekday()]
    bars  = {1:"★☆☆☆☆",2:"★★☆☆☆",3:"★★★☆☆",4:"★★★★☆",5:"★★★★★"}
    today_lord = nak_lord_graha(today_nak_idx)
    if ldate:
        tc = ((today.timetuple().tm_yday - ldate.timetuple().tm_yday) % 27) + 1
        tn = ["जन्म","सम्पत","विपत","क्षेम","प्रत्यरि","साधक","वध","मित्र","परम-मित्र"]
        tara = tn[(tc-1)%9] + (" GOOD" if tc%9 in(2,4,6,8,0) else " CAUTION")
        birth_nak_idx = ldate.timetuple().tm_yday % 27
        birth_nak = NAK[birth_nak_idx]
        birth_lord = nak_lord_graha(birth_nak_idx)
        vedha_partner = VEDHA_PAIRS.get(today_nak_idx)
        has_vedha = (vedha_partner is not None) and (vedha_partner == birth_nak_idx)
        if has_vedha:
            vedha_line = "⚠️ VEDHA PRESENT — " + nak + " obstructs " + birth_nak + " → avoid fresh entry today"
            vedha_sector_line = ("  Affected sectors (via lords " + today_lord[0] + " / " + birth_lord[0] + "): "
                                  + today_lord[3] + "  &  " + birth_lord[3])
        else:
            vedha_line = "✅ NO VEDHA — " + nak + " and " + birth_nak + " are clear of each other"
            vedha_sector_line = ""
    else:
        birth_nak = "N/A"
        birth_lord = None
        vedha_line = "N/A (no listing date on record)"
        vedha_sector_line = ""
    S  = "─" * 30
    S2 = "═" * 30
    return "\n".join([
        S2, "    BHOOVALAYA ORACLE RESULT", S2, "",
        "STEP 1: AKSHARA WEIGHT THEORY", "  (Siribhoovalaya — Jain Text)",
        "  Each Hindi sound has weight:", "  अ=1 आ=2 इ=3 ई=4 उ=5 ऊ=6",
        "  ए=7 ऐ=8 ओ=9 क=11 ब=33 र=37", "  (64 Akshara × weight = sum)", S,
        "STEP 2: NAVAANK CALCULATION", "  (Vedic Digital Root Theory)",
        "  Akshara Sum = " + str(asum), "  Digital Root (1-9) = " + str(nv),
        "  " + _navaank_steps(asum), S,
        "STEP 3: TEMPORAL VIBRATION", "  (Jupiter Cycle = 730 days)",
        "  Days elapsed since listing", "  Temporal = Days % 730 = " + str(tval),
        "  Combined = " + str(asum) + " + " + str(tval) + " = " + str(total),
        "  Sutra Index = " + str(total) + " % 9 = " + str(total % 9), S,
        "STEP 4: SUTRA PRINCIPLE", "  (Bhoovalaya Cosmic Principle)", "  " + sutra, S,
        "STEP 5: RULING GRAHA (PLANET)", "  (Vedic Financial Astrology)", "  Navaank " + str(nv) + " → " + g[0], S2,
        "  MARKET FORECAST", S2, "  Signal   : " + g[1],
        "  Strength : " + bars.get(g[2],"") + "  " + str(g[2]) + "/5",
        "  Sectors  : " + g[3], "  Hold For : " + g[4], "  Caution  : " + g[5], "  Best Day : " + g[6], S,
        "STEP 6: VEDIC TIMING", "  (Nakshatra + Tara Bala)",
        "  Today    : " + wday + " " + today.strftime("%d-%m-%Y"),
        "  Nakshatra: " + nak, "  Tara Bala: " + tara, "  (Even Tara = GOOD entry)", S,
        "STEP 7: BHOOVALAYA BANDHA (TRAVERSAL PATTERN)", "  (Siribhoovalaya 27×27 Matrix Theory)",
        "  Navaank " + str(nv) + " → " + b[0],
        "  " + b[1], "  Thought: " + b[2],
        "  Bandha Direction: " + b[3], S,
        "STEP 8: COMBINED PRICE DIRECTION (GRAHA + BANDHA)", S2,
        "  " + DIR_ARROW.get(combined_dir, combined_dir),
        "  " + combined_note,
        "  (Graha=" + g[1] + " → " + GRAHA_DIRECTION.get(g[1],"SIDEWAYS") + "  |  Bandha=" + b[3] + ")",
        "  Symbolic guess, not a guarantee — verify against real price/volume action.", S,
        "STEP 9: SARVATOBHADRA VEDHA CHECK", "  (Muhurta Shastra — Nakshatra Obstruction)",
        "  Today's Nakshatra   : " + nak + "  (Lord: " + today_lord[0] + ")",
        "  Stock's Nakshatra   : " + birth_nak + " (from listing date)" + ("  (Lord: " + birth_lord[0] + ")" if birth_lord else ""),
        "  " + vedha_line,
    ] + ([vedha_sector_line] if vedha_sector_line else []) + [
        "  (Nakshatra-lord/sector link is this app's own symbolic extension —", "   classical Muhurta texts cover timing, not stock sectors)", S2,
        "  Research only. Not SEBI advice.", S2,
    ])

def _navaank_steps(n):
    steps = []
    current = n
    while current > 9:
        digits = [int(d) for d in str(current)]
        steps.append(str(current) + "=" + "+".join(str(d) for d in digits))
        current = sum(digits)
    if steps:
        return " → ".join(steps) + " → " + str(current)
    return str(current)

# ── VEDIC ASTROLOGY CALCULATIONS ──────────────────────────────────────────────
SIGN_ABB  = ["Ar","Ta","Ge","Ca","Le","Vi","Li","Sc","Sg","Cp","Aq","Pi"]
SIGN_HI   = ["मेष","वृष","मिथुन","कर्क","सिंह","कन्या","तुला","वृश्चिक","धनु","मकर","कुंभ","मीन"]
SIGN_FULL = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
PLANET_NAMES = {
    "As":"Lagna","Su":"Sun-सूर्य","Mo":"Moon-चंद्र","Ma":"Mars-मंगल","Me":"Mercury-बुध",
    "Ju":"Jupiter-गुरु","Ve":"Venus-शुक्र","Sa":"Saturn-शनि","Ra":"Rahu-राहु","Ke":"Ketu-केतु"
}

def norm360(x): return x % 360

def jd_from_dt(year, month, day, hour=12, minute=0):
    if month <= 2:
        year -= 1
        month += 12
    A = int(year / 100)
    B = 2 - A + int(A / 4)
    return (int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + hour/24.0 + minute/1440.0 + B - 1524.5)

IST_OFFSET_HOURS = 5.5  # India Standard Time = UTC + 5:30

def jd_ut_from_ist(year, month, day, hour, minute):
    """Julian Day formulas (and GMST/Ascendant) require UT. Our date/time fields and
    datetime.now() are IST (UTC+5:30), so subtract the offset to get true UT before use."""
    jd_local = jd_from_dt(year, month, day, hour, minute)
    return jd_local - (IST_OFFSET_HOURS / 24.0)

def lahiri_ayanamsa(jd):
    T = (jd - 2451545.0) / 36525.0
    return 23.85 + 0.013611 * T + 0.000092 * T * T

def calc_planet_positions(jd, lat=19.076, lon=72.877):
    T = (jd - 2451545.0) / 36525.0
    # Sun
    L0   = norm360(280.46646 + 36000.76983 * T)
    M_su = math.radians(norm360(357.52911 + 35999.05029 * T))
    C_su = ((1.914602 - 0.004817*T - 0.000014*T*T) * math.sin(M_su) + (0.019993 - 0.000101*T) * math.sin(2*M_su) + 0.000289 * math.sin(3*M_su))
    sun_t = norm360(L0 + C_su)
    # Moon
    L_mo  = norm360(218.3164477 + 481267.88123421 * T)
    D_mo  = math.radians(norm360(297.8501921 + 445267.1114034 * T))
    M_mo  = math.radians(norm360(134.9633964 + 477198.8675055 * T))
    M_su2 = math.radians(norm360(357.5291092 + 35999.0502909 * T))
    moon_t = norm360(L_mo + 6.289 * math.sin(M_mo) - 1.274 * math.sin(2*D_mo - M_mo) + 0.658 * math.sin(2*D_mo) - 0.214 * math.sin(M_mo) - 0.186 * math.sin(M_su2))
    # Mercury
    L_me  = norm360(252.2509 + 149474.0722 * T)
    M_me  = math.radians(norm360(168.6562 + 149472.5153 * T))
    merc_t = norm360(L_me + 23.440*math.sin(M_me) + 2.912*math.sin(2*M_me) + 0.513*math.sin(3*M_me))
    # Venus
    L_ve  = norm360(181.9798 + 58517.8160 * T)
    M_ve  = math.radians(norm360(212.9346 + 58517.8039 * T))
    ven_t  = norm360(L_ve + 47.682*math.sin(M_ve) + 1.319*math.sin(2*M_ve))
    # Mars
    L_ma  = norm360(355.433 + 19140.2993 * T)
    M_ma  = math.radians(norm360(19.373 + 19140.2973 * T))
    mars_t = norm360(L_ma + 10.691*math.sin(M_ma) + 0.623*math.sin(2*M_ma) + 0.050*math.sin(3*M_ma))
    # Jupiter
    L_ju  = norm360(34.3515 + 3034.9057 * T)
    M_ju  = math.radians(norm360(20.9961 + 3034.9056 * T))
    jup_t  = norm360(L_ju + 5.555*math.sin(M_ju) + 0.168*math.sin(2*M_ju))
    # Saturn
    L_sa  = norm360(50.0774 + 1222.1138 * T)
    M_sa  = math.radians(norm360(317.0207 + 1221.5515 * T))
    sat_t  = norm360(L_sa + 6.393*math.sin(M_sa) + 0.170*math.sin(2*M_sa))
    # Nodes
    rahu_t = norm360(125.0445 - 1934.1362*T + 0.0020708*T*T)
    ketu_t = norm360(rahu_t + 180)
    # Lagna
    eps     = math.radians(23.439291111 - 0.013004167*T)
    GMST    = norm360(280.46061837 + 360.98564736629*(jd - 2451545.0) + 0.000387933*T*T)
    LST     = math.radians(norm360(GMST + lon))
    lat_r   = math.radians(lat)
    asc_t   = math.degrees(math.atan2(math.cos(LST), -math.sin(LST)*math.cos(eps) - math.tan(lat_r)*math.sin(eps))) % 360

    ay = lahiri_ayanamsa(jd)
    sid = {
        "As": (asc_t - ay) % 360, "Su": (sun_t  - ay) % 360, "Mo": (moon_t - ay) % 360,
        "Me": (merc_t - ay) % 360, "Ve": (ven_t  - ay) % 360, "Ma": (mars_t - ay) % 360,
        "Ju": (jup_t  - ay) % 360, "Sa": (sat_t  - ay) % 360, "Ra": (rahu_t - ay) % 360, "Ke": (ketu_t - ay) % 360,
    }
    return sid, ay

def lon_to_sign_deg(lon):
    lon = lon % 360
    return int(lon / 30), round(lon % 30, 2)

def d9_sign(lon):
    sign, deg = lon_to_sign_deg(lon)
    nav_num   = int(deg / (30.0 / 9))
    start_map = {0:0, 1:9, 2:6, 3:3, 4:0, 5:9, 6:6, 7:3, 8:0, 9:9, 10:6, 11:3}
    return (start_map[sign] + nav_num) % 12

# ── ADVANCED CANVAS ENGINE: NORTH INDIAN VEDIC CHART ─────────────────────────────
def _diamond_shapes(positions, lagna_sign, title, chart_size=320, y_off=0, add_fill=None, retro=None, vargottama=None):
    if add_fill is None:
        add_fill = (y_off == 0)
    retro = retro or set()
    vargottama = vargottama or set()
    W = chart_size
    p = 8  # Padding
    x0, y0 = p, p + y_off
    x1, y1 = W - p, W - p + y_off
    cx, cy = W // 2, (W // 2) + y_off

    HOUSES_GEOM = {
        1:  {"poly": [(cx, y0), (x1, cy), (cx, y1), (x0, cy)], "txt": (cx, cy - 40),   "planets": (cx, cy - 15)},
        2:  {"poly": [(x0, y0), (cx, y0), (x0, cy)],           "txt": (x0 + 35, y0 + 25), "planets": (x0 + 35, y0 + 45)},
        3:  {"poly": [(x0, y0), (x0, cy), (cx, y0)],           "txt": (x0 + 25, y0 + 55), "planets": (x0 + 25, y0 + 75)},
        4:  {"poly": [(x0, cy), (cx, y0), (cx, cy)],           "txt": (cx - 45, cy - 15), "planets": (cx - 45, cy + 5)},
        5:  {"poly": [(x0, y1), (x0, cy), (cx, y1)],           "txt": (x0 + 25, y1 - 55), "planets": (x0 + 25, y1 - 35)},
        6:  {"poly": [(x0, y1), (cx, y1), (x0, cy)],           "txt": (x0 + 35, y1 - 25), "planets": (x0 + 35, y1 - 5)},
        7:  {"poly": [(cx, y1), (x0, cy), (cx, y0), (x1, cy)], "txt": (cx, cy + 40),   "planets": (cx, cy + 55)},
        8:  {"poly": [(x1, y1), (cx, y1), (x1, cy)],           "txt": (x1 - 35, y1 - 25), "planets": (x1 - 35, y1 - 5)},
        9:  {"poly": [(x1, y1), (x1, cy), (cx, y1)],           "txt": (x1 - 25, y1 - 55), "planets": (x1 - 25, y1 - 35)},
        10: {"poly": [(x1, cy), (cx, y1), (cx, cy)],           "txt": (cx + 45, cy + 15), "planets": (cx + 45, cy - 5)},
        11: {"poly": [(x1, y0), (x1, cy), (cx, y0)],           "txt": (x1 - 25, y0 + 55), "planets": (x1 - 25, y0 + 75)},
        12: {"poly": [(x1, y0), (cx, y0), (x1, cy)],           "txt": (x1 - 35, y0 + 25), "planets": (x1 - 35, y0 + 45)},
    }

    sign_planets = {i: [] for i in range(12)}
    for planet, s_idx in positions.items():
        sign_planets[int(s_idx)].append(planet)

    lagna_s = int(lagna_sign)
    def get_house_sign(h_num): return (lagna_s + h_num - 1) % 12

    shapes = [cv.Fill(paint=ft.Paint(color="#FCFDFE"))] if add_fill else []

    for h_num, info in HOUSES_GEOM.items():
        is_lagna = (h_num == 1)
        bg_color = "#FFF8E1" if is_lagna else "#F4F8FA"
        stroke_color = "#B71C1C" if is_lagna else "#1A237E"
        stroke_w = 2.0 if is_lagna else 1.2

        pts = info["poly"]
        path_data = [cv.Path.MoveTo(pts[0][0], pts[0][1])]
        for pt in pts[1:]:
            path_data.append(cv.Path.LineTo(pt[0], pt[1]))
        path_data.append(cv.Path.Close())

        shapes.append(cv.Path(path_data, paint=ft.Paint(color=bg_color, style=ft.PaintingStyle.FILL)))
        shapes.append(cv.Path(path_data, paint=ft.Paint(color=stroke_color, stroke_width=stroke_w, style=ft.PaintingStyle.STROKE)))

    grid_paint = ft.Paint(color="#1A237E", stroke_width=1.5, style=ft.PaintingStyle.STROKE)
    shapes.extend([
        cv.Line(x0, y0, x1, y1, paint=grid_paint),
        cv.Line(x1, y0, x0, y1, paint=grid_paint),
        cv.Line(cx, y0, x0, cy, paint=grid_paint),
        cv.Line(x0, cy, cx, y1, paint=grid_paint),
        cv.Line(cx, y1, x1, cy, paint=grid_paint),
        cv.Line(x1, cy, cx, y0, paint=grid_paint),
        cv.Rect(x=x0, y=y0, width=W-(2*p), height=W-(2*p), paint=grid_paint)
    ])

    for h_num, info in HOUSES_GEOM.items():
        sign_idx = get_house_sign(h_num)
        planets_here = sign_planets.get(sign_idx, [])
        tx, ty = info["txt"]
        sign_num_str = str(sign_idx + 1)

        shapes.append(cv.Text(x=tx - 6, y=ty - 10, text=sign_num_str, style=ft.TextStyle(size=12, color="#263238", weight="bold")))
        shapes.append(cv.Text(x=tx + 5, y=ty - 8, text=f"({SIGN_ABB[sign_idx]})", style=ft.TextStyle(size=8, color="#78909C")))

        if planets_here:
            px, py = info["planets"]
            tokens = []
            for pl in planets_here:
                is_retro = pl in retro
                is_varg  = pl in vargottama
                if is_retro and is_varg:
                    label, color = pl + "(R,V)", "#6A1B9A"   # purple — retrograde AND vargottama
                elif is_retro:
                    label, color = pl + "(R)", "#EF6C00"     # orange — retrograde
                elif is_varg:
                    label, color = pl + "(V)", "#00838F"     # teal — vargottama
                else:
                    label, color = pl, "#D32F2F"             # red — normal
                tokens.append((label, color))
            total_w = sum(len(lbl) * 6 for lbl, _ in tokens) + max(0, len(tokens) - 1) * 4
            tx_cursor = px - total_w // 2
            for lbl, color in tokens:
                shapes.append(cv.Text(x=tx_cursor, y=py, text=lbl, style=ft.TextStyle(size=11, color=color, weight="bold")))
                tx_cursor += len(lbl) * 6 + 4

    shapes.append(cv.Text(x=cx - 30, y=cy - 8, text=title, style=ft.TextStyle(size=10, color="#1A237E", weight="bold", bgcolor="#E8EAF6")))
    return shapes


def build_diamond_chart(positions, lagna_sign, title, chart_size=320, retro=None, vargottama=None):
    shapes = _diamond_shapes(positions, lagna_sign, title, chart_size, y_off=0, retro=retro, vargottama=vargottama)
    return cv.Canvas(shapes=shapes, width=chart_size, height=chart_size)


def build_dual_diamond_chart(d1_pos, lagna_d1, d9_pos, lagna_d9, chart_size=320, gap=30, retro=None, vargottama=None):
    """Draws D1 and D9 stacked on ONE canvas (avoids the Android multi-canvas rendering bug)."""
    shapes = []
    shapes.extend(_diamond_shapes(d1_pos, lagna_d1, "D1 RASI", chart_size, y_off=0, retro=retro, vargottama=vargottama))
    shapes.extend(_diamond_shapes(d9_pos, lagna_d9, "D9 NAVAMSHA", chart_size, y_off=chart_size + gap, retro=retro, vargottama=vargottama))
    total_h = (chart_size * 2) + gap
    return cv.Canvas(shapes=shapes, width=chart_size, height=total_h)


def build_dual_diamond_chart_with_bars(d1_pos, lagna_d1, d9_pos, lagna_d9, chart_size=320, gap=30, bar_h=36, bar_color="#1A237E", retro=None, vargottama=None):
    """Same single-canvas D1+D9 chart, but with a blue title bar overlaid above each diamond
    (still only ONE cv.Canvas control underneath, so the Android dual-canvas bug is avoided)."""
    y1 = bar_h
    y2 = bar_h + chart_size + gap + bar_h
    total_h = y2 + chart_size

    shapes = []
    shapes.extend(_diamond_shapes(d1_pos, lagna_d1, "D1 RASI", chart_size, y_off=y1, add_fill=True, retro=retro, vargottama=vargottama))
    shapes.extend(_diamond_shapes(d9_pos, lagna_d9, "D9 NAVAMSHA", chart_size, y_off=y2, add_fill=False, retro=retro, vargottama=vargottama))
    canvas = cv.Canvas(shapes=shapes, width=chart_size, height=total_h)

    def _bar(text, top):
        return ft.Container(
            content=ft.Text(text, size=13, color="#FFFFFF", weight="bold"),
            bgcolor=bar_color, alignment=ft.alignment.center,
            border_radius=6, top=top, left=0, right=0, height=bar_h - 4
        )

    bar1 = _bar("📊  D1 — RASI CHART", 0)
    bar2 = _bar("📊  D9 — NAVAMSHA CHART", y2 - bar_h)

    stack = ft.Stack(controls=[canvas, bar1, bar2], width=chart_size, height=total_h)

    legend = ft.Row(
        controls=[
            ft.Text("■ Normal", size=10, color="#D32F2F", weight="bold"),
            ft.Text("■ (R) Retrograde", size=10, color="#EF6C00", weight="bold"),
            ft.Text("■ (V) Vargottama", size=10, color="#00838F", weight="bold"),
            ft.Text("■ (R,V) Both", size=10, color="#6A1B9A", weight="bold"),
        ],
        alignment=ft.MainAxisAlignment.CENTER, wrap=True, spacing=12
    )
    return ft.Column(controls=[stack, ft.Container(height=6), legend], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

# ── MAIN APP ───────────────────────────────────────────────────────────────────
def main(page: ft.Page):
    try:
        page.title   = "Bhoovalaya Oracle"
        page.bgcolor = C["bg"]
        page.padding = 8
        page.scroll  = "auto"

        storage = os.getenv("FLET_APP_STORAGE_DATA", ".")
        db_path = os.path.join(storage, "bhuvalaya.db")

        try:
            conn = sqlite3.connect(db_path)
            conn.execute("""CREATE TABLE IF NOT EXISTS stocks(
                symbol      TEXT PRIMARY KEY,
                eng_name    TEXT,
                hindi_name  TEXT,
                ldate       TEXT,
                asum        INTEGER,
                breakdown   TEXT,
                series      TEXT DEFAULT 'EQ',
                portfolio   INTEGER DEFAULT 0)""")
            try:
                conn.execute("ALTER TABLE stocks ADD COLUMN portfolio INTEGER DEFAULT 0")
                conn.commit()
            except Exception:
                pass  # column already exists on installs upgraded from an earlier version
            conn.execute("""CREATE TABLE IF NOT EXISTS planet_rules(
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_type          TEXT NOT NULL,
                planet             TEXT NOT NULL,
                house_d1           INTEGER,
                house_d9           INTEGER,
                house_d1_list      TEXT,
                companion_planet   TEXT,
                companion_house_d9 INTEGER,
                retro_only         INTEGER DEFAULT 0,
                signal             TEXT NOT NULL,
                weight             REAL DEFAULT 1.0,
                note               TEXT)""")
            try:
                conn.execute("ALTER TABLE planet_rules ADD COLUMN house_d1_list TEXT")
                conn.commit()
            except Exception:
                pass  # column already exists on installs upgraded from an earlier version
            try:
                conn.execute("ALTER TABLE planet_rules ADD COLUMN companion_planet TEXT")
                conn.execute("ALTER TABLE planet_rules ADD COLUMN companion_house_d9 INTEGER")
                conn.commit()
            except Exception:
                pass  # columns already exist on installs upgraded from an earlier version
            conn.commit()
            conn.close()
        except: pass

        def rule_add(rule_type, planet, house_d1, house_d9, retro_only, signal, weight, note,
                     house_d1_list=None, companion_planet=None, companion_house_d9=None):
            conn = sqlite3.connect(db_path)
            conn.execute("""INSERT INTO planet_rules(rule_type,planet,house_d1,house_d9,house_d1_list,
                             companion_planet,companion_house_d9,retro_only,signal,weight,note)
                             VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                         (rule_type, planet, house_d1, house_d9, house_d1_list,
                          companion_planet, companion_house_d9, 1 if retro_only else 0, signal, weight, note))
            conn.commit(); conn.close()

        def rule_delete(rule_id):
            conn = sqlite3.connect(db_path)
            conn.execute("DELETE FROM planet_rules WHERE id=?", (rule_id,))
            conn.commit(); conn.close()

        def rule_list():
            conn = sqlite3.connect(db_path)
            rows = conn.execute("""SELECT id,rule_type,planet,house_d1,house_d9,house_d1_list,
                                    companion_planet,companion_house_d9,retro_only,signal,weight,note
                                    FROM planet_rules ORDER BY id""").fetchall()
            conn.close()
            return rows

        def get_house_num(sign_idx, lagna_sign_idx):
            """Convert a raw sign index (0-11) to a house number (1-12) relative to the lagna."""
            return ((int(sign_idx) - int(lagna_sign_idx)) % 12) + 1

        def evaluate_rules(d1_pos, d9_pos, lagna_d1, lagna_d9, retro_set):
            """Runs all stored rules against the current chart and returns (matches, net_score, avoid_matches).
            AVOID rules are kept separate from the BUY/SELL numeric score — a single genuine
            AVOID match should be a hard caution flag, not something that can be outweighed
            by a pile of small BUY-weighted rules elsewhere.
            A rule can optionally carry a Companion Condition (companion_planet + companion_house_d9):
            when set, the rule ONLY fires if that companion planet is ALSO in that D9 house at the
            same time — a genuine AND between two independent facts, not just two rules that could
            each fire alone."""
            houses_d1 = {p: get_house_num(s, lagna_d1) for p, s in d1_pos.items() if p != "As"}
            houses_d9 = {p: get_house_num(s, lagna_d9) for p, s in d9_pos.items() if p != "As"}
            matches, avoid_matches, score = [], [], 0.0
            for (rid, rtype, planet, hd1, hd9, hd1_list, comp_planet, comp_hd9, retro_only, signal, weight, note) in rule_list():
                planets_to_check = [planet] if planet != "ANY" else list(houses_d1.keys())
                for pl in planets_to_check:
                    if retro_only and pl not in retro_set:
                        continue
                    ok = False
                    if rtype == "D1_HOUSE" and houses_d1.get(pl) == hd1:
                        ok = True
                    elif rtype == "D9_HOUSE" and houses_d9.get(pl) == hd9:
                        ok = True
                    elif rtype == "D1_D9_COMPARE" and houses_d1.get(pl) == hd1 and houses_d9.get(pl) == hd9:
                        ok = True
                    elif rtype == "D1_D9_SAME_HOUSE" and houses_d1.get(pl) is not None and houses_d1.get(pl) == houses_d9.get(pl):
                        ok = True
                    elif rtype == "VARGOTTAMA" and d1_pos.get(pl) is not None and d1_pos.get(pl) == d9_pos.get(pl):
                        ok = True
                    elif rtype == "D1_RASHI" and d1_pos.get(pl) is not None and (d1_pos.get(pl) + 1) == hd1:
                        ok = True
                    elif rtype == "D9_RASHI" and d9_pos.get(pl) is not None and (d9_pos.get(pl) + 1) == hd9:
                        ok = True
                    elif rtype == "D9_TO_D1_LIST" and houses_d9.get(pl) == hd9 and hd1_list:
                        try:
                            allowed_d1_houses = {int(x.strip()) for x in hd1_list.split(",") if x.strip()}
                        except ValueError:
                            allowed_d1_houses = set()
                        if houses_d1.get(pl) in allowed_d1_houses:
                            ok = True
                    elif rtype == "D1_HOUSE_LIST" and hd1_list:
                        try:
                            allowed_d1_houses = {int(x.strip()) for x in hd1_list.split(",") if x.strip()}
                        except ValueError:
                            allowed_d1_houses = set()
                        if houses_d1.get(pl) in allowed_d1_houses:
                            ok = True
                    if ok and comp_planet and comp_hd9:
                        # Companion Condition — must ALSO be true, or this rule doesn't fire at all
                        if houses_d9.get(comp_planet) != comp_hd9:
                            ok = False
                    if ok:
                        entry = (pl, rtype, signal, weight, note)
                        if signal == "AVOID":
                            avoid_matches.append(entry)
                        else:
                            matches.append(entry)
                            score += weight if signal == "BUY" else (-weight if signal == "SELL" else 0)
            return matches, score, avoid_matches

        def is_retrograde(jd, planet_key, lat=19.076, lon=72.877):
            pos_prev, _ = calc_planet_positions(jd - 1, lat, lon)
            pos_now,  _ = calc_planet_positions(jd, lat, lon)
            diff = (pos_now[planet_key] - pos_prev[planet_key] + 540) % 360 - 180
            return diff < 0

        def get_retrograde_set(jd, lat=19.076, lon=72.877):
            return {p for p in ["Su","Mo","Ma","Me","Ju","Ve","Sa","Ra","Ke"] if is_retrograde(jd, p, lat, lon)}

        def db_count():
            try: return sqlite3.connect(db_path).execute("SELECT COUNT(*) FROM stocks").fetchone()[0]
            except: return 0

        def db_search(q, portfolio_only=False, letter=None):
            try:
                conn = sqlite3.connect(db_path)
                if letter:
                    # Query the database directly for this letter — never truncated by
                    # the general LIMIT below, since a letter's own count is naturally small.
                    base = "SELECT symbol, eng_name, hindi_name, ldate, asum, portfolio FROM stocks WHERE symbol LIKE ?"
                    params = [letter.upper() + "%"]
                    if q:
                        base += " AND (symbol LIKE ? OR eng_name LIKE ?)"
                        params += ["%" + q + "%", "%" + q + "%"]
                    if portfolio_only:
                        base += " AND portfolio=1"
                    base += " ORDER BY portfolio DESC, symbol LIMIT 500"
                    rows = conn.execute(base, params).fetchall()
                else:
                    base = "SELECT symbol, eng_name, hindi_name, ldate, asum, portfolio FROM stocks WHERE (symbol LIKE ? OR eng_name LIKE ?)"
                    params = ["%" + q + "%", "%" + q + "%"]
                    if portfolio_only:
                        base += " AND portfolio=1"
                    base += " ORDER BY portfolio DESC, symbol LIMIT 200"
                    rows = conn.execute(base, params).fetchall()
                conn.close()
                return rows
            except: return []

        def db_get(sym):
            try:
                conn = sqlite3.connect(db_path)
                row  = conn.execute("SELECT * FROM stocks WHERE symbol=?", (sym,)).fetchone()
                conn.close()
                return row
            except: return None

        def db_save(sym, eng, hindi, ldate, series="EQ"):
            asum, bk = calc(hindi)
            try:
                conn = sqlite3.connect(db_path)
                # Explicit UPSERT (not a blind REPLACE) so an existing stock's portfolio
                # on/off flag is preserved when the entry is edited, not reset to 0.
                conn.execute("""INSERT INTO stocks(symbol,eng_name,hindi_name,ldate,asum,breakdown,series,portfolio)
                                VALUES(?,?,?,?,?,?,?,0)
                                ON CONFLICT(symbol) DO UPDATE SET
                                    eng_name=excluded.eng_name, hindi_name=excluded.hindi_name,
                                    ldate=excluded.ldate, asum=excluded.asum,
                                    breakdown=excluded.breakdown, series=excluded.series""",
                             (sym, eng, hindi, ldate, asum, bk, series))
                conn.commit()
                conn.close()
                return True, asum
            except Exception as ex: return False, str(ex)

        def set_portfolio(sym, on):
            try:
                conn = sqlite3.connect(db_path)
                conn.execute("UPDATE stocks SET portfolio=? WHERE symbol=?", (1 if on else 0, sym))
                conn.commit(); conn.close()
            except: pass

        def db_delete(sym):
            try:
                conn = sqlite3.connect(db_path)
                conn.execute("DELETE FROM stocks WHERE symbol=?", (sym,))
                conn.commit()
                conn.close()
                return True
            except: return False

        status_txt = ft.Text("Loading...", size=15, color="#FFFFFF", weight="bold")
        status_bar = ft.Container(content=status_txt, bgcolor=C["secondary"], padding=10, border_radius=6)
        prg_bar  = ft.ProgressBar(value=0, visible=False, color="#FF6F00", bgcolor="#EEEEEE")
        prg_txt  = ft.Text("", size=14, color=C["orange"], weight="bold")

        def set_status(msg, color=None):
            status_txt.value   = msg
            status_bar.bgcolor = color or C["secondary"]
            page.update()

        def set_prg(pct, msg=""):
            prg_bar.visible, prg_bar.value, prg_txt.value = True, pct, msg
            page.update()

        def hide_prg():
            prg_bar.visible, prg_txt.value = False, ""
            page.update()

        def make_field(label, hint="", value="", multiline=False):
            return ft.TextField(
                label=label, label_style=ft.TextStyle(size=14, color=C["primary"]),
                hint_text=hint, hint_style=ft.TextStyle(size=13, color=C["hint_txt"]),
                value=value, text_size=16, text_style=ft.TextStyle(size=16, color=C["black_txt"], weight="bold"),
                border_color=C["primary"], focused_border_color=C["accent"], border_width=2,
                bgcolor=C["inp_bg"], cursor_color=C["primary"], multiline=multiline, min_lines=1 if not multiline else 2
            )

        def make_header(title, bgcolor=None):
            return ft.Container(content=ft.Text(title, size=16, color="#FFFFFF", weight="bold"), bgcolor=bgcolor or C["primary"], padding=ft.padding.symmetric(horizontal=12, vertical=8), border_radius=6)

        # ── SCREEN 1: ORACLE SEARCH ───────────────────────────────────────────
        fld_oracle = make_field("NSE Stock Symbol or Name", hint="Example: RELIANCE or TCS or SBIN", value="RELIANCE")
        result_txt = ft.Text("", size=15, color=C["dark_txt"], selectable=True, font_family="monospace")
        result_box = ft.Container(content=result_txt, bgcolor=C["res_bg"], padding=14, border_radius=8, border=ft.Border(top=ft.BorderSide(2, C["primary"]), bottom=ft.BorderSide(2, C["primary"]), left=ft.BorderSide(2, C["primary"]), right=ft.BorderSide(2, C["primary"])), visible=False)
        oracle_astro_container = ft.Column(spacing=15, horizontal_alignment=ft.CrossAxisAlignment.CENTER, visible=False)
        ramal_container = ft.Column(spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER, visible=False)
        current_stock = {"sym": None, "asum": None, "ldt": None}  # remembers the last analysed stock, so Ramal never re-asks

        def do_oracle(e):
            q = fld_oracle.value.strip().upper()
            if not q:
                set_status("Enter a stock symbol.", C["red"])
                return
            set_status("Searching: " + q + " ...", C["accent"])
            if db_count() < 5:
                set_status("Database empty! Tap BUILD DATABASE.", C["red"])
                result_txt.value = "DATABASE IS EMPTY\n\nGo to Database tab and\ntap BUILD DATABASE button."
                result_box.visible = True
                oracle_astro_container.visible = False
                ramal_container.visible = False
                page.update()
                return
            row = db_get(q)
            if not row:
                rows = db_search(q)
                if rows: row = db_get(rows[0][0])
            if row:
                sym, eng, hi, ldt, asum, bk, *_ = row
                ldate = parse_dt(ldt)
                days  = (datetime.now() - ldate).days if ldate else 0
                tval  = days % 730
                rep   = make_report(asum, tval, ldate)
                set_status("Found: " + sym, C["green"])
                result_txt.value = f"━" * 30 + f"\nSYMBOL  : {sym}\nCOMPANY : {eng}\nHINDI   : {hi}\nLISTED  : {ldt}\n" + f"━" * 30 + f"\nAKSHARA SUM  = {asum}\nTEMPORAL MOD = {tval}\nCOMBINED VIB = {asum + tval}\nNAVAANK      = {(asum % 9) or 9}\n\n{rep}"
                result_box.visible = True
                oracle_astro_container.visible = False   # hide any chart from a previous search
                ramal_container.visible = False          # hide any Ramal result from a previous search
                current_stock["sym"], current_stock["asum"], current_stock["ldt"] = sym, asum, ldt
            else:
                set_status("Not found: " + q, C["red"])
                result_txt.value = f"'{q}' NOT FOUND\n\nTry: RELIANCE TCS SBIN"
                result_box.visible = True
                oracle_astro_container.visible = False
                ramal_container.visible = False
                current_stock["sym"], current_stock["asum"], current_stock["ldt"] = None, None, None
            page.update()

        def do_oracle_back(e):
            oracle_astro_container.visible = False
            ramal_container.visible = False
            page.scroll_to(offset=0, duration=300)
            page.update()

        def do_oracle_astro(e):
            # ── D1 / D9 VEDIC CHART AT TIME OF THIS CALCULATION (single combined canvas) ──
            try:
                calc_time = datetime.now()
                jd = jd_ut_from_ist(calc_time.year, calc_time.month, calc_time.day, calc_time.hour, calc_time.minute)
                pos, ay = calc_planet_positions(jd, 19.076, 72.877)  # NSE Mumbai reference coords

                d1_pos = {p: lon_to_sign_deg(l)[0] for p, l in pos.items()}
                d9_pos = {p: d9_sign(l) for p, l in pos.items()}
                lagna_idx = d1_pos["As"]
                lagna_d9  = d9_pos["As"]
                retro_set = get_retrograde_set(jd, 19.076, 72.877)
                vargottama_set = {p for p in d1_pos if p != "As" and d1_pos.get(p) == d9_pos.get(p)}

                oracle_astro_container.controls.clear()
                oracle_astro_container.controls.append(ft.Divider(height=6, color=C["divider"]))
                oracle_astro_container.controls.append(make_header("🕉️ VEDIC KUNDALI AT TIME OF CALCULATION"))
                oracle_astro_container.controls.append(ft.Text(
                    "📅 " + calc_time.strftime("%d-%m-%Y %H:%M") + "   ✨ Ayanamsa (Lahiri): " + str(round(ay, 4)) + "°" +
                    ("   ⟲ Retrograde: " + ", ".join(sorted(retro_set)) if retro_set else "") +
                    ("   ★ Vargottama: " + ", ".join(sorted(vargottama_set)) if vargottama_set else ""),
                    size=13, color=C["primary"], weight="bold"
                ))
                oracle_astro_container.controls.append(build_dual_diamond_chart_with_bars(d1_pos, lagna_idx, d9_pos, lagna_d9, retro=retro_set, vargottama=vargottama_set))

                # ── CUSTOM RULES: BUY/SELL/AVOID RECOMMENDATION ──────────────
                matches, score, avoid_matches = evaluate_rules(d1_pos, d9_pos, lagna_idx, lagna_d9, retro_set)
                if avoid_matches:
                    rec_text, rec_color = f"🚫 CUSTOM RULES: AVOID THIS STOCK TODAY  ({len(avoid_matches)} avoid-rule match{'es' if len(avoid_matches) != 1 else ''})", "#212121"
                elif score > 0:
                    rec_text, rec_color = f"🟢 CUSTOM RULES: NET BUY  (score {score:+.1f})", C["green"]
                elif score < 0:
                    rec_text, rec_color = f"🔴 CUSTOM RULES: NET SELL  (score {score:+.1f})", C["red"]
                else:
                    rec_text, rec_color = "⚪ CUSTOM RULES: NEUTRAL / no matching rules", C["black_txt"]
                oracle_astro_container.controls.append(ft.Container(height=10))
                oracle_astro_container.controls.append(ft.Container(
                    content=ft.Text(rec_text, size=15, color="#FFFFFF", weight="bold"),
                    bgcolor=rec_color, padding=12, border_radius=8, alignment=ft.alignment.center
                ))
                if avoid_matches:
                    avoid_detail = "\n".join(f"🚫 {pl}  [{rt}]  {nt or ''}" for pl, rt, sig, w, nt in avoid_matches)
                    oracle_astro_container.controls.append(ft.Text(avoid_detail, size=11, color=C["red"], weight="bold", selectable=True))
                if matches:
                    detail = "\n".join(f"• {pl}  [{rt}]  → {sig}  (w={w})  {nt or ''}" for pl, rt, sig, w, nt in matches)
                    oracle_astro_container.controls.append(ft.Text(detail, size=11, color=C["black_txt"], selectable=True))

                oracle_astro_container.controls.append(ft.Container(height=8))
                oracle_astro_container.controls.append(ft.ElevatedButton("⬅  BACK TO ORACLE SEARCH", bgcolor=C["primary"], color="#FFFFFF", height=46, style=ft.ButtonStyle(text_style=ft.TextStyle(size=14, weight="bold")), on_click=do_oracle_back))
                oracle_astro_container.visible = True
            except Exception as aex:
                oracle_astro_container.controls.clear()
                oracle_astro_container.controls.append(ft.Text(f"Astro chart error: {str(aex)}", size=13, color=C["red"]))
                oracle_astro_container.controls.append(ft.ElevatedButton("⬅  BACK TO ORACLE SEARCH", bgcolor=C["primary"], color="#FFFFFF", height=46, on_click=do_oracle_back))
                oracle_astro_container.visible = True
            page.update()

        def do_oracle_ramal(e):
            # ── RAMAL PRASHNA — cast fresh right now, for whichever stock is already
            # loaded above. Never re-asks for the stock name or BUY/SELL intent. ──
            sym = current_stock.get("sym")
            if not sym:
                set_status("Search a stock first, then cast Ramal.", C["red"])
                page.update()
                return
            cast = cast_ramal_chart()
            ji, fi = cast["judge_info"], cast["final_info"]
            direction, ramal_line = ramal_recommendation(ji, fi)
            ramal_color = {"BUY": C["green"], "SELL": C["red"], "NEUTRAL": C["black_txt"]}[direction]

            # Cross-check against the Bhoovalaya combined direction (Step 8) for this same stock
            bhoovalaya_dir, has_vedha = quick_verdict(current_stock["asum"], current_stock["ldt"])
            if (direction == "BUY" and bhoovalaya_dir == "UP") or (direction == "SELL" and bhoovalaya_dir == "DOWN"):
                club_note = "✅ Ramal AGREES with Bhoovalaya's combined direction (" + bhoovalaya_dir + ") — higher-confidence read."
            elif direction == "NEUTRAL" or bhoovalaya_dir in ("SIDEWAYS", "MIXED"):
                club_note = "↔️ One or both systems read range-bound/mixed — lower conviction either way."
            else:
                club_note = "⚠️ Ramal and Bhoovalaya DISAGREE (Ramal=" + direction + " vs Bhoovalaya=" + bhoovalaya_dir + ") — treat with extra caution."

            grid_lines = "\n".join(
                f"{cast['grid_desc'][i]:<26}: {cast['grid'][i]}" for i in range(16)
            )

            ramal_container.controls.clear()
            ramal_container.controls.append(ft.Divider(height=6, color=C["divider"]))
            ramal_container.controls.append(make_header("🎲 RAMAL PRASHNA — " + sym))
            ramal_container.controls.append(ft.Text("📅 Cast at: " + datetime.now().strftime("%d-%m-%Y %H:%M:%S") + "  (full 16-house chart)", size=12, color=C["hint_txt"]))
            ramal_container.controls.append(ft.Text(grid_lines, size=10.5, color=C["black_txt"], font_family="monospace", selectable=True))
            ramal_container.controls.append(ft.Text("15th House (Judge): " + ji["name"] + "  [" + ji["nature"] + "]", size=13, weight="bold", color=C["primary"]))
            ramal_container.controls.append(ft.Text("16th House (Final Outcome): " + fi["name"] + "  [" + fi["nature"] + "]", size=13, weight="bold", color=C["primary"]))
            ramal_container.controls.append(ft.Container(
                content=ft.Text(ramal_line, size=14, color="#FFFFFF", weight="bold"),
                bgcolor=ramal_color, padding=12, border_radius=8, alignment=ft.alignment.center
            ))
            ramal_container.controls.append(ft.Text(club_note, size=12, color=C["black_txt"], weight="bold"))
            ramal_container.controls.append(ft.Text("Symbolic Prashna casting — a fresh cast can differ each time you tap. Not a guarantee, treat as one more input alongside the rest.", size=10, color=C["hint_txt"]))
            ramal_container.controls.append(ft.Container(height=6))
            ramal_container.controls.append(ft.ElevatedButton("⬅  BACK TO ORACLE SEARCH", bgcolor=C["primary"], color="#FFFFFF", height=46, on_click=do_oracle_back))
            ramal_container.visible = True
            page.update()

        oracle_screen = ft.Column(visible=True, controls=[
            make_header("🔮  ORACLE ANALYSIS"), ft.Divider(height=4, color=C["divider"]),
            ft.Text("Enter Stock Symbol or Name:", size=15, color=C["black_txt"], weight="bold"),
            fld_oracle,
            ft.ElevatedButton("🔍  SEARCH AND CALCULATE", bgcolor=C["green"], color="#FFFFFF", height=52, style=ft.ButtonStyle(text_style=ft.TextStyle(size=17, weight="bold")), on_click=do_oracle),
            ft.Divider(height=6, color=C["divider"]), result_box,
            ft.Container(height=10),
            ft.ElevatedButton("🪐  CALCULATE ASTRO (D1 / D9)", bgcolor=C["primary"], color="#FFFFFF", height=48, style=ft.ButtonStyle(text_style=ft.TextStyle(size=15, weight="bold")), on_click=do_oracle_astro),
            oracle_astro_container,
            ft.Container(height=10),
            ft.ElevatedButton("🎲  RAMAL PRASHNA (Cast Now)", bgcolor="#4E342E", color="#FFFFFF", height=48, style=ft.ButtonStyle(text_style=ft.TextStyle(size=15, weight="bold")), on_click=do_oracle_ramal),
            ramal_container
        ])

        # ── SCREEN 2: STOCK LIST ──────────────────────────────────────────────
        fld_list_search = make_field("Search Symbol or Company Name", hint="Leave blank to show first 100 stocks")
        list_rows = ft.Column(controls=[], spacing=2)
        list_count_txt = ft.Text("", size=14, color=C["primary"], weight="bold")
        fld_portfolio_only = ft.Switch(label="📌 Show only My Portfolio (ON stocks)", value=False, active_color=C["green"])
        fld_portfolio_only.on_change = lambda e: load_list(fld_list_search.value.strip().upper())
        fld_up_only = ft.Switch(label="🔼 Show only UP-signal stocks (regardless of Portfolio on/off)", value=False, active_color=C["green"])
        fld_up_only.on_change = lambda e: load_list(fld_list_search.value.strip().upper())
        current_list_symbols = []  # tracks symbols in current display order, for reference
        selected_letter = {"value": None}  # A-Z filter state — None means no letter filter active
        price_popup = ft.Column(spacing=6, visible=False)

        # ── LIVE TIMING SIGNAL (Auto Refresh) ─────────────────────────────
        # Your custom Rules (evaluate_rules) check the current sky right now, not any one
        # stock's identity — so this is ONE market-timing signal shared by every stock at a
        # given moment, not per-row. Shown here as a single blinking banner, refreshed on
        # the interval you set, rather than duplicating an identical dot on every row.
        stocks_auto_state = {"running": False, "stop_event": None}
        stocks_live_signal_state = {"label": "OFF", "color": C["hint_txt"]}
        fld_stocks_auto_interval = make_field("Auto Refresh Interval (minutes)", value="5")
        live_signal_text = ft.Text("⏱ LIVE TIMING SIGNAL: OFF", size=14, weight="bold", color="#FFFFFF")
        live_signal_container = ft.Container(
            content=live_signal_text, bgcolor=C["hint_txt"], padding=12, border_radius=8, alignment=ft.alignment.center
        )

        def compute_live_timing_signal():
            """Runs your custom Rules against the sky right now (same engine as Oracle's
            Calculate Astro), independent of any specific stock — a general market-timing read."""
            now = datetime.now()
            jd = jd_ut_from_ist(now.year, now.month, now.day, now.hour, now.minute)
            pos, ay = calc_planet_positions(jd, 19.076, 72.877)
            d1_pos = {p: lon_to_sign_deg(l)[0] for p, l in pos.items()}
            d9_pos = {p: d9_sign(l) for p, l in pos.items()}
            lagna_idx, lagna_d9 = d1_pos["As"], d9_pos["As"]
            retro_set = get_retrograde_set(jd, 19.076, 72.877)
            matches, score, avoid_matches = evaluate_rules(d1_pos, d9_pos, lagna_idx, lagna_d9, retro_set)
            if avoid_matches:
                return "AVOID", "#212121"
            elif score > 0:
                return "BUY", C["green"]
            elif score < 0:
                return "SELL", C["red"]
            else:
                return "NEUTRAL", C["accent"]

        def stocks_blink_loop(stop_event):
            blink_on = True
            while not stop_event.is_set():
                if stop_event.wait(0.8):
                    break
                blink_on = not blink_on
                label, color = stocks_live_signal_state["label"], stocks_live_signal_state["color"]
                if blink_on:
                    live_signal_container.bgcolor = color
                    live_signal_text.color = "#FFFFFF"
                else:
                    live_signal_container.bgcolor = "#FFFFFF"
                    live_signal_text.color = color
                page.update()

        def stocks_recalc_loop(interval_seconds, stop_event):
            while not stop_event.is_set():
                label, color = compute_live_timing_signal()
                stocks_live_signal_state["label"], stocks_live_signal_state["color"] = label, color
                live_signal_text.value = f"⏱ LIVE TIMING SIGNAL: {label}"
                live_signal_container.bgcolor = color
                live_signal_text.color = "#FFFFFF"
                load_list(fld_list_search.value.strip().upper())
                page.update()
                if stop_event.wait(interval_seconds):
                    break

        def do_toggle_stocks_auto_refresh(e):
            if stocks_auto_state["running"]:
                if stocks_auto_state["stop_event"]:
                    stocks_auto_state["stop_event"].set()
                stocks_auto_state["running"] = False
                btn_stocks_auto_refresh.text = "▶  START AUTO REFRESH"
                btn_stocks_auto_refresh.bgcolor = C["green"]
                live_signal_text.value = "⏱ LIVE TIMING SIGNAL: OFF"
                live_signal_container.bgcolor = C["hint_txt"]
                live_signal_text.color = "#FFFFFF"
                set_status("Stocks Auto Refresh stopped.", C["orange"])
                page.update()
                return
            try:
                minutes = float(fld_stocks_auto_interval.value)
                if not (0.5 <= minutes <= 1440):
                    raise ValueError("Interval must be between 0.5 and 1440 minutes")
            except Exception:
                set_status("Enter a valid interval in minutes (0.5–1440), e.g. 5.", C["red"])
                page.update()
                return
            stop_event = threading.Event()
            stocks_auto_state["stop_event"] = stop_event
            stocks_auto_state["running"] = True
            btn_stocks_auto_refresh.text = "⏸  STOP AUTO REFRESH"
            btn_stocks_auto_refresh.bgcolor = C["red"]
            set_status(f"Stocks Auto Refresh started — every {minutes:g} min.", C["green"])
            threading.Thread(target=stocks_recalc_loop, args=(minutes * 60, stop_event), daemon=True).start()
            threading.Thread(target=stocks_blink_loop, args=(stop_event,), daemon=True).start()
            page.update()

        btn_stocks_auto_refresh = ft.ElevatedButton("▶  START AUTO REFRESH", bgcolor=C["green"], color="#FFFFFF", height=46,
                                                      style=ft.ButtonStyle(text_style=ft.TextStyle(size=14, weight="bold")),
                                                      on_click=do_toggle_stocks_auto_refresh)

        def do_close_price_popup(e=None):
            price_popup.visible = False
            page.update()

        def do_fetch_price(sym):
            price_popup.controls.clear()
            price_popup.controls.append(ft.Divider(height=4, color=C["divider"]))
            price_popup.controls.append(ft.Text(f"⏳ Fetching live price for {sym} (NSE, then Yahoo Finance as fallback)...", size=13, color=C["accent"]))
            price_popup.visible = True
            page.scroll_to(offset=0, duration=200)
            page.update()

            def worker():
                try:
                    q = fetch_stock_quote(sym)
                    lp, chg, pchg, src = q["last_price"], q["change"], q["pchange"], q.get("source", "Unknown")
                    try:
                        chg_f = float(chg) if chg is not None else None
                        pchg_f = float(pchg) if pchg is not None else None
                        change_str = f"   ({chg_f:+.2f} / {pchg_f:+.2f}%)" if (chg_f is not None and pchg_f is not None) else ""
                        chg_color = C["green"] if (chg_f is not None and chg_f >= 0) else C["red"]
                    except (TypeError, ValueError):
                        change_str = ""
                        chg_color = C["black_txt"]
                    price_popup.controls.clear()
                    price_popup.controls.append(ft.Divider(height=4, color=C["divider"]))
                    price_popup.controls.append(make_header("💰 " + sym + " — LIVE PRICE"))
                    price_popup.controls.append(ft.Text(
                        f"Current Trading Price : ₹{lp}" + change_str,
                        size=15, weight="bold", color=chg_color
                    ))
                    price_popup.controls.append(ft.Text(f"Yesterday's Close      : ₹{q['prev_close']}", size=13, color=C["black_txt"]))
                    price_popup.controls.append(ft.Text(f"52-Week High           : ₹{q['week_high']}", size=13, color=C["green"]))
                    price_popup.controls.append(ft.Text(f"52-Week Low            : ₹{q['week_low']}", size=13, color=C["red"]))
                    price_popup.controls.append(ft.Text(f"Source: {src}" + (" (NSE was unreachable, used fallback)" if src != "NSE India" else "") + ". Can be delayed a few minutes — verify on your broker's terminal before trading.", size=10, color=C["hint_txt"]))
                    price_popup.controls.append(ft.ElevatedButton("✖  CLOSE", bgcolor=C["red"], color="#FFFFFF", height=40, on_click=do_close_price_popup))
                except Exception as ex:
                    price_popup.controls.clear()
                    price_popup.controls.append(ft.Divider(height=4, color=C["divider"]))
                    price_popup.controls.append(ft.Text(
                        f"⚠️ Could not fetch live price for {sym}.\nReason: {str(ex)}\n\nBoth NSE and the Yahoo Finance fallback were tried. Try again in a moment, or check your internet connection.",
                        size=12, color=C["red"]
                    ))
                    price_popup.controls.append(ft.ElevatedButton("✖  CLOSE", bgcolor=C["red"], color="#FFFFFF", height=40, on_click=do_close_price_popup))
                page.update()

            threading.Thread(target=worker, daemon=True).start()

        def load_list(q=""):
            list_rows.controls.clear()
            rows = db_search(q, portfolio_only=fld_portfolio_only.value, letter=selected_letter["value"])
            if fld_up_only.value:
                rows = [r for r in rows if quick_verdict(r[4], r[3])[0] == "UP"]
            current_list_symbols.clear()
            filter_note = " matching '" + q + "'" if q else (
                " (Portfolio only)" if fld_portfolio_only.value else " (first 200)")
            if fld_up_only.value:
                filter_note += " — UP signal only"
            if selected_letter["value"]:
                filter_note += f" — starting with '{selected_letter['value']}'"
            list_count_txt.value = f"Showing {len(rows)} stocks" + filter_note
            for i, r in enumerate(rows):
                sym, eng, hi, ldt, asum, portfolio = r
                current_list_symbols.append(sym)
                bg = C["row_odd"] if i % 2 == 0 else C["row_even"]
                combined_dir, has_vedha = quick_verdict(asum, ldt)
                badge_color = {"UP": C["green"], "DOWN": C["red"], "SIDEWAYS": C["orange"], "MIXED": C["accent"]}.get(combined_dir, C["accent"])
                badge_text = {"UP": "🔼 UP", "DOWN": "🔽 DOWN", "SIDEWAYS": "↔️ SIDE", "MIXED": "⚠️ MIXED"}.get(combined_dir, combined_dir)

                def make_portfolio_toggle(s):
                    def _on_change(e):
                        set_portfolio(s, e.control.value)
                        set_status(("📌 Added to" if e.control.value else "Removed from") + f" portfolio: {s}", C["green"] if e.control.value else C["orange"])
                        load_list(fld_list_search.value.strip().upper())  # refresh so ON stocks re-sort to the top immediately
                    return _on_change

                row_ctrl = ft.Container(
                    key=sym,
                    content=ft.Column([
                        ft.Row([
                            ft.Switch(value=bool(portfolio), active_color=C["green"], scale=0.8, on_change=make_portfolio_toggle(sym)),
                            ft.Container(content=ft.Text(sym, size=15, color="#FFFFFF", weight="bold"), bgcolor=C["primary"], padding=ft.padding.symmetric(horizontal=10, vertical=4), border_radius=4),
                            ft.Text(ldt, size=12, color=C["hint_txt"]),
                            ft.Text(f"Ak:{asum}", size=12, color=C["accent"]),
                            ft.Container(content=ft.Text(badge_text, size=11, color="#FFFFFF", weight="bold"), bgcolor=badge_color, padding=ft.padding.symmetric(horizontal=8, vertical=3), border_radius=4),
                        ] + ([ft.Container(content=ft.Text("Vedha", size=10, color="#FFFFFF", weight="bold"), bgcolor=C["red"], padding=ft.padding.symmetric(horizontal=6, vertical=3), border_radius=4)] if has_vedha else []), wrap=True, spacing=6),
                        ft.Text(eng, size=14, color=C["black_txt"], weight="bold"),
                        ft.Text(hi, size=15, color=C["primary"], weight="bold"),
                        ft.Row([
                            ft.TextButton("✏️ Edit", style=ft.ButtonStyle(color=C["accent"]), on_click=lambda e, s=sym: load_edit(s)),
                            ft.TextButton("🔮 Analyse", style=ft.ButtonStyle(color=C["green"]), on_click=lambda e, s=sym: (setattr(fld_oracle, 'value', s), show_screen("oracle"), do_oracle(e))),
                            ft.TextButton("🎲 Ramal", style=ft.ButtonStyle(color="#4E342E"), on_click=lambda e, s=sym: (setattr(fld_oracle, 'value', s), show_screen("oracle"), do_oracle(e), do_oracle_ramal(e))),
                            ft.TextButton("💰 Price", style=ft.ButtonStyle(color=C["orange"]), on_click=lambda e, s=sym: do_fetch_price(s)),
                        ], wrap=True),
                    ], spacing=2), bgcolor=bg, padding=8, border_radius=6, border=ft.Border(bottom=ft.BorderSide(1, C["divider"])))
                list_rows.controls.append(row_ctrl)
            page.update()

        list_screen = ft.Column(visible=False, controls=[
            make_header("📋 STOCK LIST (NSE India)"), ft.Divider(height=4, color=C["divider"]),
            ft.ElevatedButton("⬅  BACK TO ORACLE", bgcolor=C["primary"], color="#FFFFFF", height=44, on_click=lambda e: show_screen("oracle")),
            price_popup,
            ft.Divider(height=4, color=C["divider"]),
            ft.Text("⏱ LIVE TIMING SIGNAL — your custom Rules checked against the sky right now (one shared signal for all stocks, not per-row); blinks while active", size=10, color=C["hint_txt"]),
            fld_stocks_auto_interval, btn_stocks_auto_refresh, live_signal_container,
            ft.Divider(height=4, color=C["divider"]),
            ft.Text("🔼 UP  🔽 DOWN  ↔️ SIDE  ⚠️ MIXED — Bhoovalaya (Graha+Bandha) combined direction | Vedha = Sarvatobhadra caution flag", size=10, color=C["hint_txt"]),
            fld_list_search,
            ft.Row([
                ft.ElevatedButton("🔍 Search", bgcolor=C["primary"], color="#FFFFFF", height=46, on_click=lambda e: load_list(fld_list_search.value.strip().upper())),
                ft.ElevatedButton("📋 Show All", bgcolor=C["accent"], color="#FFFFFF", height=46, on_click=lambda e: load_list("")),
            ]),
            ft.Divider(height=4, color=C["divider"]),
            ft.Text("📌 PORTFOLIO — every stock defaults OFF. Flip a stock's own switch to mark it ON as yours; ON stocks are saved and always listed first, above the OFF ones.", size=11, color=C["black_txt"]),
            fld_portfolio_only, fld_up_only,
            list_count_txt, ft.Divider(height=4, color=C["divider"]), list_rows
        ])

        # ── SCREEN 3: DATA ENTRY ──────────────────────────────────────────────
        fld_sym, fld_eng, fld_hindi, fld_ldate, fld_series = make_field("Symbol *"), make_field("English Company Name *"), make_field("Hindi Name *"), make_field("Listing Date (DD-MM-YYYY)"), make_field("Series", value="EQ")
        entry_status = ft.Text("", size=15, color=C["green"], weight="bold")
        akshara_preview = ft.Container(content=ft.Text("", size=14, color=C["dark_txt"]), bgcolor=C["res_bg"], padding=10, border_radius=6, visible=False)

        def load_edit(sym):
            row = db_get(sym)
            if row:
                fld_sym.value, fld_eng.value, fld_hindi.value, fld_ldate.value, fld_series.value = row[0], row[1], row[2], row[3], row[6] if len(row)>6 else "EQ"
                fld_sym.disabled = True
                asum, bk = calc(row[2])
                akshara_preview.content.value, akshara_preview.visible = f"Akshara Sum = {asum}\n{bk[:80]}", True
                entry_status.value, entry_status.color = f"Loaded: {sym} — Edit and tap UPDATE", C["accent"]
                show_screen("entry")

        def do_transliterate(e):
            eng, sym = fld_eng.value.strip(), fld_sym.value.strip().upper()
            if not eng: return
            entry_status.value, entry_status.color = "Translating...", C["accent"]
            page.update()
            hi = get_hindi(sym, eng)
            fld_hindi.value = hi
            asum, bk = calc(hi)
            akshara_preview.content.value, akshara_preview.visible = f"Akshara Sum = {asum}\n{bk[:80]}", True
            entry_status.value, entry_status.color = "Hindi name generated!", C["green"]
            page.update()

        def do_save(e):
            sym, eng, hindi, ldate, series = fld_sym.value.strip().upper(), fld_eng.value.strip(), fld_hindi.value.strip(), fld_ldate.value.strip(), fld_series.value.strip() or "EQ"
            if not sym or not eng or not hindi: return
            ok, val = db_save(sym, eng, hindi, ldate, series)
            entry_status.value, entry_status.color = (f"Saved! {sym} Akshara={val}", C["green"]) if ok else (f"Failed: {val}", C["red"])
            if ok: fld_sym.disabled = False
            page.update()

        entry_screen = ft.Column(visible=False, controls=[
            make_header("✏️ MANAGE STOCK ENTRY"), ft.Divider(height=4, color=C["divider"]),
            fld_sym, fld_eng, ft.ElevatedButton("🌐 AUTO TRANSLITERATE HINDI", bgcolor=C["accent"], color="#FFFFFF", on_click=do_transliterate),
            fld_hindi, ft.ElevatedButton("👁️ PREVIEW SOUND WEIGHTS", bgcolor=C["secondary"], color="#FFFFFF", on_click=lambda e: (asum:=calc(fld_hindi.value.strip())) and setattr(akshara_preview.content,'value',f"Akshara: {asum[0]}\n{asum[1]}") or setattr(akshara_preview,'visible',True) or page.update()),
            akshara_preview, fld_ldate, fld_series, entry_status,
            ft.Row([
                ft.ElevatedButton("💾 SAVE NEW", bgcolor=C["green"], color="#FFFFFF", on_click=do_save),
                ft.ElevatedButton("🔄 UPDATE", bgcolor=C["primary"], color="#FFFFFF", on_click=do_save),
                ft.ElevatedButton("❌ DELETE", bgcolor=C["red"], color="#FFFFFF", on_click=lambda e: db_delete(fld_sym.value.strip().upper()) and setattr(entry_status,'value',"Deleted!") or page.update()),
                ft.ElevatedButton("🧹 CLEAR", bgcolor=C["hint_txt"], color="#FFFFFF", on_click=lambda e: (setattr(fld_sym,'value',""), setattr(fld_sym,'disabled',False), setattr(fld_eng,'value',""), setattr(fld_hindi,'value',""), setattr(fld_ldate,'value',""), setattr(akshara_preview,'visible',False), page.update())),
            ])
        ])

        # ── SCREEN 4: ASTRO CHART ────────────────────────────────────────────
        fld_date = make_field("Date (DD-MM-YYYY)", value=datetime.now().strftime("%d-%m-%Y"))
        fld_time = make_field("Time (HH:MM)", value=datetime.now().strftime("%H:%M"))
        fld_lat  = make_field("Latitude (Decimal)", value="19.076")
        fld_lon  = make_field("Longitude (Decimal)", value="72.877")
        astro_chart_container = ft.Column(spacing=15, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        def do_astro_close(e):
            astro_chart_container.controls.clear()
            page.update()

        def do_astro(e):
            try:
                dt = parse_dt(fld_date.value)
                tm = fld_time.value.strip().split(":")
                hh, mm = int(tm[0]), int(tm[1])
                lat, lon = float(fld_lat.value), float(fld_lon.value)
                jd = jd_ut_from_ist(dt.year, dt.month, dt.day, hh, mm)
                pos, ay = calc_planet_positions(jd, lat, lon)
                
                d1_pos = {p: lon_to_sign_deg(l)[0] for p, l in pos.items()}
                d9_pos = {p: d9_sign(l) for p, l in pos.items()}
                
                lagna_idx = d1_pos["As"]
                lagna_d9  = d9_pos["As"]
                retro_set = get_retrograde_set(jd, lat, lon)
                vargottama_set = {p for p in d1_pos if p != "As" and d1_pos.get(p) == d9_pos.get(p)}

                astro_chart_container.controls.clear()
                
                astro_chart_container.controls.append(ft.Text(
                    "✨ SIDEREAL AYANAMSA (LAHIRI): " + str(round(ay, 4)) + "°" +
                    ("   ⟲ Retrograde: " + ", ".join(sorted(retro_set)) if retro_set else "") +
                    ("   ★ Vargottama: " + ", ".join(sorted(vargottama_set)) if vargottama_set else ""),
                    size=13, color=C["primary"], weight="bold"))
                astro_chart_container.controls.append(build_dual_diamond_chart_with_bars(d1_pos, lagna_idx, d9_pos, lagna_d9, retro=retro_set, vargottama=vargottama_set))
                astro_chart_container.controls.append(ft.Container(height=8))
                astro_chart_container.controls.append(ft.ElevatedButton("✖  CLOSE CHARTS", bgcolor=C["red"], color="#FFFFFF", height=46, style=ft.ButtonStyle(text_style=ft.TextStyle(size=14, weight="bold")), on_click=do_astro_close))
                
                set_status("Charts Calculated Successfully!", C["green"])
            except Exception as ex:
                set_status(f"Error: {str(ex)}", C["red"])
            page.update()

        astro_screen = ft.Column(visible=False, controls=[
            make_header("🕉️ VEDIC KUNDALI ENGINES"), ft.Divider(height=4, color=C["divider"]),
            ft.Row([fld_date, fld_time]), ft.Row([fld_lat, fld_lon]),
            ft.ElevatedButton("🕉️ GENERATE NORTH INDIAN CHARTS", bgcolor=C["primary"], color="#FFFFFF", height=50, on_click=do_astro),
            ft.Divider(height=6, color=C["divider"]), astro_chart_container
        ])

        # ── SCREEN 5: DATABASE BUILD (STRICT HEADER-BASED PARSING) ─────
        def build_db_thread():
            try:
                set_status("Downloading NSE Data...", C["accent"])
                res = requests.get(NSE_URL, timeout=15)
                
                lines = res.text.splitlines()
                reader = csv.DictReader(lines)
                
                # कॉलम्स के नामों को क्लीन (Strip) कर रहे हैं ताकि कोई स्पेस न रहे
                reader.fieldnames = [f.strip().upper() for f in reader.fieldnames] if reader.fieldnames else []
                
                rows = list(reader)
                total = len(rows)
                
                if not reader.fieldnames or "SYMBOL" not in reader.fieldnames:
                    raise Exception("Invalid CSV Header structure from NSE.")

                conn = sqlite3.connect(db_path)
                for idx, row in enumerate(rows):
                    clean_row = {k.strip().upper(): v.strip() for k, v in row.items() if k}
                    
                    sym = clean_row.get("SYMBOL", "")
                    eng = clean_row.get("NAME OF COMPANY", "") or clean_row.get("COMPANY NAME", "")
                    series = clean_row.get("SERIES", "EQ")
                    
                    if series != "EQ" or not sym: 
                        continue
                    
                    # सीधे कॉलम के नाम "DATE OF LISTING" से तारीख उठाएगा
                    ldt = clean_row.get("DATE OF LISTING", "").strip()
                    
                    # सुरक्षा जांच: अगर तारीख की जगह गलती से ISIN नंबर या Face Value (जैसे 10) आ जाए
                    if "INE" in ldt or len(ldt) <= 4:
                        ldt = ""
                        for val in clean_row.values():
                            if "-" in val and not val.startswith("INE") and len(val) >= 9:
                                ldt = val
                                break
                    
                    hi = get_hindi(sym, eng)
                    if "LIMITED" in eng.upper() and not hi.endswith("लिमिटेड"):
                        hi = hi.replace("लिमिटेड", "").strip() + " लिमिटेड"
                    
                    asum, bk = calc(hi)
                    conn.execute("""INSERT INTO stocks(symbol,eng_name,hindi_name,ldate,asum,breakdown,series,portfolio)
                                    VALUES(?,?,?,?,?,?,?,0)
                                    ON CONFLICT(symbol) DO UPDATE SET
                                        eng_name=excluded.eng_name, hindi_name=excluded.hindi_name,
                                        ldate=excluded.ldate, asum=excluded.asum,
                                        breakdown=excluded.breakdown, series=excluded.series""",
                                 (sym, eng, hi, ldt, asum, bk, series))
                    
                    if idx % 10 == 0:
                        set_prg(idx/total, f"Processing {idx}/{total}: {sym}")
                        
                conn.commit()
                conn.close()
                hide_prg()
                set_status(f"Success! {db_count()} stocks loaded perfectly.", C["green"])
            except Exception as ex:
                hide_prg()
                set_status(f"Build failed: {str(ex)}", C["red"])

        db_screen = ft.Column(visible=False, controls=[
            make_header("⚙️ DATABASE AND ENGINE SETUP"), ft.Divider(height=4, color=C["divider"]),
            ft.ElevatedButton("⚡ BUILD AUTOMATED DATABASE", bgcolor=C["orange"], color="#FFFFFF", height=54, on_click=lambda e: threading.Thread(target=build_db_thread, daemon=True).start()),
            prg_bar, prg_txt
        ])

        # ── SCREEN 6: CUSTOM D1/D9 RULES ────────────────────────────────────
        PLANET_OPTS = ["ANY", "Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"]
        RASHI_NAMES = ["1=Aries", "2=Taurus", "3=Gemini", "4=Cancer", "5=Leo", "6=Virgo",
                       "7=Libra", "8=Scorpio", "9=Sagittarius", "10=Capricorn", "11=Aquarius", "12=Pisces"]
        fld_rule_type   = ft.Dropdown(label="Rule Type", value="D9_HOUSE",
                                        options=[ft.dropdown.Option(o) for o in ["D1_HOUSE", "D9_HOUSE", "D1_D9_COMPARE", "D1_D9_SAME_HOUSE", "D9_TO_D1_LIST", "D1_HOUSE_LIST", "VARGOTTAMA", "D1_RASHI", "D9_RASHI"]])
        fld_rule_planet = ft.Dropdown(label="Planet", value="ANY",
                                        options=[ft.dropdown.Option(o) for o in PLANET_OPTS])
        fld_rule_h1     = make_field("D1 House (1-12) OR D1 Rashi number", hint="HOUSE rules: house# counted from Lagna. RASHI rules: " + ", ".join(RASHI_NAMES[:4]) + "...")
        fld_rule_h9     = make_field("D9 House (1-12) OR D9 Rashi number", hint="Same numbering as above, applied to the D9 (Navamsha) chart")
        fld_rule_h1_list = make_field("D1 House LIST (D9_TO_D1_LIST or D1_HOUSE_LIST)", hint="Comma-separated house numbers, e.g. 4,5,9,10,11 — used for D9_TO_D1_LIST and D1_HOUSE_LIST rule types")
        fld_rule_companion_planet = ft.Dropdown(label="Companion Planet (optional AND condition)", value="",
                                        options=[ft.dropdown.Option("")] + [ft.dropdown.Option(o) for o in PLANET_OPTS[1:]])
        fld_rule_companion_h9 = make_field("Companion D9 House (optional)", hint="If set, this planet must ALSO be in this D9 house for the rule to fire — leave both blank if not needed")
        fld_rule_retro  = ft.Checkbox(label="Apply only when planet is Retrograde", value=False)
        fld_rule_signal = ft.Dropdown(label="Signal", value="BUY",
                                        options=[ft.dropdown.Option(o) for o in ["BUY", "SELL", "AVOID", "NEUTRAL"]])
        fld_rule_weight = make_field("Weight", value="1.0")
        fld_rule_note   = make_field("Note (optional)", hint="e.g. Jupiter own house — strength")

        rules_list_col = ft.Column(spacing=6)

        def refresh_rules_list():
            rules_list_col.controls.clear()
            rows = rule_list()
            if not rows:
                rules_list_col.controls.append(ft.Text("No custom rules yet. Add one above, or tap LOAD EXAMPLE RULES.", size=12, color=C["black_txt"]))
            for (rid, rtype, planet, hd1, hd9, hd1_list, comp_planet, comp_hd9, retro_only, signal, weight, note) in rows:
                sig_color = {"SELL": C["red"], "BUY": C["green"], "AVOID": "#212121"}.get(signal, C["black_txt"])
                label1 = "D1 Rashi" if rtype == "D1_RASHI" else "D1H"
                label2 = "D9 Rashi" if rtype == "D9_RASHI" else "D9H"
                if rtype == "D9_TO_D1_LIST":
                    desc = f"#{rid}  [{rtype}]  {planet}  D9H:{hd9 or '-'} → D1H in [{hd1_list or '-'}]  {'(Retro only)' if retro_only else ''}  → {signal} (w={weight})  {note or ''}"
                elif rtype == "D1_HOUSE_LIST":
                    desc = f"#{rid}  [{rtype}]  {planet}  D1H in [{hd1_list or '-'}]  {'(Retro only)' if retro_only else ''}  → {signal} (w={weight})  {note or ''}"
                else:
                    desc = f"#{rid}  [{rtype}]  {planet}  {label1}:{hd1 or '-'}  {label2}:{hd9 or '-'}  {'(Retro only)' if retro_only else ''}  → {signal} (w={weight})  {note or ''}"
                if comp_planet and comp_hd9:
                    desc += f"  AND {comp_planet} in D9H:{comp_hd9}"
                rules_list_col.controls.append(
                    ft.Row([
                        ft.Text(desc, size=12, color=sig_color, weight="bold" if signal == "AVOID" else None, expand=True),
                        ft.IconButton(icon=ft.Icons.DELETE, icon_color=C["red"], on_click=lambda e, rid=rid: do_delete_rule(rid))
                    ])
                )
            page.update()

        def do_delete_rule(rid):
            rule_delete(rid)
            set_status(f"Rule #{rid} deleted.", C["orange"])
            refresh_rules_list()

        def do_add_rule(e):
            try:
                h1 = int(fld_rule_h1.value) if fld_rule_h1.value and fld_rule_h1.value.strip() else None
                h9 = int(fld_rule_h9.value) if fld_rule_h9.value and fld_rule_h9.value.strip() else None
                w  = float(fld_rule_weight.value) if fld_rule_weight.value and fld_rule_weight.value.strip() else 1.0
                h1_list_raw = (fld_rule_h1_list.value or "").strip()
                comp_planet_raw = (fld_rule_companion_planet.value or "").strip() or None
                comp_h9_raw = int(fld_rule_companion_h9.value) if fld_rule_companion_h9.value and fld_rule_companion_h9.value.strip() else None
                if h1 is not None and not (1 <= h1 <= 12): raise ValueError("D1 field must be 1-12 (house# from Lagna, or 1-12=Aries..Pisces for a RASHI rule)")
                if h9 is not None and not (1 <= h9 <= 12): raise ValueError("D9 field must be 1-12 (house# from Lagna, or 1-12=Aries..Pisces for a RASHI rule)")
                if comp_h9_raw is not None and not (1 <= comp_h9_raw <= 12): raise ValueError("Companion D9 House must be 1-12")
                if (comp_planet_raw and not comp_h9_raw) or (comp_h9_raw and not comp_planet_raw):
                    raise ValueError("Companion condition needs BOTH the planet AND the D9 house filled in — or leave both blank")
                if fld_rule_type.value == "D9_TO_D1_LIST":
                    if h9 is None: raise ValueError("D9_TO_D1_LIST needs the D9 House field filled in (the fixed D9 house)")
                    if not h1_list_raw: raise ValueError("D9_TO_D1_LIST needs the D1 House LIST field filled in, e.g. 4,5,10,11")
                    parsed = [int(x.strip()) for x in h1_list_raw.split(",") if x.strip()]
                    if not all(1 <= n <= 12 for n in parsed): raise ValueError("Every number in the D1 House LIST must be 1-12")
                    h1_list_raw = ",".join(str(n) for n in parsed)  # normalized
                elif fld_rule_type.value == "D1_HOUSE_LIST":
                    if not h1_list_raw: raise ValueError("D1_HOUSE_LIST needs the D1 House LIST field filled in, e.g. 4,5,9,10,11")
                    parsed = [int(x.strip()) for x in h1_list_raw.split(",") if x.strip()]
                    if not all(1 <= n <= 12 for n in parsed): raise ValueError("Every number in the D1 House LIST must be 1-12")
                    h1_list_raw = ",".join(str(n) for n in parsed)  # normalized
                else:
                    h1_list_raw = None
                rule_add(fld_rule_type.value, fld_rule_planet.value, h1, h9, fld_rule_retro.value, fld_rule_signal.value, w, fld_rule_note.value,
                         house_d1_list=h1_list_raw, companion_planet=comp_planet_raw, companion_house_d9=comp_h9_raw)
                set_status("Rule added.", C["green"])
                fld_rule_h1.value = ""; fld_rule_h9.value = ""; fld_rule_h1_list.value = ""
                fld_rule_companion_planet.value = ""; fld_rule_companion_h9.value = ""; fld_rule_note.value = ""
                refresh_rules_list()
            except Exception as ex:
                set_status(f"Rule error: {str(ex)}", C["red"])
                page.update()

        EXAMPLE_RULE_PACK = [
            # (rule_type, planet, house_d1, house_d9, retro_only, signal, weight, note, house_d1_list, companion_planet, companion_house_d9)
            ("D1_HOUSE",      "Ju", 11, None, 0, "BUY",  2.0, "Jupiter in D1 11th house from Lagna — gains/profits house", None, None, None),
            ("D9_HOUSE",      "Ju", None, 11, 0, "BUY",  2.0, "Jupiter in D9 11th house — navamsha confirms gains", None, None, None),
            ("D1_D9_COMPARE", "Ju", 11, 11,   0, "BUY",  3.0, "Jupiter strong in BOTH D1 & D9 11th — very strong bullish confirmation", None, None, None),
            ("D1_D9_SAME_HOUSE", "Ju", None, None, 0, "BUY", 2.0, "Jupiter holds the SAME house number in both D1 & D9 (whatever that house is) — consistent placement, generally strengthens Jupiter's result either way", None, None, None),
            ("D1_D9_SAME_HOUSE", "ANY", None, None, 0, "NEUTRAL", 0.5, "ANY planet with matching D1/D9 house — logged for reference, doesn't move the score by default; raise the weight/change signal once you've tested this yourself", None, None, None),
            ("D9_TO_D1_LIST", "ANY", None, 2, 0, "AVOID", 1.0, "D9 2nd house planet whose D1 house is 1,2,3,6,7,8, or 12 — avoid buy or sell en
