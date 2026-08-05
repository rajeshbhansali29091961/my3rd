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
    "ADANIENT":"अदानी एंटरप्राइजेज","ADANIGREEN":"अदानी ग्रीन",
    "DLF":"डीएलएफ","GODREJPROP":"गोदरेज प्रॉपर्टीज",
    "BRITANNIA":"ब्रिटानिया","DABUR":"डाबर इंडिया",
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
    "MANAGEMENT":"मैनेजमेंट","CONSULTING":"कंसल्टिंग",
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
    sess.get("https://www.nseindia.com", timeout=8)
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
    try:
        return fetch_nse_quote(symbol)
    except Exception as nse_err:
        try:
            return fetch_yahoo_quote(symbol)
        except Exception as yahoo_err:
            raise RuntimeError(f"NSE failed ({nse_err}); Yahoo Finance fallback also failed ({yahoo_err})")

# ── COLORS ─────────────────────────────────────────────────────────────────────
C = {
    "bg":        "#FFFFFF",
    "primary":   "#0D47A1",
    "secondary": "#1565C0",
    "accent":    "#1976D2",
    "dark_txt":  "#0D47A1",
    "black_txt": "#212121",
    "hint_txt":  "#546E7A",
    "green":     "#1B5E20",
    "orange":    "#BF360C",
    "red":       "#B71C1C",
    "inp_bg":    "#F3F8FF",
    "res_bg":    "#EEF4FF",
    "row_odd":   "#F3F8FF",
    "row_even":  "#FFFFFF",
    "divider":   "#90CAF9",
}

# ── HELPER FUNCTIONS ───────────────────────────────────────────────────────────
def parse_dt(s):
    if not s: return None
    for f in ("%d-%m-%Y","%Y-%m-%d","%d/%m/%Y","%d-%b-%Y"):
        try: return datetime.strptime(s.strip(), f)
        except: pass
    return None

def quick_verdict(asum, ldt_str):
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

# ── RAMAL PRASHNA ─────────────────────────────────────────────────────────────
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

IST_OFFSET_HOURS = 5.5

def jd_ut_from_ist(year, month, day, hour, minute):
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
        10: {"poly": [(x1, cy), (cx, y1), (cx, cy)],           "txt": (cx + 45, cy - 15), "planets": (cx + 45, cy + 5)},
        11: {"poly": [(x1, y0), (x1, cy), (cx, y0)],           "txt": (x1 - 25, y0 + 55), "planets": (x1 - 25, y0 + 75)},
        12: {"poly": [(x1, y0), (cx, y0), (x1, cy)],           "txt": (x1 - 35, y0 + 25), "planets": (x1 - 35, y0 + 45)},
    }

    shapes = []
    if add_fill:
        shapes.append(cv.Rect(x0, y0, W - 2*p, W - 2*p, paint=ft.Paint(color="#FFFFFF", style=ft.PaintingStyle.FILL)))

    # Outer border
    shapes.append(cv.Rect(x0, y0, W - 2*p, W - 2*p, paint=ft.Paint(color="#0D47A1", stroke_width=2, style=ft.PaintingStyle.STROKE)))
    # Diagonals & Crosses
    shapes.append(cv.Line(x0, y0, x1, y1, paint=ft.Paint(color="#1565C0", stroke_width=1.5)))
    shapes.append(cv.Line(x0, y1, x1, y0, paint=ft.Paint(color="#1565C0", stroke_width=1.5)))
    shapes.append(cv.Line(cx, y0, x0, cy, paint=ft.Paint(color="#1565C0", stroke_width=1.5)))
    shapes.append(cv.Line(x0, cy, cx, y1, paint=ft.Paint(color="#1565C0", stroke_width=1.5)))
    shapes.append(cv.Line(cx, y1, x1, cy, paint=ft.Paint(color="#1565C0", stroke_width=1.5)))
    shapes.append(cv.Line(x1, cy, cx, y0, paint=ft.Paint(color="#1565C0", stroke_width=1.5)))

    # Title
    shapes.append(cv.Text(cx, y0 + 12, title, ft.TextStyle(size=12, weight=ft.FontWeight.BOLD, color="#0D47A1"), alignment=ft.alignment.center))

    # Map planets to houses
    house_planets = {h: [] for h in range(1, 13)}
    for k, val in positions.items():
        s_idx = val if isinstance(val, int) else val[0]
        h_idx = ((s_idx - lagna_sign) % 12) + 1
        label = k
        if k in retro: label += "(R)"
        if k in vargottama: label += "*"
        house_planets[h_idx].append(label)

    # Render house numbers and planets
    for h in range(1, 13):
        sign_for_house = ((lagna_sign + h - 1) % 12) + 1
        tx, ty = HOUSES_GEOM[h]["txt"]
        shapes.append(cv.Text(tx, ty, str(sign_for_house), ft.TextStyle(size=10, weight=ft.FontWeight.BOLD, color="#B71C1C"), alignment=ft.alignment.center))
        
        plist = house_planets[h]
        if plist:
            px, py = HOUSES_GEOM[h]["planets"]
            ptext = " ".join(plist)
            shapes.append(cv.Text(px, py, ptext, ft.TextStyle(size=9, weight=ft.FontWeight.W_500, color="#212121"), alignment=ft.alignment.center))

    return shapes

def draw_north_indian_chart(positions, lagna_sign, title, size=320):
    shapes = _diamond_shapes(positions, lagna_sign, title, chart_size=size)
    return ft.Container(
        content=cv.Canvas(shapes, width=size, height=size),
        width=size, height=size, alignment=ft.alignment.center
    )

def draw_dual_chart(d1_pos, d1_lagna, d9_pos, d9_lagna, size=320):
    shapes_d1 = _diamond_shapes(d1_pos, d1_lagna, "D1 (Rashi)", chart_size=size, y_off=0, add_fill=True)
    shapes_d9 = _diamond_shapes(d9_pos, d9_lagna, "D9 (Navamsha)", chart_size=size, y_off=size + 10, add_fill=True)
    total_h = (size * 2) + 10
    return ft.Container(
        content=cv.Canvas(shapes_d1 + shapes_d9, width=size, height=total_h),
        width=size, height=total_h, alignment=ft.alignment.center
    )

# ── DATABASE MANAGEMENT ────────────────────────────────────────────────────────
def init_db(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE NOT NULL,
            name_eng TEXT NOT NULL,
            name_hin TEXT NOT NULL,
            listing_date TEXT
        )
    """)
    c.execute("SELECT COUNT(*) FROM stocks")
    count = c.fetchone()[0]
    if count == 0:
        default_data = [
            ("SBIN", "State Bank of India", "भारतीय स्टेट बैंक", "01-01-1995"),
            ("RELIANCE", "Reliance Industries Limited", "रिलायंस इंडस्ट्रीज लिमिटेड", "15-01-1977"),
            ("TCS", "Tata Consultancy Services Limited", "टाटा कंसल्टेंसी सर्विसेज लिमिटेड", "25-08-2004"),
            ("INFY", "Infosys Limited", "इन्फोसिस लिमिटेड", "14-06-1993"),
            ("HDFCBANK", "HDFC Bank Limited", "एचडीएफसी बैंक लिमिटेड", "19-05-1995"),
            ("ICICIBANK", "ICICI Bank Limited", "आईसीआईसीआई बैंक लिमिटेड", "17-09-1997"),
            ("AXISBANK", "Axis Bank Limited", "एक्सिस बैंक लिमिटेड", "16-11-1998"),
            ("WIPRO", "Wipro Limited", "विप्रो लिमिटेड", "08-11-1995"),
            ("NTPC", "NTPC Limited", "राष्ट्रीय ताप विद्युत निगम लिमिटेड", "05-11-2004"),
            ("ONGC", "Oil and Natural Gas Corporation Limited", "तेल और प्राकृतिक गैस निगम लिमिटेड", "20-07-1995"),
        ]
        c.executemany("INSERT INTO stocks (symbol, name_eng, name_hin, listing_date) VALUES (?, ?, ?, ?)", default_data)
        conn.commit()
    conn.close()

def get_stocks_by_letter(db_path, alpha="ALL"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    if alpha == "ALL" or not alpha:
        query = "SELECT symbol, name_eng, name_hin, listing_date FROM stocks ORDER BY symbol ASC LIMIT 200"
        cursor.execute(query)
    else:
        query = """
            SELECT symbol, name_eng, name_hin, listing_date 
            FROM stocks 
            WHERE symbol LIKE ? OR name_eng LIKE ? 
            ORDER BY symbol ASC
        """
        pattern = f"{alpha}%"
        cursor.execute(query, (pattern, pattern))
    rows = cursor.fetchall()
    conn.close()
    return rows

def sync_nse_database(db_path, status_callback=None):
    if not REQUESTS_OK:
        if status_callback: status_callback("Error: 'requests' module not installed.")
        return
    try:
        if status_callback: status_callback("Downloading NSE Equity List...")
        resp = requests.get(NSE_URL, timeout=15)
        resp.raise_for_status()
        
        csv_text = resp.content.decode('utf-8', errors='ignore')
        reader = csv.DictReader(io.StringIO(csv_text))
        
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        added = 0
        updated = 0
        
        for idx, row in enumerate(reader):
            sym = row.get("SYMBOL", "").strip()
            name_eng = row.get("NAME OF COMPANY", "").strip()
            ldate = row.get("DATE OF LISTING", "").strip()
            
            if not sym or not name_eng:
                continue
                
            name_hin = get_hindi(sym, name_eng)
            parsed_date = parse_dt(ldate)
            formatted_date = parsed_date.strftime("%d-%m-%Y") if parsed_date else ldate

            c.execute("SELECT id FROM stocks WHERE symbol = ?", (sym,))
            exists = c.fetchone()
            if exists:
                c.execute("UPDATE stocks SET name_eng=?, name_hin=?, listing_date=? WHERE symbol=?",
                          (name_eng, name_hin, formatted_date, sym))
                updated += 1
            else:
                c.execute("INSERT INTO stocks (symbol, name_eng, name_hin, listing_date) VALUES (?, ?, ?, ?)",
                          (sym, name_eng, name_hin, formatted_date))
                added += 1
                
            if status_callback and idx % 50 == 0:
                status_callback(f"Synced {idx} stocks... (+{added} new)")
                
        conn.commit()
        conn.close()
        if status_callback: status_callback(f"Sync Complete! Added: {added}, Updated: {updated}")
    except Exception as e:
        if status_callback: status_callback(f"Sync Failed: {str(e)}")

# ── MAIN FLET APP ─────────────────────────────────────────────────────────────
def main(page: ft.Page):
    page.title = "Bhoovalaya Oracle & Stock Financial Astrology"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = C["bg"]
    page.padding = 10
    page.scroll = ft.ScrollMode.AUTO

    db_path = os.path.join(os.path.dirname(__file__), "oracle_stocks.db")
    init_db(db_path)

    # UI State & Containers
    report_output = ft.Text(value="Select or enter a stock to view detailed Bhoovalaya analysis.", size=12, color=C["black_txt"], selectable=True)
    live_price_txt = ft.Text(value="", size=14, weight=ft.FontWeight.BOLD, color=C["primary"])
    chart_container = ft.Container(alignment=ft.alignment.center)
    ramal_container = ft.Container(alignment=ft.alignment.center)

    # Inputs
    sym_inp = ft.TextField(label="Symbol (e.g. SBIN)", width=150, bgcolor=C["inp_bg"])
    eng_inp = ft.TextField(label="Company Name (English)", expand=True, bgcolor=C["inp_bg"])
    hin_inp = ft.TextField(label="Company Name (Hindi)", expand=True, bgcolor=C["inp_bg"])
    dt_inp  = ft.TextField(label="Listing Date (DD-MM-YYYY)", width=180, bgcolor=C["inp_bg"])

    # Search / Autocomplete Handler
    def on_select_stock(sym, eng, hin, ldate):
        sym_inp.value = sym
        eng_inp.value = eng
        hin_inp.value = hin
        dt_inp.value = ldate
        page.update()
        run_full_analysis()

    # Dynamic Alphabet Browser Component
    stock_list_column = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)
    selected_alpha_text = ft.Text(value="Showing: ALL", size=13, weight=ft.FontWeight.BOLD, color=C["primary"])

    def refresh_stock_list(alpha="ALL"):
        selected_alpha_text.value = f"Showing: {alpha}"
        stock_list_column.controls.clear()
        stocks = get_stocks_by_letter(db_path, alpha)
        
        if not stocks:
            stock_list_column.controls.append(
                ft.Container(
                    content=ft.Text(f"No stocks found starting with '{alpha}'", color=C["hint_txt"]),
                    padding=15, alignment=ft.alignment.center
                )
            )
        else:
            for idx, (sym, n_eng, n_hin, ldate) in enumerate(stocks):
                asum, _ = calc(n_hin if n_hin else n_eng)
                combined_dir, has_vedha = quick_verdict(asum, ldate)
                
                bg_col = C["row_odd"] if idx % 2 == 0 else C["row_even"]
                vedha_badge = " ⚠️ VEDHA" if has_vedha else ""
                
                row_item = ft.Container(
                    content=ft.Row([
                        ft.Column([
                            ft.Text(f"{sym}", weight=ft.FontWeight.BOLD, size=13, color=C["black_txt"]),
                            ft.Text(f"{n_hin or n_eng}", size=11, color=C["hint_txt"]),
                        ], expand=True),
                        ft.Text(f"{combined_dir}{vedha_badge}", size=11, weight=ft.FontWeight.BOLD, color=C["primary"])
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    bgcolor=bg_col,
                    padding=8,
                    border_radius=4,
                    margin=ft.margin.only(bottom=2),
                    on_click=lambda e, s=sym, en=n_eng, hi=n_hin, d=ldate: on_select_stock(s, en, hi, d)
                )
                stock_list_column.controls.append(row_item)
        page.update()

    def on_alpha_click(e):
        refresh_stock_list(e.control.data)

    alphabet_buttons = []
    letters = ["ALL"] + [chr(code) for code in range(ord('A'), ord('Z') + 1)]
    for letter in letters:
        btn = ft.Container(
            content=ft.Text(letter, size=11, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
            alignment=ft.alignment.center,
            width=32, height=32,
            bgcolor=C["accent"],
            border_radius=16,
            data=letter,
            on_click=on_alpha_click,
        )
        alphabet_buttons.append(btn)

    alpha_index_bar = ft.Row(controls=alphabet_buttons, scroll=ft.ScrollMode.ALWAYS, spacing=4)

    # Core Calculation Logic
    def run_full_analysis():
        hin_name = hin_inp.value.strip()
        eng_name = eng_inp.value.strip()
        sym = sym_inp.value.strip().upper()
        ldt_str = dt_inp.value.strip()

        if not hin_name and eng_name:
            hin_name = get_hindi(sym, eng_name)
            hin_inp.value = hin_name

        target_name = hin_name or eng_name
        if not target_name:
            report_output.value = "Please enter a Stock Name or Symbol."
            page.update()
            return

        # 1. Bhoovalaya Report
        asum, _ = calc(target_name)
        ldate = parse_dt(ldt_str)
        today = datetime.now()
        tval = ((today - ldate).days % 730) if ldate else 0
        rep = make_report(asum, tval, ldate)
        report_output.value = rep

        # 2. Live Quote Fetching
        if sym and REQUESTS_OK:
            live_price_txt.value = "Fetching live quote..."
            page.update()
            
            def fetch_async():
                try:
                    q = fetch_stock_quote(sym)
                    lp = q.get('last_price', 'N/A')
                    chg = q.get('change', 0)
                    pchg = q.get('pchange', 0)
                    src = q.get('source', '')
                    col = C["green"] if (chg and chg >= 0) else C["red"]
                    sign = "+" if (chg and chg >= 0) else ""
                    live_price_txt.value = f"Live Price ({src}): ₹{lp} | {sign}{chg} ({sign}{pchg}%)"
                    live_price_txt.color = col
                except Exception as ex:
                    live_price_txt.value = f"Quote Unavailable ({ex})"
                    live_price_txt.color = C["orange"]
                page.update()
            
            threading.Thread(target=fetch_async, daemon=True).start()

        # 3. Vedic Astrological D1 + D9 Charts
        calc_dt = ldate if ldate else today
        jd_ut = jd_ut_from_ist(calc_dt.year, calc_dt.month, calc_dt.day, 10, 0)
        positions, ayan = calc_planet_positions(jd_ut)

        d1_pos = {}
        d9_pos = {}
        for p_code, lon in positions.items():
            s_idx, _ = lon_to_sign_deg(lon)
            d1_pos[p_code] = s_idx
            d9_pos[p_code] = d9_sign(lon)

        d1_lagna = d1_pos["As"]
        d9_lagna = d9_pos["As"]

        dual_chart_widget = draw_dual_chart(d1_pos, d1_lagna, d9_pos, d9_lagna, size=300)
        chart_container.content = dual_chart_widget

        # 4. Ramal Prashna Cast
        ramal_data = cast_ramal_chart()
        j_info = ramal_data["judge_info"]
        f_info = ramal_data["final_info"]
        rec_tag, rec_desc = ramal_recommendation(j_info, f_info)

        ramal_card = ft.Container(
            content=ft.Column([
                ft.Text("🔮 RAMAL PRASHNA (16-HOUSE PRASHNA)", size=14, weight=ft.FontWeight.BOLD, color=C["primary"]),
                ft.Text(f"Judge (15th House): {j_info['name']} | {j_info['nature']} ({j_info['bias']})", size=12, weight=ft.FontWeight.BOLD),
                ft.Text(f"Final Outcome (16th House): {f_info['name']} | {f_info['nature']} ({f_info['bias']})", size=12, weight=ft.FontWeight.BOLD),
                ft.Divider(color=C["divider"]),
                ft.Text(rec_desc, size=12, weight=ft.FontWeight.BOLD, color=C["green"] if rec_tag=="BUY" else (C["red"] if rec_tag=="SELL" else C["orange"])),
            ]),
            bgcolor=C["res_bg"], padding=10, border_radius=6, margin=ft.margin.only(top=10)
        )
        ramal_container.content = ramal_card
        page.update()

    # Sync Button Handler
    sync_status_txt = ft.Text("", size=11, color=C["hint_txt"])
    def on_sync_click(e):
        def run_sync():
            sync_nse_database(db_path, lambda msg: setattr(sync_status_txt, "value", msg) or page.update())
            refresh_stock_list("ALL")
        threading.Thread(target=run_sync, daemon=True).start()

    # UI Layout Construction
    refresh_stock_list("ALL")

    page.add(
        ft.Text("Bhoovalaya Oracle & Financial Astrology", size=20, weight=ft.FontWeight.BOLD, color=C["primary"]),
        ft.Row([
            sym_inp,
            ft.ElevatedButton("Analyze", on_click=lambda e: run_full_analysis(), bgcolor=C["primary"], color="#FFFFFF"),
            ft.OutlinedButton("Sync NSE DB", on_click=on_sync_click),
        ]),
        sync_status_txt,
        ft.Row([eng_inp, hin_inp]),
        dt_inp,
        ft.Divider(color=C["divider"]),
        live_price_txt,
        
        # Main Tabbed Content Area
        ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(
                    text="Analysis Report",
                    content=ft.Container(
                        content=ft.Column([
                            report_output,
                            ramal_container
                        ], scroll=ft.ScrollMode.AUTO),
                        padding=10
                    )
                ),
                ft.Tab(
                    text="D1 & D9 Kundali",
                    content=ft.Container(
                        content=chart_container,
                        padding=10, alignment=ft.alignment.center
                    )
                ),
                ft.Tab(
                    text="A-Z Stock Directory",
                    content=ft.Container(
                        content=ft.Column([
                            selected_alpha_text,
                            ft.Container(content=alpha_index_bar, padding=ft.padding.only(top=4, bottom=8)),
                            ft.Divider(color=C["divider"]),
                            stock_list_column
                        ], expand=True),
                        padding=10
                    )
                ),
            ],
            expand=True
        )
    )

if __name__ == "__main__":
    ft.app(target=main)
