import os
import re
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

        # ── QUICK RULE — ONE-LINE STRING FORMAT ─────────────────────────────
        # A single, uniform text grammar that can express EVERY one of the 10
        # rule_type values above, so a user never has to pick a rule_type by
        # name — they just type one line. parse_quick_rule() turns that line
        # into the exact same fields rule_add() already takes; quick_rule_string()
        # does the reverse, so every existing/example rule can also be shown in
        # this shorthand (learn-by-example). Nothing about evaluate_rules() or
        # the DB schema changes — this is purely an alternate way to fill the
        # same fields.
        #
        # GRAMMAR (case-insensitive, spaces optional inside a condition):
        #   <PLANET> <CONDITION> [RETRO] [+<PLANET>@D9H<n>] => <SIGNAL> [wt=<n>] [note="..."]
        #
        # PLANET     Su Mo Ma Me Ju Ve Sa Ra Ke  or  ANY
        # CONDITION  (pick exactly one)
        #   D1H<n>               planet's D1 house = n                   -> D1_HOUSE
        #   D9H<n>               planet's D9 house = n                   -> D9_HOUSE
        #   D1R<n>               planet's D1 RASHI (sign) = n            -> D1_RASHI
        #   D9R<n>               planet's D9 RASHI (sign) = n            -> D9_RASHI
        #   VG                   Vargottama (same rashi in D1 and D9)    -> VARGOTTAMA
        #   D1H<n>=D9H<n2>       D1 house n AND D9 house n2, together    -> D1_D9_COMPARE
        #   D1H=D9H              D1 house equals D9 house (any number)   -> D1_D9_SAME_HOUSE
        #   D9H<n>~ASPECT        this D9 house is ASPECTED by the planet -> D9_HOUSE_ASPECT
        #   D9H<n>->D1H[list]    fixed D9 house n, that planet's D1 house is in the list -> D9_TO_D1_LIST
        #   D1H[list]            D1 house is anywhere in the list (no D9 pin) -> D1_HOUSE_LIST
        # RETRO        optional — only fires when the planet is retrograde
        # +<PL>@D9H<n> optional Companion Condition — <PL> must ALSO be in D9 house n
        # SIGNAL       BUY | SELL | AVOID | NEUTRAL
        # wt=<n>       optional weight (default 1.0)
        # note="..."   optional note text
        #
        # Worked example (matches the user's own question — "D9 house 2's rashi
        # exists in D1 house 4,5,9,10,11"):
        #   Mo D9H2->D1H[4,5,9,10,11] => BUY
        QUICK_RULE_HELP = (
            'Mo D9H2->D1H[4,5,9,10,11] => BUY\n'
            'Sa D9H7 RETRO => AVOID\n'
            'Ju VG => BUY  wt=2 note="Jupiter vargottama"\n'
            'ANY D9H11~ASPECT => BUY\n'
            'Ma D1R1 => BUY   (Mars in Aries rashi, D1)\n'
            'ANY D9H2->D1H[2,3,6,7,8,12] +Sa@D9H7 => AVOID'
        )

        def parse_quick_rule(text):
            """Parse one QUICK RULE line into the fields rule_add() expects.
            Raises ValueError with a plain-English message on anything it can't parse."""
            if not text or not text.strip():
                raise ValueError("Type a rule first, e.g.  Mo D9H2->D1H[4,5,9,10,11] => BUY")
            raw = text.strip()

            note = None
            m = re.search(r'note\s*=\s*"([^"]*)"', raw, re.IGNORECASE)
            if m:
                note = m.group(1)
                raw = raw[:m.start()] + raw[m.end():]

            weight = 1.0
            m = re.search(r'\bwt\s*=\s*([\-0-9.]+)', raw, re.IGNORECASE)
            if m:
                try:
                    weight = float(m.group(1))
                except ValueError:
                    raise ValueError(f'wt= must be a number, got "{m.group(1)}"')
                raw = raw[:m.start()] + raw[m.end():]

            if "=>" not in raw:
                raise ValueError('Missing "=>". Format:  <planet> <condition> => <SIGNAL>   e.g.  Mo D9H2 => BUY')
            left, right = raw.split("=>", 1)
            right = right.strip()
            signal = right.split()[0].upper() if right else ""
            if signal not in ("BUY", "SELL", "AVOID", "NEUTRAL"):
                raise ValueError(f'Signal after "=>" must be BUY / SELL / AVOID / NEUTRAL — got "{signal or "(nothing)"}"')

            left = left.strip()
            retro = bool(re.search(r'\bRETRO\b', left, re.IGNORECASE))
            left = re.sub(r'\bRETRO\b', '', left, flags=re.IGNORECASE)

            comp_planet, comp_h9 = None, None
            m = re.search(r'\+\s*([A-Za-z]{2})\s*@\s*D9H\s*(\d{1,2})', left, re.IGNORECASE)
            if m:
                comp_planet = m.group(1).capitalize()
                comp_h9 = int(m.group(2))
                left = left[:m.start()] + left[m.end():]

            tokens = left.split()
            if not tokens:
                raise ValueError("Missing planet and condition before '=>'.")
            planet = tokens[0].strip()
            planet = "ANY" if planet.upper() == "ANY" else planet.capitalize()
            valid_planets = {"ANY", "Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"}
            if planet not in valid_planets:
                raise ValueError(f'Unknown planet "{tokens[0]}". Use one of: {", ".join(sorted(valid_planets))}')

            cond = "".join(tokens[1:]).strip()
            if not cond:
                raise ValueError("Missing condition, e.g. D9H2, D1H[4,5,9], VG, D1R9, D9H11~ASPECT ...")

            rule_type = None
            h1 = h9 = None
            h1_list = None

            def _int_grp(pattern, s):
                mm = re.fullmatch(pattern, s, re.IGNORECASE)
                return mm

            if cond.upper() == "VG":
                rule_type = "VARGOTTAMA"
            elif cond.upper() == "D1H=D9H":
                rule_type = "D1_D9_SAME_HOUSE"
            elif _int_grp(r'D9H(\d{1,2})~ASPECT', cond):
                h9 = int(_int_grp(r'D9H(\d{1,2})~ASPECT', cond).group(1)); rule_type = "D9_HOUSE_ASPECT"
            elif _int_grp(r'D9H(\d{1,2})->D1H\[([0-9,]+)\]', cond):
                mm = _int_grp(r'D9H(\d{1,2})->D1H\[([0-9,]+)\]', cond)
                h9 = int(mm.group(1)); h1_list = mm.group(2); rule_type = "D9_TO_D1_LIST"
            elif _int_grp(r'D1H\[([0-9,]+)\]', cond):
                h1_list = _int_grp(r'D1H\[([0-9,]+)\]', cond).group(1); rule_type = "D1_HOUSE_LIST"
            elif _int_grp(r'D1H(\d{1,2})=D9H(\d{1,2})', cond):
                mm = _int_grp(r'D1H(\d{1,2})=D9H(\d{1,2})', cond)
                h1 = int(mm.group(1)); h9 = int(mm.group(2)); rule_type = "D1_D9_COMPARE"
            elif _int_grp(r'D1H(\d{1,2})', cond):
                h1 = int(_int_grp(r'D1H(\d{1,2})', cond).group(1)); rule_type = "D1_HOUSE"
            elif _int_grp(r'D9H(\d{1,2})', cond):
                h9 = int(_int_grp(r'D9H(\d{1,2})', cond).group(1)); rule_type = "D9_HOUSE"
            elif _int_grp(r'D1R(\d{1,2})', cond):
                h1 = int(_int_grp(r'D1R(\d{1,2})', cond).group(1)); rule_type = "D1_RASHI"
            elif _int_grp(r'D9R(\d{1,2})', cond):
                h9 = int(_int_grp(r'D9R(\d{1,2})', cond).group(1)); rule_type = "D9_RASHI"
            else:
                raise ValueError(f'Could not understand condition "{cond}". See the cheat-sheet under the Quick Rule box.')

            for label, val in (("D1 house/rashi", h1), ("D9 house/rashi", h9)):
                if val is not None and not (1 <= val <= 12):
                    raise ValueError(f"{label} number must be 1-12, got {val}.")
            if comp_h9 is not None and not (1 <= comp_h9 <= 12):
                raise ValueError("Companion D9 house must be 1-12.")
            if h1_list:
                try:
                    nums = [int(x.strip()) for x in h1_list.split(",") if x.strip()]
                except ValueError:
                    raise ValueError("House list must be comma-separated numbers, e.g. [4,5,9,10,11].")
                if not nums or any(not (1 <= n <= 12) for n in nums):
                    raise ValueError("Every number in the house list must be 1-12.")
                h1_list = ",".join(str(n) for n in nums)

            return {
                "rule_type": rule_type, "planet": planet, "house_d1": h1, "house_d9": h9,
                "house_d1_list": h1_list, "companion_planet": comp_planet, "companion_house_d9": comp_h9,
                "retro_only": retro, "signal": signal, "weight": weight, "note": note,
            }

        def quick_rule_string(rtype, planet, hd1, hd9, hd1_list, comp_planet, comp_hd9, retro_only, signal, weight, note):
            """Reverse of parse_quick_rule() — renders any stored rule row back into the
            one-line shorthand, so existing/example rules double as worked examples."""
            if rtype == "D1_HOUSE": cond = f"D1H{hd1}"
            elif rtype == "D9_HOUSE": cond = f"D9H{hd9}"
            elif rtype == "D1_RASHI": cond = f"D1R{hd1}"
            elif rtype == "D9_RASHI": cond = f"D9R{hd9}"
            elif rtype == "VARGOTTAMA": cond = "VG"
            elif rtype == "D1_D9_COMPARE": cond = f"D1H{hd1}=D9H{hd9}"
            elif rtype == "D1_D9_SAME_HOUSE": cond = "D1H=D9H"
            elif rtype == "D9_HOUSE_ASPECT": cond = f"D9H{hd9}~ASPECT"
            elif rtype == "D9_TO_D1_LIST": cond = f"D9H{hd9}->D1H[{hd1_list}]"
            elif rtype == "D1_HOUSE_LIST": cond = f"D1H[{hd1_list}]"
            else: cond = rtype
            s = f"{planet} {cond}"
            if retro_only: s += " RETRO"
            if comp_planet and comp_hd9: s += f" +{comp_planet}@D9H{comp_hd9}"
            s += f" => {signal}"
            try:
                if float(weight) != 1.0: s += f" wt={float(weight):g}"
            except (TypeError, ValueError):
                pass
            if note: s += f' note="{note}"'
            return s

        def get_house_num(sign_idx, lagna_sign_idx):
            """Convert a raw sign index (0-11) to a house number (1-12) relative to the lagna."""
            return ((int(sign_idx) - int(lagna_sign_idx)) % 12) + 1

        # Classical Parashari drishti (aspect) rules: EVERY planet aspects the 7th house
        # from its own position. Mars/Jupiter/Saturn also cast special extra aspects.
        # Rahu/Ketu have no single agreed classical aspect scheme — by common modern
        # convention this app treats them like Saturn (3rd/7th/10th), noted honestly here
        # rather than presented as ancient doctrine.
        ASPECT_EXTRA_HOUSES = {"Ma": [4, 8], "Ju": [5, 9], "Sa": [3, 10], "Ra": [3, 10], "Ke": [3, 10]}

        def planet_aspect_houses(planet_key, house_pos):
            """Houses (1-12) aspected by a planet currently sitting in house_pos."""
            offsets = [7] + ASPECT_EXTRA_HOUSES.get(planet_key, [])
            return {((int(house_pos) - 1 + (off - 1)) % 12) + 1 for off in offsets}

        def apply_timing_flag(score, avoid_matches):
            """Shared GOOD/BAD-timing flag shown at the very top of the Stocks/Show All
            page — same custom-rules verdict (score + AVOID matches) that CALCULATE ASTRO
            and the Live Timing Signal below use, so all three always agree."""
            if avoid_matches:
                top_timing_text.value = "🔴 BAD TIMING — AVOID TRADING TODAY  (custom AVOID rule matched)"
                top_timing_flag_container.bgcolor = C["red"]
            elif score > 0:
                top_timing_text.value = f"🟢 GOOD TIMING — GO FOR TRADE  (score {score:+.1f})"
                top_timing_flag_container.bgcolor = C["green"]
            elif score < 0:
                top_timing_text.value = f"🔴 BAD TIMING — AVOID TRADING  (score {score:+.1f})"
                top_timing_flag_container.bgcolor = C["red"]
            else:
                top_timing_text.value = "⚪ NEUTRAL — NO STRONG SIGNAL, TRADE WITH CAUTION"
                top_timing_flag_container.bgcolor = C["hint_txt"]
            page.update()

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
                    elif rtype == "D9_HOUSE_ASPECT" and houses_d9.get(pl) is not None and hd9 in planet_aspect_houses(pl, houses_d9.get(pl)):
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
                apply_timing_flag(score, avoid_matches)  # keep the top-of-page flag in sync
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
                oracle_astro_container.controls.append(ft.ElevatedButton("⬅  CLOSE ASTRO CHART", bgcolor=C["primary"], color="#FFFFFF", height=46, style=ft.ButtonStyle(text_style=ft.TextStyle(size=14, weight="bold")), on_click=do_oracle_back))
                oracle_astro_container.visible = True
            except Exception as aex:
                oracle_astro_container.controls.clear()
                oracle_astro_container.controls.append(ft.Text(f"Astro chart error: {str(aex)}", size=13, color=C["red"]))
                oracle_astro_container.controls.append(ft.ElevatedButton("⬅  CLOSE ASTRO CHART", bgcolor=C["primary"], color="#FFFFFF", height=46, on_click=do_oracle_back))
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
            ft.Text("🪐 Auto Astro (D1/D9) has moved to the Stocks / Show All page — tap the Stocks tab below.", size=12, color=C["hint_txt"]),
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

        # ── TOP-OF-PAGE GOOD/BAD TIMING FLAG ───────────────────────────────
        # A single green/red headline flag, always the first thing on this page — tells
        # you at a glance whether right now is good or bad timing to trade, per your
        # custom Rules. Kept in sync by CALCULATE ASTRO below and by Auto Refresh.
        top_timing_text = ft.Text("⏳ TIMING: tap CALCULATE ASTRO below, or start Auto Refresh, to check now",
                                    size=15, weight="bold", color="#FFFFFF")
        top_timing_flag_container = ft.Container(
            content=top_timing_text, bgcolor=C["hint_txt"], padding=14, border_radius=8, alignment=ft.alignment.center
        )

        # ── LIVE TIMING SIGNAL (Auto Refresh) ─────────────────────────────
        # Your custom Rules (evaluate_rules) check the current sky right now, not any one
        # stock's identity — so this is ONE market-timing signal shared by every stock at a
        # given moment, not per-row. Shown here as a static banner, refreshed on the
        # interval you set (no blinking — a fixed-interval color swap is enough to notice a
        # change, and it avoids the constant background redraw that a blinking timer causes).
        stocks_auto_state = {"running": False, "stop_event": None}
        fld_stocks_auto_interval = make_field("Auto Refresh Interval (minutes)", value="5")
        live_signal_text = ft.Text("⏱ LIVE TIMING SIGNAL: OFF", size=14, weight="bold", color="#FFFFFF")
        live_signal_container = ft.Container(
            content=live_signal_text, bgcolor=C["hint_txt"], padding=12, border_radius=8, alignment=ft.alignment.center
        )

        def compute_live_timing_signal():
            """Runs your custom Rules against the sky right now (same engine as this page's
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
                return "AVOID", "#212121", score, avoid_matches
            elif score > 0:
                return "BUY", C["green"], score, avoid_matches
            elif score < 0:
                return "SELL", C["red"], score, avoid_matches
            else:
                return "NEUTRAL", C["accent"], score, avoid_matches

        def stocks_recalc_loop(interval_seconds, stop_event):
            while not stop_event.is_set():
                label, color, score, avoid_matches = compute_live_timing_signal()
                live_signal_text.value = f"⏱ LIVE TIMING SIGNAL: {label}"
                live_signal_container.bgcolor = color
                live_signal_text.color = "#FFFFFF"
                apply_timing_flag(score, avoid_matches)
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
            top_timing_flag_container,
            make_header("📋 STOCK LIST (NSE India)"), ft.Divider(height=4, color=C["divider"]),
            ft.ElevatedButton("⬅  BACK TO ORACLE", bgcolor=C["primary"], color="#FFFFFF", height=44, on_click=lambda e: show_screen("oracle")),
            price_popup,
            ft.Divider(height=4, color=C["divider"]),
            ft.Text("🪐 AUTO ASTRO (D1/D9) — calculates the current-sky Vedic chart and runs your custom Rules against it, right here.", size=11, color=C["black_txt"]),
            ft.ElevatedButton("🪐  CALCULATE ASTRO (D1 / D9)", bgcolor=C["primary"], color="#FFFFFF", height=48, style=ft.ButtonStyle(text_style=ft.TextStyle(size=15, weight="bold")), on_click=do_oracle_astro),
            oracle_astro_container,
            ft.Divider(height=4, color=C["divider"]),
            ft.Text("⏱ LIVE TIMING SIGNAL — your custom Rules checked against the sky right now (one shared signal for all stocks, not per-row); updates every refresh interval", size=10, color=C["hint_txt"]),
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
                                        options=[ft.dropdown.Option(o) for o in ["D1_HOUSE", "D9_HOUSE", "D9_HOUSE_ASPECT", "D1_D9_COMPARE", "D1_D9_SAME_HOUSE", "D9_TO_D1_LIST", "D1_HOUSE_LIST", "VARGOTTAMA", "D1_RASHI", "D9_RASHI"]])
        fld_rule_planet = ft.Dropdown(label="Planet", value="ANY",
                                        options=[ft.dropdown.Option(o) for o in PLANET_OPTS])
        fld_rule_h1     = make_field("D1 House (1-12) OR D1 Rashi number", hint="HOUSE rules: house# counted from Lagna. RASHI rules: " + ", ".join(RASHI_NAMES[:4]) + "...")
        fld_rule_h9     = make_field("D9 House (1-12) OR D9 Rashi number", hint="D9_HOUSE_ASPECT: enter the D9 house being ASPECTED (Planet field = the aspecting planet, or ANY). Other rules: same numbering as D1, applied to the D9 (Navamsha) chart")
        fld_rule_h1_list = make_field("D1 House LIST (D9_TO_D1_LIST or D1_HOUSE_LIST)", hint="Comma-separated house numbers, e.g. 4,5,9,10,11 — used for D9_TO_D1_LIST (needs a fixed D9 House too) and D1_HOUSE_LIST (no D9 House needed, fully general)")
        fld_rule_companion_planet = ft.Dropdown(label="Companion Planet (optional AND condition)", value="",
                                        options=[ft.dropdown.Option("")] + [ft.dropdown.Option(o) for o in PLANET_OPTS[1:]])
        fld_rule_companion_h9 = make_field("Companion D9 House (optional)", hint="If set, this planet must ALSO be in this D9 house for the rule to fire — leave both blank if not needed")
        fld_rule_retro  = ft.Checkbox(label="Apply only when planet is Retrograde", value=False)
        fld_rule_signal = ft.Dropdown(label="Signal", value="BUY",
                                        options=[ft.dropdown.Option(o) for o in ["BUY", "SELL", "AVOID", "NEUTRAL"]])
        fld_rule_weight = make_field("Weight", value="1.0")
        fld_rule_note   = make_field("Note (optional)", hint="e.g. Jupiter own house — strength")

        # ── SIMPLE RULE WIZARD — describe D1 and D9 in plain words, and this picks
        # the correct technical Rule Type above for you. Doesn't change the engine at
        # all — it just fills in the same Rule Type dropdown you'd otherwise have to
        # choose manually from 10 cryptic names.
        D1_MODE_OPTS = [
            "Not used", "Specific House number", "House is one of a List", "Specific Rashi (sign)",
        ]
        D9_MODE_OPTS = [
            "Not used", "Specific House number", "House is one of a List", "Specific Rashi (sign)",
            "Same House as D1 (any house)", "Same Rashi as D1 (Vargottama)", "This house is ASPECTED by the planet",
        ]
        fld_d1_mode = ft.Dropdown(label="What does D1 mean here?", value="Not used",
                                   options=[ft.dropdown.Option(o) for o in D1_MODE_OPTS])
        fld_d9_mode = ft.Dropdown(label="What does D9 mean here?", value="Specific House number",
                                   options=[ft.dropdown.Option(o) for o in D9_MODE_OPTS])
        wizard_status_txt = ft.Text("", size=12, color=C["black_txt"])

        # ── QUICK RULE UI — the one-line box described above, this is the
        # fastest path in: type the whole rule (planet + D1/D9 house-or-rashi
        # + signal, with optional list/vargottama/aspect/retro/companion) as a
        # single line of text and tap ADD. Uses parse_quick_rule() only — it
        # writes to the exact same planet_rules table via rule_add().
        fld_quick_rule = ft.TextField(
            label="⚡ QUICK RULE — type the whole rule as ONE line",
            hint_text="Mo D9H2->D1H[4,5,9,10,11] => BUY",
            multiline=False
        )
        quick_rule_status_txt = ft.Text("", size=12, color=C["black_txt"])
        quick_rule_cheatsheet = ft.Text(
            "FORMAT:  <planet> <condition> => <SIGNAL>   [RETRO]  [+<planet>@D9H<n>]  [wt=<n>]  [note=\"...\"]\n"
            "planet: Su Mo Ma Me Ju Ve Sa Ra Ke or ANY\n"
            "D1H<n> / D9H<n> = planet's house is n (1-12, counted from Lagna)\n"
            "D1R<n> / D9R<n> = planet's RASHI (sign) is n (1=Aries...12=Pisces)\n"
            "VG = Vargottama (same rashi in D1 and D9)\n"
            "D1H<n>=D9H<n2> = D1 house n AND D9 house n2 together\n"
            "D1H=D9H = D1 house equals D9 house (any number)\n"
            "D9H<n>~ASPECT = this D9 house is aspected by the planet\n"
            "D9H<n>->D1H[list] = fixed D9 house n, planet's D1 house is in the list\n"
            "D1H[list] = D1 house is anywhere in the list (no D9 house pinned)\n"
            "SIGNAL: BUY / SELL / AVOID / NEUTRAL\n"
            "Examples:\n" + QUICK_RULE_HELP,
            size=10, color=C["hint_txt"]
        )

        def do_auto_select_rule_type(e):
            d1, d9 = fld_d1_mode.value, fld_d9_mode.value
            mapping = {
                ("Not used", "Specific House number"): "D9_HOUSE",
                ("Not used", "This house is ASPECTED by the planet"): "D9_HOUSE_ASPECT",
                ("Not used", "Same House as D1 (any house)"): "D1_D9_SAME_HOUSE",
                ("Not used", "Same Rashi as D1 (Vargottama)"): "VARGOTTAMA",
                ("Not used", "Specific Rashi (sign)"): "D9_RASHI",
                ("Specific House number", "Not used"): "D1_HOUSE",
                ("Specific Rashi (sign)", "Not used"): "D1_RASHI",
                ("House is one of a List", "Not used"): "D1_HOUSE_LIST",
                ("House is one of a List", "Specific House number"): "D9_TO_D1_LIST",
                ("Specific House number", "Specific House number"): "D1_D9_COMPARE",
            }
            derived = mapping.get((d1, d9))
            if derived is None:
                wizard_status_txt.value = "⚠️ That combination isn't directly supported yet. Try: leave one side as 'Not used', or use House-List on the D1 side with a fixed D9 House."
                wizard_status_txt.color = C["red"]
                page.update()
                return
            fld_rule_type.value = derived
            wizard_status_txt.value = f"✅ Rule Type set to: {derived} — now fill in the house/rashi/list value(s) below and tap ADD RULE."
            wizard_status_txt.color = C["green"]
            page.update()

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
                elif rtype == "D9_HOUSE_ASPECT":
                    desc = f"#{rid}  [{rtype}]  {planet} aspecting D9H:{hd9 or '-'}  {'(Retro only)' if retro_only else ''}  → {signal} (w={weight})  {note or ''}"
                else:
                    desc = f"#{rid}  [{rtype}]  {planet}  {label1}:{hd1 or '-'}  {label2}:{hd9 or '-'}  {'(Retro only)' if retro_only else ''}  → {signal} (w={weight})  {note or ''}"
                if comp_planet and comp_hd9:
                    desc += f"  AND {comp_planet} in D9H:{comp_hd9}"
                try:
                    desc += f"\n     ⚡ {quick_rule_string(rtype, planet, hd1, hd9, hd1_list, comp_planet, comp_hd9, retro_only, signal, weight, note)}"
                except Exception:
                    pass  # never let a display-only formatting issue block the rules list
                # GO / NO-TRADE flag — green for BUY (go for trade), red for SELL/AVOID
                # (not to trade), grey for NEUTRAL rules kept only for reference.
                if signal == "BUY":
                    flag_color, flag_label = C["green"], "GO"
                elif signal in ("SELL", "AVOID"):
                    flag_color, flag_label = C["red"], "NO-TRADE"
                else:
                    flag_color, flag_label = C["hint_txt"], "NEUTRAL"
                flag_badge = ft.Container(
                    content=ft.Text(flag_label, size=10, color="#FFFFFF", weight="bold"),
                    bgcolor=flag_color, padding=ft.padding.symmetric(horizontal=6, vertical=3), border_radius=4
                )
                rules_list_col.controls.append(
                    ft.Row([
                        flag_badge,
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
                if fld_rule_type.value == "D9_HOUSE_ASPECT" and h9 is None:
                    raise ValueError("D9_HOUSE_ASPECT needs the D9 House field filled in (the house being ASPECTED)")
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

        def do_add_quick_rule(e):
            try:
                parsed = parse_quick_rule(fld_quick_rule.value)
                rule_add(parsed["rule_type"], parsed["planet"], parsed["house_d1"], parsed["house_d9"],
                         parsed["retro_only"], parsed["signal"], parsed["weight"], parsed["note"],
                         house_d1_list=parsed["house_d1_list"], companion_planet=parsed["companion_planet"],
                         companion_house_d9=parsed["companion_house_d9"])
                quick_rule_status_txt.value = f"✅ Rule added  (stored as {parsed['rule_type']})"
                quick_rule_status_txt.color = C["green"]
                set_status("Quick rule added.", C["green"])
                fld_quick_rule.value = ""
                refresh_rules_list()
            except Exception as ex:
                quick_rule_status_txt.value = f"⚠️ {str(ex)}"
                quick_rule_status_txt.color = C["red"]
                page.update()

        EXAMPLE_RULE_PACK = [
            # (rule_type, planet, house_d1, house_d9, retro_only, signal, weight, note, house_d1_list, companion_planet, companion_house_d9)

            # ── GROUP 1: Kendra/Trikona (1,4,5,7,9,10,11) benefic placements ──────
            ("D1_HOUSE",      "Ju", 11, None, 0, "BUY",  2.0, "Jupiter in D1 11th house from Lagna — gains/profits house", None, None, None),
            ("D9_HOUSE",      "Ju", None, 11, 0, "BUY",  2.0, "Jupiter in D9 11th house — navamsha confirms gains", None, None, None),
            ("D1_HOUSE",      "Ve", 2,  None, 0, "BUY",  1.5, "Venus D1 2nd house — wealth/liquidity", None, None, None),
            ("D1_HOUSE",      "Mo", 4,  None, 0, "BUY",  1.0, "Moon D1 4th house — public sentiment/liquidity comfortable", None, None, None),
            ("D1_HOUSE",      "Su", 10, None, 0, "BUY",  1.0, "Sun D1 10th house — leadership/PSU strength", None, None, None),

            # ── GROUP 2: Dusthana (6,8,12) malefic/caution placements ──────────
            ("D1_HOUSE",      "Ma", 8,  None, 0, "SELL", 2.0, "Mars D1 8th house — classic sudden-crash placement", None, None, None),
            ("D1_HOUSE",      "Ma", 8,  None, 1, "AVOID", 1.0, "Mars RETROGRADE in D1 8th — high-risk combination, sit this one out entirely", None, None, None),
            ("D1_HOUSE",      "Sa", 6,  None, 0, "SELL", 1.5, "Saturn D1 6th house — debt/obstacle pressure", None, None, None),
            ("D1_HOUSE",      "Sa", 8,  None, 1, "SELL", 1.5, "Saturn retrograde D1 8th house — prolonged structural correction", None, None, None),
            ("D1_HOUSE",      "Ke", 12, None, 0, "SELL", 1.5, "Ketu D1 12th house — losses/isolation", None, None, None),
            ("D9_HOUSE",      "Sa", None, 7, 0, "AVOID", 1.0, "Saturn in D9 7th house — avoid trading (buy or sell) entirely", None, None, None),

            # ── GROUP 3: Planetary dignity — exaltation / debilitation / own-sign ──
            # These are classical Vedic fundamentals (not market-specific folklore): a
            # planet in its exaltation sign gives its best results, debilitation its
            # weakest, own sign a comfortable/stable result. D1_RASHI/D9_RASHI use the
            # absolute rashi number (1=Aries...12=Pisces), independent of house/Lagna.
            ("D1_RASHI",      "Ju", 4,  None, 0, "BUY",  2.5, "Jupiter EXALTED in Cancer (#4) in D1 — best possible Jupiter result", None, None, None),
            ("D9_RASHI",      "Ju", None, 4,  0, "BUY",  2.5, "Jupiter EXALTED in Cancer (#4) in D9 — navamsha confirms peak strength", None, None, None),
            ("D1_RASHI",      "Ju", 10, None, 0, "SELL", 1.5, "Jupiter DEBILITATED in Capricorn (#10) in D1 — weakest Jupiter result", None, None, None),
            ("D1_RASHI",      "Ve", 12, None, 0, "BUY",  2.0, "Venus EXALTED in Pisces (#12) in D1 — finance/luxury sector at its best", None, None, None),
            ("D1_RASHI",      "Ve", 6,  None, 0, "SELL", 1.0, "Venus DEBILITATED in Virgo (#6) in D1", None, None, None),
            ("D1_RASHI",      "Mo", 2,  None, 0, "BUY",  1.5, "Moon EXALTED in Taurus (#2) in D1 — strong public sentiment/liquidity", None, None, None),
            ("D1_RASHI",      "Mo", 8,  None, 0, "SELL", 1.0, "Moon DEBILITATED in Scorpio (#8) in D1 — shaky sentiment", None, None, None),
            ("D1_RASHI",      "Su", 1,  None, 0, "BUY",  1.0, "Sun EXALTED in Aries (#1) in D1 — leadership/PSU sector strong", None, None, None),
            ("D1_RASHI",      "Sa", 7,  None, 0, "BUY",  1.0, "Saturn EXALTED in Libra (#7) in D1 — old-economy/structure sector stable", None, None, None),
            ("D1_RASHI",      "Sa", 1,  None, 0, "SELL", 1.5, "Saturn DEBILITATED in Aries (#1) in D1", None, None, None),
            ("D9_RASHI",      "Ve", 7,  None, 0, "BUY",  1.5, "Venus OWN SIGN Libra (#7) in D9 — strong finance/luxury signification in navamsha", None, None, None),
            ("D1_RASHI",      "Ju", 9,  None, 0, "BUY",  1.5, "Jupiter OWN SIGN Sagittarius (#9) in D1 — own-sign strength, regardless of house", None, None, None),

            # ── GROUP 4: Vargottama (D1 rashi = D9 rashi) ───────────────────────
            ("VARGOTTAMA",    "Ju", None, None, 0, "BUY", 3.0, "Jupiter Vargottama (same rashi in D1 & D9) — amplified benefic strength", None, None, None),
            ("VARGOTTAMA",    "Sa", None, None, 0, "SELL", 1.5, "Saturn Vargottama — amplified malefic pressure, whatever house it's in", None, None, None),

            # ── GROUP 5: Retrograde ──────────────────────────────────────────
            ("D9_HOUSE",      "Me", 3,  None, 1, "SELL", 2.0, "Mercury retrograde in D9 3rd house — trade/communication volatility", None, None, None),

            # ── GROUP 6: House-position consistency across D1 and D9 ───────────
            ("D1_D9_COMPARE", "Ju", 11, 11,   0, "BUY",  3.0, "Jupiter strong in BOTH D1 & D9 11th — very strong bullish confirmation", None, None, None),
            ("D1_D9_COMPARE", "Sa", 8,  8,    1, "AVOID", 1.0, "Saturn retrograde AND afflicted in BOTH D1 & D9 8th house — strong caution, avoid new positions", None, None, None),
            ("D1_D9_SAME_HOUSE", "Ju", None, None, 0, "BUY", 2.0, "Jupiter holds the SAME house number in both D1 & D9 (whatever that house is) — consistent placement, generally strengthens Jupiter's result either way", None, None, None),
            ("D1_D9_SAME_HOUSE", "ANY", None, None, 0, "NEUTRAL", 0.5, "ANY planet with matching D1/D9 house — logged for reference, doesn't move the score by default; raise the weight/change signal once you've tested this yourself", None, None, None),

            # ── GROUP 7: D9_TO_D1_LIST — one planet's D9 house vs a whole SET of D1 houses ──
            ("D9_TO_D1_LIST", "ANY", None, 2, 0, "AVOID", 1.0, "D9 2nd house planet whose D1 house is 1,2,3,6,7,8, or 12 — avoid buy or sell entirely", "1,2,3,6,7,8,12", None, None),
            ("D9_TO_D1_LIST", "ANY", None, 2, 0, "BUY",   1.5, "D9 2nd house planet whose D1 house is 4,5,10, or 11 — buy recommended", "4,5,10,11", None, None),

            # ── GROUP 8: D9_HOUSE_ASPECT — a house being ASPECTED (drishti), not occupied ──
            ("D9_HOUSE_ASPECT", "Ju", None, 11, 0, "BUY",  2.0, "D9 11th house (gains) ASPECTED by Jupiter — benefic drishti on the gains house", None, None, None),
            ("D9_HOUSE_ASPECT", "Sa", None, 1,  0, "AVOID", 1.0, "D9 1st house (overall chart strength) ASPECTED by Saturn — malefic drishti on the Lagna, avoid trading", None, None, None),
            ("D9_HOUSE_ASPECT", "Ma", None, 2,  0, "SELL", 1.5, "D9 2nd house (wealth) ASPECTED by Mars — aggressive/volatile drishti on the wealth house", None, None, None),
            ("D9_HOUSE_ASPECT", "ANY", None, 2, 0, "NEUTRAL", 0.5, "D9 2nd house (liquid wealth) aspected by ANY planet — logged for reference only, raise weight/change signal once you've tested this yourself", None, None, None),

            # ── GROUP 9: Compound AND rules (Companion Condition) ───────────────
            ("D9_TO_D1_LIST",   "ANY", None, 2, 0, "AVOID", 1.0, "COMPOUND: D9 2nd house planet's D1 house is in {2,3,6,7,8,12} AND Saturn is separately in D9's 7th house — both facts must hold together", "2,3,6,7,8,12", "Sa", 7),
            ("D9_HOUSE_ASPECT", "Ju", None, 11, 0, "BUY",  2.5, "COMPOUND: D9 11th house aspected by Jupiter AND Venus is separately in D9's 2nd house — double benefic confirmation on gains+wealth", None, "Ve", 2),

            # ── GROUP 10: Rahu/Ketu — speculation and volatility ────────────────
            ("D1_HOUSE",      "Ra", 11, None, 0, "BUY",  1.5, "Rahu D1 11th house — speculative sudden gains (volatile)", None, None, None),
            ("D1_HOUSE",      "Ra", 8,  None, 0, "AVOID", 1.0, "Rahu D1 8th house — speculative/sudden-event risk, sit this one out", None, None, None),

            # ── GROUP 11: General planet-house significations (single-fact) ─────
            ("D1_HOUSE",      "Me", 3,  None, 0, "BUY",  1.0, "Mercury D1 3rd house — trade/communication/IT sector active and direct", None, None, None),
            ("D1_HOUSE",      "Ve", 11, None, 0, "BUY",  1.5, "Venus D1 11th house — consumer/luxury sector gains", None, None, None),

            # ── GROUP 12: D1_HOUSE_LIST — one planet's D1 house checked against a SET of
            # houses, with NO D9 house pinned at all. Fully general: any planet, any set
            # of houses, any signal — these four rows show different combinations of all three.
            ("D1_HOUSE_LIST", "Mo", None, None, 0, "BUY",   1.5, "Moon's D1 house is 4, 5, 9, 10, or 11 (any D9 house for Moon is fine, not fixed to one) — buy signal", "4,5,9,10,11", None, None),
            ("D1_HOUSE_LIST", "Sa", None, None, 0, "AVOID", 1.0, "Saturn's D1 house is 6, 8, or 12 (any of the three dusthanas) — avoid trading regardless of D9", "6,8,12", None, None),
            ("D1_HOUSE_LIST", "Ju", None, None, 0, "SELL",  1.0, "Jupiter's D1 house is 6 or 12 — even a natural benefic loses ground here", "6,12", None, None),
            ("D1_HOUSE_LIST", "ANY", None, None, 0, "NEUTRAL", 0.5, "ANY planet whose D1 house is 1, 3, or 6 — logged for reference only; raise weight/change signal once tested", "1,3,6", None, None),
        ]

        def do_load_example_rules(e):
            for (rt, pl, h1, h9, ro, sig, w, nt, h1_list, comp_pl, comp_h9) in EXAMPLE_RULE_PACK:
                rule_add(rt, pl, h1, h9, ro, sig, w, nt, house_d1_list=h1_list, companion_planet=comp_pl, companion_house_d9=comp_h9)
            set_status(f"Loaded {len(EXAMPLE_RULE_PACK)} example rules.", C["green"])
            refresh_rules_list()

        # ── EXPORT / IMPORT RULES AS JSON TEXT ──────────────────────────
        # Uses plain copy/paste (selectable text + text field) instead of native
        # file dialogs, since save/open file pickers have been unreliable once
        # compiled into an Android APK elsewhere in this app.
        export_output = ft.Text("", size=10, color=C["black_txt"], selectable=True, font_family="monospace", visible=False)
        import_input   = ft.TextField(label="Paste Rules JSON here", multiline=True, min_lines=4, max_lines=10, value="")

        def do_export_rules(e):
            rows = rule_list()
            data = []
            for (rid, rtype, planet, hd1, hd9, hd1_list, comp_planet, comp_hd9, retro_only, signal, weight, note) in rows:
                data.append({
                    "rule_type": rtype, "planet": planet, "house_d1": hd1, "house_d9": hd9,
                    "house_d1_list": hd1_list,
                    "companion_planet": comp_planet, "companion_house_d9": comp_hd9,
                    "retro_only": retro_only, "signal": signal, "weight": weight, "note": note
                })
            export_output.value = json.dumps(data, ensure_ascii=False, indent=2)
            export_output.visible = True
            set_status(f"Exported {len(data)} rules below — long-press the text to select & copy.", C["green"])
            page.update()

        def do_import_rules(e):
            try:
                raw = (import_input.value or "").strip()
                if not raw:
                    set_status("Paste JSON rules into the box first.", C["red"])
                    page.update()
                    return
                data = json.loads(raw)
                if not isinstance(data, list):
                    raise ValueError("JSON must be a list of rule objects")
                count = 0
                for item in data:
                    rule_add(
                        item.get("rule_type", "D1_HOUSE"), item.get("planet", "ANY"),
                        item.get("house_d1"), item.get("house_d9"),
                        item.get("retro_only", 0), item.get("signal", "NEUTRAL"),
                        float(item.get("weight", 1.0)), item.get("note", ""),
                        house_d1_list=item.get("house_d1_list"),
                        companion_planet=item.get("companion_planet"),
                        companion_house_d9=item.get("companion_house_d9")
                    )
                    count += 1
                set_status(f"Imported {count} rules.", C["green"])
                import_input.value = ""
                refresh_rules_list()
            except Exception as ex:
                set_status(f"Import error: {str(ex)}", C["red"])
                page.update()

        HELP_TEXT = """HOW THE BUY/SELL/AVOID SIGNAL WORKS
The banner under CALCULATE ASTRO on the Stocks / Show All page is computed by adding up every rule below that matches the current chart: +weight for BUY rules, -weight for SELL rules, 0 for NEUTRAL. AVOID rules work differently on purpose — see below. This is a reference tool based on conventional interpretations, not a validated predictive model — use it as one input, not a standalone signal.

HOUSE vs RASHI — THE MOST IMPORTANT DISTINCTION TO UNDERSTAND
These are two different things, and mixing them up is the #1 source of confusion:
• HOUSE (Bhava) — counted starting from the Ascendant (Lagna), 1st house = wherever the Lagna itself sits, then 2nd, 3rd... 12th going around. This is RELATIVE to that specific chart's Ascendant.
• RASHI (sign) — the fixed zodiac sign itself: 1=Aries, 2=Taurus, 3=Gemini, 4=Cancer, 5=Leo, 6=Virgo, 7=Libra, 8=Scorpio, 9=Sagittarius, 10=Capricorn, 11=Aquarius, 12=Pisces. This is ABSOLUTE — Aries is always Aries no matter what the Lagna is.

A FULLY WORKED EXAMPLE (numbers, not just theory):
Say the Ascendant (Lagna) for this chart falls in Aries (rashi #1). Say Jupiter sits in Sagittarius (rashi #9).
• Jupiter's HOUSE = count from Lagna's sign to Jupiter's sign, inclusive of the start: Aries(1)→Taurus(2)→...→Sagittarius(9) = 9 signs along = Jupiter is in the 9th HOUSE.
• Jupiter's RASHI is simply Sagittarius (#9) — regardless of house, because Sagittarius is Jupiter's own sign (Jupiter "rules" Sagittarius), this is called Swakshetra (own-sign) and is considered a strong, stable placement in its own right.
So the exact same planet position gives you TWO separate facts you can build rules from: "Jupiter in 9th house" (a D1_HOUSE rule with value 9) AND "Jupiter in Sagittarius" (a D1_RASHI rule with value 9 — yes, both happen to be 9 here, but that's a coincidence of this specific example; house and rashi numbers do NOT generally match for other planets or other Lagnas).

KEY HOUSES FOR WEALTH (D1 and D9 both)
• 2nd — liquid wealth, banking, accumulated value
• 5th — speculation, trading, IPOs
• 9th — fortune, long-term growth
• 11th — gains, profits, income (most-watched house)
• 6th, 8th, 12th (dusthanas) — debt/obstacles, sudden crashes/liability, losses — generally bearish

PLANET → MARKET MEANING
• Jupiter (Ju): expansion, banking, overall bullishness → strong in 2nd/5th/9th/11th
• Venus (Ve): currency, consumer/luxury, comfort → strong in 2nd/11th
• Mercury (Me): trade, IT, quick transactions → watch closely if retrograde
• Sun (Su): authority, government/PSU, energy → strong in 10th/11th
• Moon (Mo): public sentiment, FMCG/retail liquidity → strong in 4th/11th
• Mars (Ma): energy sector, aggression, sudden moves → 8th is the classic sudden-crash placement
• Saturn (Sa): structure, old-economy, discipline, delay → steady in 3rd/11th, drags in 1st/6th/8th
• Rahu (Ra): speculation, sudden gains, unconventional/tech sectors → 11th = sudden windfall (volatile)
• Ketu (Ke): sudden loss, detachment, liquidation → bearish in 8th/12th

RETROGRADE — TWO SCHOOLS OF THOUGHT
Most trading-desk convention treats Mercury retrograde as a caution period (miscommunication, contract issues, volatility) — often bearish for IT/trade stocks. Some traditional astrologers instead argue a retrograde planet acts stronger, not weaker. Given this genuine disagreement, treat retrograde as a volatility multiplier and let your own rule's Signal/Weight decide the direction. Note: Rahu/Ketu are always calculated as retrograde (their mean motion never goes direct), so a "retrograde only" rule on them will basically always fire.

VARGOTTAMA
When a planet sits in the SAME rashi/sign in both D1 and D9 (regardless of house number), it's considered to triple/amplify that planet's natural result — good or bad. Use the VARGOTTAMA rule type for this (house fields not needed).

THE "AVOID" SIGNAL — HOW IT'S DIFFERENT FROM SELL
BUY and SELL both feed into one numeric tug-of-war score — a handful of small BUY rules can outweigh one SELL rule. AVOID is deliberately NOT part of that tally. It's meant for placements you consider serious enough that no amount of other-rule positivity should paper over them (e.g. a retrograde malefic sitting in a genuinely dangerous house). If even ONE of your AVOID rules matches, the banner switches to "🚫 AVOID THIS STOCK TODAY" regardless of what the BUY/SELL score says — you'll still see the numeric score's detail below it, but the headline is the AVOID warning. Use it sparingly, for placements you've personally found reliably bad — that's the whole point of letting you set your OWN experienced rules rather than a fixed formula.

QUICK RULE — ONE LINE PER RULE (top of the Rules screen, above the wizard)
The fastest way in: type the entire rule as a single line of text and tap ADD QUICK RULE — no dropdowns, no rule-type name to remember. It understands house, rashi, house-list, vargottama, aspect, retrograde, and companion (AND) conditions, all in one uniform grammar:
  <planet> <condition> => <SIGNAL>   [RETRO]   [+<planet>@D9H<n>]   [wt=<n>]   [note="..."]
Condition shapes: D1H<n> / D9H<n> (house), D1R<n> / D9R<n> (rashi), VG (vargottama), D1H<n>=D9H<n2> (compare), D1H=D9H (same house), D9H<n>~ASPECT (aspect), D9H<n>->D1H[list] (fixed D9 house + D1 list), D1H[list] (plain D1 list).
Worked example — exactly the question "if D9's house no 2 has a planet and that planet's D1 house is 4,5,9,10 or 11": Mo D9H2->D1H[4,5,9,10,11] => BUY  (use ANY instead of Mo for any planet).
Every rule you already saved (including the example pack) is also shown in this same shorthand next to its normal description in the rules list below, so you can learn the format by reading real rules — this is purely a second way to fill the same fields; the dropdown form and the wizard still work exactly as before and write to the same table.

SIMPLE RULE WIZARD (top of the Rules screen)
If picking from 10 rule-type names feels like a lot, use the wizard first: answer "What does D1 mean here?" and "What does D9 mean here?" in plain words (Not used / Specific House / House is one of a List / Specific Rashi / Same as D1 / Aspected), then tap "AUTO-SELECT RULE TYPE FROM MY ANSWERS." It fills in the correct technical Rule Type below for you -- you never have to memorize which cryptic name matches which situation. It doesn't change how rules work underneath; it's just a translator sitting on top of the same 10 types explained below.

QUICK REFERENCE -- EVERY RULE TYPE, ONE LINE EACH, WITH A WORKED EXAMPLE (ENGLISH + HINDI)
Field shorthand: Pl=Planet, D1H=D1 House, D9H=D9 House, List=D1 House LIST, Comp=Companion Planet+House, Sig=Signal.
Shorthand (Hindi): Pl=ग्रह, D1H=D1 भाव, D9H=D9 भाव, List=D1 भाव सूची, Comp=साथी ग्रह+भाव, Sig=संकेत।

1. D1_HOUSE -- one planet, one fixed D1 house.
   एक ग्रह, D1 में एक निश्चित भाव।
   Example: Pl=Ju, D1H=11, Sig=BUY -> "Jupiter in D1 11th house -> BUY"
   उदाहरण: Pl=Ju, D1H=11, Sig=BUY -> "गुरु D1 के 11वें भाव में -> खरीदें (BUY)"

2. D9_HOUSE -- one planet, one fixed D9 house.
   एक ग्रह, D9 में एक निश्चित भाव।
   Example: Pl=Sa, D9H=7, Sig=AVOID -> "Saturn in D9 7th house -> AVOID"
   उदाहरण: Pl=Sa, D9H=7, Sig=AVOID -> "शनि D9 के 7वें भाव में -> बचें (AVOID)"

3. D9_HOUSE_ASPECT -- one D9 house being ASPECTED (drishti) by a planet, not occupied by it.
   D9 का कोई भाव किसी ग्रह की दृष्टि (aspect) में हो, उस ग्रह के वहां बैठने से नहीं।
   Example: Pl=ANY, D9H=11, Sig=BUY -> "D9 11th house aspected by any planet -> BUY"
   उदाहरण: Pl=ANY, D9H=11, Sig=BUY -> "D9 का 11वां भाव किसी भी ग्रह की दृष्टि में -> खरीदें"

4. D1_D9_COMPARE -- a planet's D1 house AND D9 house must BOTH match your exact numbers.
   एक ग्रह का D1 भाव और D9 भाव दोनों आपके बताए गए नंबर से मेल खाने चाहिए।
   Example: Pl=Ju, D1H=11, D9H=11, Sig=BUY -> "Jupiter in D1 11th AND D9 11th together -> BUY"
   उदाहरण: Pl=Ju, D1H=11, D9H=11, Sig=BUY -> "गुरु D1 के 11वें और D9 के 11वें भाव में एक साथ -> खरीदें"

5. D1_D9_SAME_HOUSE -- a planet's D1 house equals its D9 house, whatever that number is (no house values entered).
   एक ग्रह का D1 भाव और D9 भाव बराबर हों, चाहे वह कोई भी भाव संख्या हो (भाव भरने की जरूरत नहीं)।
   Example: Pl=Ju, Sig=BUY -> "Jupiter's D1 and D9 house match (any house) -> BUY"
   उदाहरण: Pl=Ju, Sig=BUY -> "गुरु का D1 और D9 भाव मेल खाता है (कोई भी भाव) -> खरीदें"

6. D9_TO_D1_LIST -- one FIXED D9 house, then that planet's D1 house checked against a SET.
   D9 का एक निश्चित भाव तय करें, फिर उस ग्रह के D1 भाव को भावों की एक सूची से जांचें।
   Example: Pl=ANY, D9H=2, List=1,2,3,6,7,8,12, Sig=AVOID -> "D9 2nd house planet, if its D1 house is any of these -> AVOID"
   उदाहरण: Pl=ANY, D9H=2, List=1,2,3,6,7,8,12, Sig=AVOID -> "D9 के दूसरे भाव में जो भी ग्रह हो, अगर उसका D1 भाव इस सूची में है -> बचें"

7. D1_HOUSE_LIST -- NO D9 house at all -- just a planet's D1 house checked against a SET. Fully general.
   D9 का कोई भाव तय करने की जरूरत नहीं -- सिर्फ ग्रह के D1 भाव को सूची से जांचें। पूरी तरह लचीला।
   Example: Pl=Mo, List=4,5,9,10,11, Sig=BUY -> "Moon's D1 house is any of these -> BUY"
   उदाहरण: Pl=Mo, List=4,5,9,10,11, Sig=BUY -> "चंद्रमा का D1 भाव इस सूची में से कोई भी हो -> खरीदें"

8. VARGOTTAMA -- a planet's RASHI (sign) is identical in D1 and D9 (no house/list fields needed).
   किसी ग्रह की राशि D1 और D9 दोनों में एक जैसी हो (भाव/सूची भरने की जरूरत नहीं)।
   Example: Pl=Ju, Sig=BUY -> "Jupiter Vargottama -> BUY"
   उदाहरण: Pl=Ju, Sig=BUY -> "गुरु वर्गोत्तम -> खरीदें"

9. D1_RASHI -- a planet sits in a specific absolute RASHI (1=Aries...12=Pisces) in D1, regardless of house.
   कोई ग्रह D1 में एक निश्चित राशि (1=मेष...12=मीन) में बैठा हो, भाव चाहे जो भी हो।
   Example: Pl=Ju, D1H=9, Sig=BUY -> "Jupiter in Sagittarius (own sign) in D1 -> BUY"
   उदाहरण: Pl=Ju, D1H=9, Sig=BUY -> "गुरु D1 में धनु राशि (अपनी राशि) में -> खरीदें"

10. D9_RASHI -- same as above, checked in the D9 chart.
    ऊपर जैसा ही, लेकिन D9 चार्ट में जांचा जाता है।
    Example: Pl=Ve, D9H=7, Sig=BUY -> "Venus in Libra (own sign) in D9 -> BUY"
    उदाहरण: Pl=Ve, D9H=7, Sig=BUY -> "शुक्र D9 में तुला राशि (अपनी राशि) में -> खरीदें"

COMBINING WITH RETROGRADE: tick "Apply only when Retrograde" on ANY of the 10 types above to restrict it further -- e.g. rule #2 becomes "Saturn RETROGRADE in D9 7th -> AVOID."
रिट्रोग्रेड के साथ जोड़ना: ऊपर दिए गए किसी भी प्रकार पर "केवल वक्री होने पर लागू करें" को चुनें ताकि नियम और सीमित हो जाए -- जैसे नियम #2 बन जाता है "शनि वक्री D9 के 7वें भाव में -> बचें।"

COMBINING WITH COMPANION CONDITION: fill in Companion Planet + Companion D9 House on ANY of the 10 types to AND a second independent fact onto it -- e.g. rule #6 becomes "D9 2nd house planet's D1 house in that list, AND Saturn separately in D9's 7th -> AVOID," matching your own compound example already loaded in the starter pack.
साथी शर्त (Companion Condition) के साथ जोड़ना: किसी भी प्रकार में साथी ग्रह और साथी D9 भाव भरें ताकि एक दूसरी स्वतंत्र शर्त भी जुड़ जाए -- जैसे नियम #6 बन जाता है "D9 के दूसरे भाव के ग्रह का D1 भाव उस सूची में हो, और साथ ही शनि अलग से D9 के 7वें भाव में हो -> बचें," जो आपके अपने उदाहरण से मेल खाता है जो पहले से स्टार्टर पैक में मौजूद है।

RULE TYPES EXPLAINED
• D1_HOUSE — fires when a planet is in the given HOUSE (counted from Lagna) in the D1 (Rasi) chart
• D9_HOUSE — fires when a planet is in the given HOUSE (counted from Lagna) in the D9 (Navamsha) chart
• D1_D9_COMPARE — fires only when BOTH the D1 house AND D9 house match the SPECIFIC values you enter (e.g. only 11th-and-11th) — the strongest, most exact confirmation
• D1_D9_SAME_HOUSE — a more general version of the above: fires whenever a planet's D1 house number EQUALS its D9 house number, whatever that number happens to be (11th-11th, or 3rd-3rd, or any other matching pair) — no house values need to be entered for this type. Use D1_D9_COMPARE when you care about one specific house; use D1_D9_SAME_HOUSE when you just want to flag "this planet's house position is consistent across both charts," regardless of which house it is.
• D9_TO_D1_LIST — for a common pattern that doesn't fit the types above: "whichever planet sits in a FIXED D9 house, check whether that same planet's D1 house is ANY of a whole SET of houses." Enter the fixed D9 house in the D9 House field, and the set of acceptable D1 houses as a comma-separated list in the "D1 House LIST" field (e.g. "4,5,10,11"). Fires if the D9 house matches AND the D1 house is anywhere in that list. Example: "D9 2nd house planet, if its D1 house is 1, 2, 3, 6, 7, 8, or 12 → AVOID" becomes one single rule: D9 House=2, D1 House LIST=1,2,3,6,7,8,12, Signal=AVOID — instead of needing 7 separate rows.
• VARGOTTAMA — fires when D1 rashi = D9 rashi for that planet (house fields not needed) — note this is about the SIGN matching, which is a different, separate concept from D1_D9_SAME_HOUSE matching on HOUSE NUMBER (see the House vs Rashi section above)
• D1_RASHI — fires when a planet sits in the given absolute RASHI (1=Aries...12=Pisces) in the D1 chart, regardless of which house that rashi falls in for this particular Lagna
• D9_RASHI — same as above, but checked in the D9 (Navamsha) chart
• D1_HOUSE_LIST — the fully general cousin of D9_TO_D1_LIST, with NO D9 house pinned at all: "this planet's D1 house is ANY of a whole SET of houses," full stop. Works for any planet (or ANY), any set of D1 houses you type in, and any signal (BUY/SELL/AVOID/NEUTRAL) — nothing about this rule type is fixed. Example: "Moon's D1 house is 4, 5, 9, 10, or 11 -> BUY" becomes: Rule Type=D1_HOUSE_LIST, Planet=Mo, D1 House LIST=4,5,9,10,11, Signal=BUY. Swap the planet, the house list, or the signal freely — e.g. Planet=Sa, D1 House LIST=6,8,12, Signal=AVOID for a completely different rule using the exact same mechanism.
• D9_HOUSE_ASPECT — fires when the chosen D9 HOUSE (enter it in the D9 House field) is ASPECTED (drishti) by the chosen Planet — or by ANY planet if Planet=ANY. Classical Parashari rule: every planet aspects the 7th house from its own position; Mars also aspects the 4th/8th, Jupiter the 5th/9th, Saturn the 3rd/10th. Rahu/Ketu are treated like Saturn here (3rd/7th/10th) as a common modern convention, not classical doctrine. Example: Planet=ANY, D9 House=11, Signal=BUY → fires whenever any planet currently aspects the D9 11th (gains) house.

CHART COLOR CODING (on the D1/D9 diamond charts themselves)
• Red — normal planet, no special condition
• Orange "(R)" — retrograde
• Teal "(V)" — Vargottama (same rashi in D1 and D9)
• Purple "(R,V)" — both retrograde and Vargottama at once
A legend with these same colors appears just below every chart.

BHOOVALAYA BANDHA (STEP 7 of the Oracle report)
The Navaank (digital root, Step 2) also maps to one of six classical Bandha (traversal/lock) patterns from the Siribhoovalaya tradition — each represents a distinct way of moving through the 27×27 akshara matrix. This is a symbolic overlay for your own thinking, not a standalone rule.

• रथबंध Rathabandha (Chariot) — steady, linear forward motion → Direction: UP. Favors trend-following; hold through medium-term moves.
• चक्रबंध Chakrabandha (Wheel) — cyclical, repeating loops → Direction: SIDEWAYS. Expect swings both ways; better for swing-trade re-entries than one hold.
• पद्मबंध Padmabandha (Lotus) — layered, unfolding petal by petal → Direction: UP. Gradual build-up; consider accumulating in tranches.
• हंसबंध Hamsabandha (Swan) — graceful glide, discernment → Direction: UP (mild). Favors selective, quality-over-quantity entries.
• मुक्तावली Muktavali (Pearl-chain) — linked, sequential continuity → Direction: CONTINUATION (reinforces whatever the Graha already says). Moves may be linked to sector/peer stocks.
• सर्वतोभद्र Sarvatobhadra (Balanced square) — balance in every direction → Direction: SIDEWAYS. Range-bound; better to wait for a clear breakout.

Which Bandha you get depends only on Navaank: Bandha index = (Navaank − 1) mod 6.

COMBINED PRICE DIRECTION (STEP 8 of the Oracle report)
Step 8 cross-checks the Graha's signal (Step 5: Bullish/Bearish/Volatile/Speculative) against the Bandha's directional tendency above, to give one final UP / DOWN / SIDEWAYS / MIXED call:
• Graha and Bandha AGREE (e.g. both point UP) → higher-confidence UP or DOWN call
• Bandha is CONTINUATION → simply follows whatever direction the Graha already gives
• Either signal is SIDEWAYS → tempered down to SIDEWAYS (lower conviction, range-bound read)
• Graha and Bandha genuinely CONFLICT (one UP, one DOWN) → flagged as MIXED rather than forcing a false-confident call
This is a heuristic combination of two symbolic systems, not a backtested statistical model — treat it as food for thought alongside your own research and the custom Rules above, not as a standalone buy/sell trigger.

SARVATOBHADRA VEDHA CHECK (STEP 9 of the Oracle report)
Vedha means "obstruction" — a classical Muhurta-shastra concept where certain pairs of nakshatras are said to afflict/cancel each other's auspiciousness when they occur together. This is genuinely a timing/electional-astrology tool in the original tradition — classical texts do NOT link it to stock sectors or price direction; that link is this app's own extension, done honestly rather than invented as if it were textual.

Step 9 compares today's trading-day nakshatra against the stock's own "birth" nakshatra (from its listing date) using the standard Sarvatobhadra Chakra pairing table. If they form a Vedha pair, it's flagged ⚠️ as an extra caution signal for that day; if not, it shows ✅ clear.

Each nakshatra also has a real, classical ruling planet (the "Nakshatra Lord", same sequence used for Vimshottari Dasha: Ketu → Venus → Sun → Moon → Mars → Rahu → Jupiter → Saturn → Mercury, repeating 3x across all 27 nakshatras). When a Vedha is present, Step 9 also shows both nakshatras' lords and pulls their associated sectors from the Graha table in Step 5 — so you get a concrete "which sectors does this caution flag concern" answer, built from a real classical assignment (the lordship) even though the sector-linkage itself is this app's own layer, not ancient doctrine.

Treat this whole step as an additional caution flag to weigh alongside Graha, Bandha, and your own Rules — not a standalone reason to act.

LIVE PRICE (in Stocks list, next to Ramal)
Tap "💰 Price" on any stock row to fetch its current trading price, change vs previous close, yesterday's closing price, and 52-week high/low. It tries NSE's live quote API first; if NSE blocks the request (it does this unpredictably to automated requests), it automatically falls back to Yahoo Finance for the same stock — no action needed from you. The panel tells you which source actually answered. It runs in the background so the list stays responsive while fetching. If both sources fail, the panel shows the error and you can simply try again in a moment. Treat this as a quick reference, not a substitute for checking your broker's terminal before actually placing a trade.

RAMAL PRASHNA (in Oracle, below Calculate Astro)
Ramal is a separate Persian/Arabic geomancy system (also used in some Indian traditions), cast fresh at the exact moment you ask the question — like a horary chart. Tapping "🎲 RAMAL PRASHNA" never re-asks for the stock; it uses whichever stock you already searched above.

It randomly casts 4 "Mother" figures (simulating a disc-spin), derives 4 Daughters (by transposing the Mothers) and 4 Nephews, then 2 Witnesses, then the 15th house "Judge", and finally the 16th house "Final Outcome" (Mother 1 combined with the Judge) — the complete classical 16-house chart, with all 16 possible Shakal figures properly named (not a partial set). Since we don't ask BUY or SELL intent, the result shows both readings from the same cast.

The verdict requires the Judge (15th) AND Final Outcome (16th) to agree in nature (both Mitrik/inward) for a high-confidence BUY call — a stricter, closer-to-tradition check than using the Judge alone. If the Judge shows Kharij (outward) energy, that's read as a caution against buying regardless of the Final Outcome. Anything else lands as neutral/wait.

Ramal is then cross-checked against Bhoovalaya's own combined direction (Step 8) for the same stock — if both agree, it's flagged as higher-confidence; if they disagree, that's flagged too, rather than picking one silently. Because Ramal is randomly re-cast at the moment of asking, tapping it again later (or for the same stock on a different day) can genuinely give a different reading — that's expected behavior for a Prashna-style system, not a bug.

EXPORT / IMPORT RULES
"📤 EXPORT RULES" turns all your saved rules into JSON text shown in a copyable box below the button — long-press the text to select it, copy, then paste it anywhere (a text file on your PC, notes app, email) to back it up or test it elsewhere. "📥 IMPORT RULES FROM JSON" does the reverse: paste JSON text (in the same format) into the box above it and tap the button to load those rules straight into this app. This uses plain copy-paste rather than a file-save dialog, since those have proven unreliable once compiled into an Android APK.

COMPANION CONDITION — COMBINING TWO SEPARATE FACTS WITH "AND"
Every rule type above checks ONE fact about ONE planet. Sometimes you need TWO facts to be true at the SAME time before it counts — e.g. "condition A about whichever planet is in D9's 2nd house" AND, completely separately, "Saturn specifically is in D9's 7th house." Entering these as two separate rules would fire the AVOID banner if EITHER happened alone, which is not what you want.
The "Companion Condition" fields solve this: fill in a Companion Planet and a Companion D9 House, and the rule will ONLY fire when its normal condition is true AND that companion planet is separately sitting in that D9 house too — both must hold at once.
Worked example: "If D9's 2nd house planet's D1 house is in {2,3,6,7,8,12} AND Saturn is in D9's 7th house -> AVOID" is built as: Rule Type=D9_TO_D1_LIST, Planet=ANY, D9 House=2, D1 House LIST=2,3,6,7,8,12, Companion Planet=Sa, Companion D9 House=7, Signal=AVOID. This is already included in the example pack below.
Leave both Companion fields blank for an ordinary single-fact rule — this is fully optional and only needed for compound AND conditions like this one.

Tap "📦 LOAD EXAMPLE RULES" to add the full starter pack covering all the patterns above (the exact count is shown in the confirmation message after loading), then edit/delete individual rules to match your own approach.

REFERENCE: PLANETARY DIGNITY TABLE (exaltation / own sign / debilitation)
This is classical Vedic astrology, not market-specific — a planet gives its strongest result in its exaltation sign, a comfortable/stable result in its own sign(s), and its weakest result in its debilitation sign (always the sign directly opposite its exaltation). Build D1_RASHI or D9_RASHI rules from this table using the rashi number (1=Aries, 2=Taurus, 3=Gemini, 4=Cancer, 5=Leo, 6=Virgo, 7=Libra, 8=Scorpio, 9=Sagittarius, 10=Capricorn, 11=Aquarius, 12=Pisces):
• Sun (Su) — exalted #1 Aries · own #5 Leo · debilitated #7 Libra
• Moon (Mo) — exalted #2 Taurus · own #4 Cancer · debilitated #8 Scorpio
• Mars (Ma) — exalted #10 Capricorn · own #1 Aries / #8 Scorpio · debilitated #4 Cancer
• Mercury (Me) — exalted #6 Virgo · own #3 Gemini / #6 Virgo · debilitated #12 Pisces
• Jupiter (Ju) — exalted #4 Cancer · own #9 Sagittarius / #12 Pisces · debilitated #10 Capricorn
• Venus (Ve) — exalted #12 Pisces · own #2 Taurus / #7 Libra · debilitated #6 Virgo
• Saturn (Sa) — exalted #7 Libra · own #10 Capricorn / #11 Aquarius · debilitated #1 Aries
Rahu/Ketu dignity is disputed across different classical texts (Jagannatha Hora gives Rahu exalted in Gemini/Taurus depending on the source, Ketu in Sagittarius/Scorpio) — deliberately left out of this table rather than presenting a contested claim as settled.

REFERENCE: FINANCIAL-ASTROLOGY TRADITIONS THIS APP DRAWS ON
Two broad, largely separate traditions inform the planet→market associations used above and in the Graha table (Oracle Step 5):
• Western/tropical: W. D. Gann (early-to-mid 20th century US trader) pioneered linking planetary cycles, angles, and time periods to price action — his specific price/time-square and geometric-angle methods are NOT implemented here, only the general idea that planetary cycles can be watched. Later writers like Bill Meridian and Louise McWhirter extended this into more systematic planet-to-sector mappings.
• Vedic/Indian: a long-running tradition (various contemporary Indian financial astrologers, building on classical Parashari and Jaimini principles) applies standard natal-chart techniques — house lordships, dignity, aspects, dashas — to market/sector timing instead of a person's life. This app's D1/D9 house-and-dignity approach sits in this camp.
Neither tradition has peer-reviewed, statistically validated backing — they are heuristic, experience-based frameworks, and different practitioners within each tradition disagree with each other (see the Retrograde section above for one concrete example). Treat every planet→sector association in this app, including the ones you build yourself, as a hypothesis to test against your own market experience — not a settled result. This app is a rule-tracking and charting tool for your own research, not financial advice, and it does not predict prices.

REFERENCE: WHAT THIS APP DOES NOT CALCULATE (so you don't assume a rule exists that isn't there)
To be upfront about scope — none of the following are implemented, so no rule can currently be built on them:
• Moon phase (Amavasya/Purnima) or Sun-Moon angular distance
• Planetary combustion (a planet very close to the Sun)
• Planetary war (two planets at the same longitude)
• Transits measured from the Moon's position instead of the Lagna (Chandra Lagna)
• Gann's specific price-square, time-cycle, or geometric-angle methods
• Divisional charts other than D1 (Rasi) and D9 (Navamsha) — e.g. D10 (career/business) is not calculated
• Dasha/sub-period (Vimshottari Dasha) timing, beyond the Nakshatra Lord lookup already used in Step 9
If any of these would be useful to you, they'd need to be added as new features — they are not quietly happening in the background.

USER Q&A — REAL WORKED EXAMPLE
User's Question: "if d9's house no 2 has moon or any planet which i define and rashi of d9's house exist in d1's house no. 4,5,9,10,11 then how i can define it and in which rule?"

Answer: Use the D9_TO_D1_LIST rule type. Set Planet = Mo (or ANY, or any specific planet of your choice), D9 House = 2, D1 House LIST = 4,5,9,10,11, and Signal = whichever you intend (BUY / SELL / AVOID / NEUTRAL). This rule type is built for exactly this shape of question — a FIXED D9 house (here, 2) combined with a SET of acceptable D1 houses (here, 4,5,9,10,11); it's item #6 in the Quick Reference table above.
One distinction worth being clear on: D9_TO_D1_LIST pins the D9 house to one specific number, while D1_HOUSE_LIST (item #7) does not pin any D9 house at all — it only checks the D1 house. Since this question specifically named "D9's house no 2," D9_TO_D1_LIST is the correct rule type here, not D1_HOUSE_LIST.

USER Q&A #2 — SAME QUESTION, ANSWERED USING THE SIMPLE RULE WIZARD
User's Question: "if d9 house no. 2 and its rashi exist in d1's house no. 4,5,9,10,11 how i can define in above rule?"

Answer: Same underlying rule type as Q&A #1 above (D9_TO_D1_LIST) — but here's the wizard shortcut instead of picking it manually: on the Rules screen, set "What does D1 mean here?" = House is one of a List, and "What does D9 mean here?" = Specific House number, then tap AUTO-SELECT RULE TYPE FROM MY ANSWERS. It fills in D9_TO_D1_LIST for you automatically. Then fill in: Planet = ANY (or your choice), D9 House = 2, D1 House LIST = 4,5,9,10,11, Signal = your choice, and tap ADD RULE. This shows that once you can describe D1 and D9 in plain words, you don't need to remember the technical rule-type name at all — the wizard finds it for you."""

        help_screen = ft.Column(visible=False, scroll="auto", controls=[
            make_header("📖 HELP / REFERENCE GUIDE"), ft.Divider(height=4, color=C["divider"]),
            ft.Text(HELP_TEXT, size=12.5, color=C["black_txt"], selectable=True),
            ft.Container(height=10),
            ft.ElevatedButton("⬅  BACK TO RULES", bgcolor=C["primary"], color="#FFFFFF", height=48, on_click=lambda e: show_screen("rules"))
        ])

        rules_screen = ft.Column(visible=False, scroll="auto", controls=[
            make_header("📜 CUSTOM D1 / D9 RULES"), ft.Divider(height=4, color=C["divider"]),
            ft.Text("Define your own planet-in-house rules. These drive the BUY/SELL recommendation shown under CALCULATE ASTRO on the Stocks / Show All page, and the Green/Red timing flag at the top of that page.", size=12, color=C["black_txt"]),
            ft.ElevatedButton("📖 HELP / REFERENCE GUIDE", bgcolor=C["accent"], color="#FFFFFF", height=44, on_click=lambda e: show_screen("help")),
            ft.Divider(height=6, color=C["divider"]),
            ft.Container(
                content=ft.Column([
                    ft.Text("⚡ FASTEST WAY IN — type the whole rule as one line, then tap ADD. Covers house, rashi, list, vargottama, aspect, retrograde and companion conditions — everything below in one box.", size=12, weight="bold", color=C["green"]),
                    fld_quick_rule,
                    ft.ElevatedButton("⚡ ADD QUICK RULE", bgcolor=C["green"], color="#FFFFFF", height=44, on_click=do_add_quick_rule),
                    quick_rule_status_txt,
                    quick_rule_cheatsheet,
                ], spacing=6),
                bgcolor="#E8F5E9", border_radius=8, padding=10
            ),
            ft.Divider(height=6, color=C["divider"]),
            ft.Text("Prefer dropdowns instead? Use the form below — it does exactly the same thing, field by field.", size=11, color=C["black_txt"]),
            ft.Container(
                content=ft.Column([
                    ft.Text("🧩 NOT SURE WHICH RULE TYPE TO PICK? Answer these two questions in plain words, then tap the button — it sets the Rule Type below for you.", size=12, weight="bold", color=C["primary"]),
                    fld_d1_mode, fld_d9_mode,
                    ft.ElevatedButton("🧩 AUTO-SELECT RULE TYPE FROM MY ANSWERS", bgcolor=C["primary"], color="#FFFFFF", height=44, on_click=do_auto_select_rule_type),
                    wizard_status_txt,
                ], spacing=6),
                bgcolor="#E8EAF6", border_radius=8, padding=10
            ),
            ft.Divider(height=6, color=C["divider"]),
            fld_rule_type, fld_rule_planet,
            ft.Row([fld_rule_h1, fld_rule_h9]),
            fld_rule_h1_list,
            ft.Text("Companion Condition (optional) — an extra planet+house that must ALSO be true (AND), for compound rules", size=11, color=C["black_txt"]),
            ft.Row([fld_rule_companion_planet, fld_rule_companion_h9]),
            fld_rule_retro, fld_rule_signal, fld_rule_weight, fld_rule_note,
            ft.ElevatedButton("➕ ADD RULE", bgcolor=C["primary"], color="#FFFFFF", height=48, on_click=do_add_rule),
            ft.ElevatedButton("📦 LOAD EXAMPLE RULES (financial astrology starter pack)", bgcolor=C["orange"], color="#FFFFFF", height=44, on_click=do_load_example_rules),
            ft.Divider(height=6, color=C["divider"]),
            ft.Text("EXPORT / IMPORT RULES (copy-paste JSON — e.g. to test on desktop and bring back)", size=12, weight="bold", color=C["black_txt"]),
            ft.ElevatedButton("📤 EXPORT RULES (JSON)", bgcolor=C["accent"], color="#FFFFFF", height=44, on_click=do_export_rules),
            export_output,
            import_input,
            ft.ElevatedButton("📥 IMPORT RULES FROM JSON", bgcolor=C["green"], color="#FFFFFF", height=44, on_click=do_import_rules),
            ft.Divider(height=6, color=C["divider"]),
            ft.Text("EXISTING RULES:", size=13, weight="bold", color=C["black_txt"]),
            rules_list_col
        ])

        # ── NAVIGATION CONTROL ────────────────────────────────────────────────
        all_screens = {"oracle": oracle_screen, "list": list_screen, "entry": entry_screen, "astro": astro_screen, "db": db_screen, "rules": rules_screen, "help": help_screen}

        AZ_LETTERS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        az_letter_containers = {}  # letter -> its Container, so we can restyle the selected one

        def do_select_letter(letter):
            if selected_letter["value"] == letter:
                selected_letter["value"] = None  # tap the same letter again to clear the filter
            else:
                selected_letter["value"] = letter
            for l, ctrl in az_letter_containers.items():
                is_sel = (l == selected_letter["value"])
                ctrl.bgcolor = C["primary"] if is_sel else None
                ctrl.content.color = "#FFFFFF" if is_sel else C["primary"]
            load_list(fld_list_search.value.strip().upper())
            page.update()

        def do_clear_letter(e=None):
            selected_letter["value"] = None
            for ctrl in az_letter_containers.values():
                ctrl.bgcolor = None
                ctrl.content.color = C["primary"]
            load_list(fld_list_search.value.strip().upper())
            page.update()

        def _az_letter_btn(l):
            txt = ft.Text(l, size=10, weight="bold", color=C["primary"])
            ctrl = ft.Container(content=txt, padding=2, border_radius=3,
                                 on_click=lambda e, l=l: do_select_letter(l))
            az_letter_containers[l] = ctrl
            return ctrl

        az_index_strip = ft.Container(
            content=ft.Column(
                [ft.Container(content=ft.Text("ALL", size=9, weight="bold", color=C["red"]),
                              padding=2, on_click=do_clear_letter)]
                + [_az_letter_btn(l) for l in AZ_LETTERS],
                spacing=1, tight=True, scroll="auto", height=380
            ),
            bgcolor="#E8EAF6", border_radius=6, padding=3,
            top=110, right=4, visible=False
        )

        floating_back_to_oracle = ft.Container(
            content=ft.ElevatedButton("⬅ ORACLE", bgcolor=C["primary"], color="#FFFFFF", height=38,
                                        style=ft.ButtonStyle(text_style=ft.TextStyle(size=12, weight="bold")),
                                        on_click=lambda e: show_screen("oracle")),
            top=8, right=8, visible=False
        )
        page.overlay.append(az_index_strip)
        page.overlay.append(floating_back_to_oracle)

        def show_screen(name):
            for k, v in all_screens.items(): v.visible = (k == name)
            confirm_exit_panel.visible = False
            floating_back_to_oracle.visible = (name == "list")
            az_index_strip.visible = (name == "list")
            page.update()

        # Each tab gets its own distinct color (Flet's built-in NavigationBar can't do
        # per-item colors, so this is a manually built button row instead).
        NAV_ITEMS = [
            (ft.Icons.PSYCHOLOGY,             "Oracle",   "oracle", "#0D47A1"),
            (ft.Icons.FORMAT_LIST_BULLETED,   "Stocks",   "list",   "#00695C"),
            (ft.Icons.EDIT_NOTE,              "Entry",    "entry",  "#6A1B9A"),
            (ft.Icons.STARS,                  "Kundali",  "astro",  "#EF6C00"),
            (ft.Icons.STORAGE,                "Data",     "db",     "#455A64"),
            (ft.Icons.RULE,                   "Rules",    "rules",  "#2E7D32"),
        ]

        def nav_button(icon, label, target, color):
            return ft.Container(
                content=ft.Column([
                    ft.Icon(icon, color="#FFFFFF", size=20),
                    ft.Text(label, size=9, color="#FFFFFF", weight="bold")
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2, tight=True),
                bgcolor=color, padding=6, border_radius=8, expand=1,
                alignment=ft.alignment.center,
                on_click=lambda e, t=target: show_screen(t)
            )

        def do_show_exit_confirm(e):
            confirm_exit_panel.visible = True
            page.update()

        def do_exit_no(e):
            confirm_exit_panel.visible = False
            page.update()

        def do_exit_yes(e):
            # page.window.destroy()/close() only ask Flutter's window layer to close,
            # which is known to not always kill the underlying process once compiled
            # into an Android APK. Try the graceful route first, then fall back to a
            # hard OS-level process kill that works regardless of Flutter's state,
            # since the Python interpreter runs in the same process as the app on Android.
            try:
                page.window.destroy()
            except Exception:
                pass
            try:
                page.window.close()
            except Exception:
                pass
            os._exit(0)

        exit_button = ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.POWER_SETTINGS_NEW, color="#FFFFFF", size=20),
                ft.Text("Exit", size=9, color="#FFFFFF", weight="bold")
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2, tight=True),
            bgcolor=C["red"], padding=6, border_radius=8, expand=1,
            alignment=ft.alignment.center, on_click=do_show_exit_confirm
        )

        nav_row = ft.Container(
            content=ft.Row(
                controls=[nav_button(icon, label, target, color) for (icon, label, target, color) in NAV_ITEMS] + [exit_button],
                spacing=4
            ),
            bgcolor="#E8EAF6", padding=6
        )

        confirm_exit_panel = ft.Container(
            content=ft.Column([
                ft.Text("⚠️ Exit Bhoovalaya Oracle?", size=16, weight="bold", color=C["red"]),
                ft.Text("Are you sure you want to close the app? Any unsaved entries will be lost.", size=13, color=C["black_txt"]),
                ft.Row([
                    ft.ElevatedButton("✔  YES, EXIT", bgcolor=C["red"], color="#FFFFFF", height=46, expand=1, on_click=do_exit_yes),
                    ft.ElevatedButton("✖  NO, STAY", bgcolor=C["primary"], color="#FFFFFF", height=46, expand=1, on_click=do_exit_no),
                ], spacing=10)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
            bgcolor="#FFF3E0",
            border=ft.Border(top=ft.BorderSide(3, C["red"]), bottom=ft.BorderSide(3, C["red"]), left=ft.BorderSide(3, C["red"]), right=ft.BorderSide(3, C["red"])),
            border_radius=10, padding=16, visible=False
        )

        page.add(status_bar, oracle_screen, list_screen, entry_screen, astro_screen, db_screen, rules_screen, help_screen, confirm_exit_panel, nav_row)

        refresh_rules_list()

        try:
            _lbl, _clr, _score, _avoid = compute_live_timing_signal()
            apply_timing_flag(_score, _avoid)
        except Exception:
            pass  # ephemeris/rules not ready yet — top flag just keeps its placeholder text

        n = db_count()
        if n < 5: set_status("No database. Go to Database tab.", C["red"])
        else: set_status(f"Ready — {n} stocks loaded.", C["green"])

    except Exception as err:
        page.controls.clear()
        page.add(ft.Container(content=ft.Text(f"STARTUP ERROR:\n{str(err)}", size=15, color="#FFFFFF"), bgcolor=C["red"], padding=20))
        page.update()

if __name__ == "__main__":
    ft.app(target=main)
