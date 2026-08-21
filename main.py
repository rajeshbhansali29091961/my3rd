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

# ── PANCHANGA (Tithi / Yoga / Karana) ─────────────────────────────────────────
# Standard Vedic Panchanga limbs 3-5 (Vara=weekday and Nakshatra are already handled
# elsewhere in this file). All three below depend only on the Sun-Moon angular
# relationship, so sidereal vs tropical longitude doesn't matter as long as both
# Sun and Moon longitudes come from the SAME system (ayanamsa cancels out in the
# difference/sum) — we feed it the sidereal values already computed elsewhere.
TITHI_NAMES_SHUKLA = [
    "प्रतिपदा Pratipada","द्वितीया Dwitiya","तृतीया Tritiya","चतुर्थी Chaturthi","पंचमी Panchami",
    "षष्ठी Shashthi","सप्तमी Saptami","अष्टमी Ashtami","नवमी Navami","दशमी Dashami",
    "एकादशी Ekadashi","द्वादशी Dwadashi","त्रयोदशी Trayodashi","चतुर्दशी Chaturdashi","पूर्णिमा Purnima"
]
TITHI_NAMES_KRISHNA = TITHI_NAMES_SHUKLA[:14] + ["अमावस्या Amavasya"]
# Tithis conventionally treated as inauspicious/caution for new undertakings (Rikta
# tithis 4,9,14 in both Pakshas) — used only as a soft caution note here, nothing more.
RIKTA_TITHI_NUMS = {4, 9, 14}

YOGA_NAMES = [
    "विष्कुम्भ Vishkambha","प्रीति Priti","आयुष्मान Ayushman","सौभाग्य Saubhagya","शोभन Shobhana",
    "अतिगण्ड Atiganda","सुकर्मा Sukarma","धृति Dhriti","शूल Shoola","गण्ड Ganda",
    "वृद्धि Vriddhi","ध्रुव Dhruva","व्याघात Vyaghata","हर्षण Harshana","वज्र Vajra",
    "सिद्धि Siddhi","व्यतीपात Vyatipata","वरीयान Variyana","परिघ Parigha","शिव Shiva",
    "सिद्ध Siddha","साध्य Sadhya","शुभ Shubha","शुक्ल Shukla","ब्रह्म Brahma",
    "इन्द्र Indra","वैधृति Vaidhriti"
]
# Yogas classically flagged as inauspicious/obstructive (soft caution only)
INAUSPICIOUS_YOGAS = {"व्यतीपात Vyatipata", "वैधृति Vaidhriti", "शूल Shoola", "व्याघात Vyaghata", "गण्ड Ganda"}

KARANA_MOVABLE = ["बव Bava","बालव Balava","कौलव Kaulava","तैतिल Taitila","गरज Garija","वणिज Vanija","विष्टि Vishti (Bhadra)"]
KARANA_FIXED_END = ["शकुनि Shakuni","चतुष्पद Chatushpada","नाग Naga"]
KARANA_FIXED_START = "किंस्तुघ्न Kimstughna"

def compute_panchanga(sun_lon, moon_lon):
    """Returns (tithi_name, tithi_num, paksha, yoga_name, karana_name, caution_notes[])."""
    diff = (moon_lon - sun_lon) % 360
    tithi_num = int(diff / 12) + 1  # 1..30
    if tithi_num <= 15:
        paksha, t_in_paksha = "Shukla (Waxing)", tithi_num
        tithi_name = TITHI_NAMES_SHUKLA[t_in_paksha - 1]
    else:
        paksha, t_in_paksha = "Krishna (Waning)", tithi_num - 15
        tithi_name = TITHI_NAMES_KRISHNA[t_in_paksha - 1]

    yoga_val = (sun_lon + moon_lon) % 360
    yoga_num = int(yoga_val / (360.0 / 27.0)) % 27
    yoga_name = YOGA_NAMES[yoga_num]

    karana_num = int(diff / 6) + 1  # 1..60
    if karana_num == 1:
        karana_name = KARANA_FIXED_START
    elif karana_num >= 58:
        karana_name = KARANA_FIXED_END[min(karana_num - 58, 2)]
    else:
        karana_name = KARANA_MOVABLE[(karana_num - 2) % 7]

    notes = []
    if t_in_paksha in RIKTA_TITHI_NUMS:
        notes.append("⚠️ Rikta Tithi (4th/9th/14th) — classically avoided for fresh starts")
    if yoga_name in INAUSPICIOUS_YOGAS:
        notes.append("⚠️ Inauspicious Yoga (" + yoga_name + ") — extra caution advised")
    if "Vishti" in karana_name:
        notes.append("⚠️ Vishti/Bhadra Karana — traditionally avoided for new undertakings")
    return tithi_name, tithi_num, paksha, yoga_name, karana_name, notes

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

IST_OFFSET_HOURS = 5.5  # India Standard Time = UTC + 5:30 — DEFAULT fallback only; the app's
                          # actual working offset now comes from the user's saved Place setting.

def jd_ut_from_ist(year, month, day, hour, minute, gmt_offset_hours=IST_OFFSET_HOURS):
    """Julian Day formulas (and GMST/Ascendant) require UT. Our date/time fields and
    datetime.now() are assumed to be in the local clock time of gmt_offset_hours (IST/UTC+5:30
    by default, but configurable via Place Settings), so subtract the offset to get true UT."""
    jd_local = jd_from_dt(year, month, day, hour, minute)
    return jd_local - (gmt_offset_hours / 24.0)

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
            conn.execute("""CREATE TABLE IF NOT EXISTS simple_rules(
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                planet              TEXT NOT NULL DEFAULT 'ANY',
                d1_house            INTEGER,
                d1_rashi            INTEGER,
                d1_list             TEXT,
                d9_house            INTEGER,
                d9_rashi            INTEGER,
                d9_aspect           INTEGER DEFAULT 0,
                vargottama          INTEGER DEFAULT 0,
                same_house          INTEGER DEFAULT 0,
                companion_planet    TEXT,
                companion_d9_house  INTEGER,
                retro_only          INTEGER DEFAULT 0,
                weight              REAL DEFAULT 1.0,
                action              TEXT NOT NULL DEFAULT 'BUY',
                struct_src_chart    TEXT,
                struct_src_house    INTEGER,
                struct_tgt_chart    TEXT,
                struct_tgt_list     TEXT,
                struct_aspect       TEXT,
                struct_aspect_planets TEXT,
                struct_aspect_mode  TEXT,
                rule_name           TEXT,
                struct_src_empty    TEXT)""")
            for coldef in ("struct_src_chart TEXT", "struct_src_house INTEGER",
                           "struct_tgt_chart TEXT", "struct_tgt_list TEXT", "struct_aspect TEXT",
                           "struct_aspect_planets TEXT", "struct_aspect_mode TEXT",
                           "rule_name TEXT", "struct_src_empty TEXT"):
                try:
                    conn.execute(f"ALTER TABLE simple_rules ADD COLUMN {coldef}")
                    conn.commit()
                except Exception:
                    pass  # column already exists on installs upgraded from an earlier version
            # Place Settings — user-configurable reference location + GMT offset used by every
            # "automatic" astro calculation in the app (Oracle's CALCULATE ASTRO, the Stocks tab's
            # Live Timing Signal, and as the default prefill on the Kundali Engines page). Stored as
            # simple key-value pairs so new settings can be added later without another migration.
            conn.execute("""CREATE TABLE IF NOT EXISTS app_settings(
                key   TEXT PRIMARY KEY,
                value TEXT)""")
            conn.commit()
            conn.close()
        except: pass

        PLACE_DEFAULTS = {"place_name": "Mumbai", "latitude": "19.076", "longitude": "72.877", "gmt_offset": "5.5"}

        def get_place_settings():
            """Reads the saved Place Settings, falling back to the Mumbai/IST defaults
            (the same values this app always used) for any key not yet saved."""
            result = dict(PLACE_DEFAULTS)
            try:
                conn = sqlite3.connect(db_path)
                rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
                conn.close()
                for k, v in rows:
                    if k in result and v not in (None, ""):
                        result[k] = v
            except Exception:
                pass
            return result

        def save_place_settings(place_name, latitude, longitude, gmt_offset):
            conn = sqlite3.connect(db_path)
            for k, v in (("place_name", place_name), ("latitude", str(latitude)),
                         ("longitude", str(longitude)), ("gmt_offset", str(gmt_offset))):
                conn.execute("""INSERT INTO app_settings(key, value) VALUES(?, ?)
                                 ON CONFLICT(key) DO UPDATE SET value=excluded.value""", (k, v))
            conn.commit()
            conn.close()

        current_place = get_place_settings()  # loaded once at startup; refreshed in-memory on Save

        RASHI_LIST = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo",
                      "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
        HOUSE_OPTIONS  = ["Any"] + [str(i) for i in range(1, 13)]
        RASHI_OPTIONS  = ["Any"] + RASHI_LIST
        PLANET_OPTIONS = ["ANY", "Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"]
        PLANET_ONLY_OPTIONS = ["Any", "Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"]  # for the Companion column
        YES_NO_OPTIONS = ["No", "Yes"]
        YES_NO_ANY_OPTIONS = ["Any", "Yes", "No"]
        ACTION_OPTIONS = ["BUY", "SELL", "NEUTRAL", "WAIT"]
        CHART_OPTIONS  = ["D1", "D9"]
        ASPECT_MODE_OPTIONS = ["Any", "None Aspect", "At Least One", "All Aspect"]

        # Classical Parashari drishti (aspect) rules, used only when a row's "Aspect"
        # column is set to Yes: EVERY planet aspects the 7th house from its own D9
        # position; Mars/Jupiter/Saturn also cast special extra aspects. Rahu/Ketu have
        # no single agreed classical aspect scheme — by common modern convention this
        # app treats them like Saturn (3rd/7th/10th), noted honestly rather than
        # presented as ancient doctrine.
        ASPECT_EXTRA_HOUSES = {"Ma": [4, 8], "Ju": [5, 9], "Sa": [3, 10], "Ra": [3, 10], "Ke": [3, 10]}

        def planet_aspect_houses(planet_key, house_pos):
            """Houses (1-12) aspected by a planet currently sitting in house_pos."""
            offsets = [7] + ASPECT_EXTRA_HOUSES.get(planet_key, [])
            return {((int(house_pos) - 1 + (off - 1)) % 12) + 1 for off in offsets}

        def rashi_of_house(house_no, lagna_sign_idx):
            """0-indexed sign occupying a given house number, given the lagna sign."""
            return (int(lagna_sign_idx) + int(house_no) - 1) % 12

        def simple_rule_add(planet, d1_house, d1_rashi, d1_list, d9_house, d9_rashi,
                             d9_aspect, vargottama, same_house, companion_planet,
                             companion_d9_house, retro_only, weight, action,
                             struct_src_chart=None, struct_src_house=None,
                             struct_tgt_chart=None, struct_tgt_list=None, struct_aspect=None,
                             struct_aspect_planets=None, struct_aspect_mode=None,
                             rule_name=None, struct_src_empty=None):
            conn = sqlite3.connect(db_path)
            conn.execute("""INSERT INTO simple_rules(planet,d1_house,d1_rashi,d1_list,d9_house,d9_rashi,
                             d9_aspect,vargottama,same_house,companion_planet,companion_d9_house,
                             retro_only,weight,action,struct_src_chart,struct_src_house,struct_tgt_chart,
                             struct_tgt_list,struct_aspect,struct_aspect_planets,struct_aspect_mode,
                             rule_name,struct_src_empty)
                             VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                         (planet, d1_house, d1_rashi, d1_list, d9_house, d9_rashi,
                          1 if d9_aspect else 0, 1 if vargottama else 0, 1 if same_house else 0,
                          companion_planet, companion_d9_house, 1 if retro_only else 0, weight, action,
                          struct_src_chart, struct_src_house, struct_tgt_chart, struct_tgt_list, struct_aspect,
                          struct_aspect_planets, struct_aspect_mode, rule_name, struct_src_empty))
            conn.commit(); conn.close()

        def simple_rule_update(rule_id, planet, d1_house, d1_rashi, d1_list, d9_house, d9_rashi,
                                d9_aspect, vargottama, same_house, companion_planet,
                                companion_d9_house, retro_only, weight, action,
                                struct_src_chart=None, struct_src_house=None,
                                struct_tgt_chart=None, struct_tgt_list=None, struct_aspect=None,
                                struct_aspect_planets=None, struct_aspect_mode=None,
                                rule_name=None, struct_src_empty=None):
            conn = sqlite3.connect(db_path)
            conn.execute("""UPDATE simple_rules SET planet=?, d1_house=?, d1_rashi=?, d1_list=?, d9_house=?,
                             d9_rashi=?, d9_aspect=?, vargottama=?, same_house=?, companion_planet=?,
                             companion_d9_house=?, retro_only=?, weight=?, action=?, struct_src_chart=?,
                             struct_src_house=?, struct_tgt_chart=?, struct_tgt_list=?, struct_aspect=?,
                             struct_aspect_planets=?, struct_aspect_mode=?, rule_name=?, struct_src_empty=?
                             WHERE id=?""",
                         (planet, d1_house, d1_rashi, d1_list, d9_house, d9_rashi,
                          1 if d9_aspect else 0, 1 if vargottama else 0, 1 if same_house else 0,
                          companion_planet, companion_d9_house, 1 if retro_only else 0, weight, action,
                          struct_src_chart, struct_src_house, struct_tgt_chart, struct_tgt_list, struct_aspect,
                          struct_aspect_planets, struct_aspect_mode, rule_name, struct_src_empty, rule_id))
            conn.commit(); conn.close()

        def simple_rule_delete(rule_id):
            conn = sqlite3.connect(db_path)
            conn.execute("DELETE FROM simple_rules WHERE id=?", (rule_id,))
            conn.commit(); conn.close()

        def simple_rule_list():
            conn = sqlite3.connect(db_path)
            rows = conn.execute("""SELECT id,planet,d1_house,d1_rashi,d1_list,d9_house,d9_rashi,
                                    d9_aspect,vargottama,same_house,companion_planet,companion_d9_house,
                                    retro_only,weight,action,struct_src_chart,struct_src_house,
                                    struct_tgt_chart,struct_tgt_list,struct_aspect,
                                    struct_aspect_planets,struct_aspect_mode,rule_name,struct_src_empty
                                    FROM simple_rules ORDER BY id""").fetchall()
            conn.close()
            return rows

        def get_house_num(sign_idx, lagna_sign_idx):
            """Convert a raw sign index (0-11) to a house number (1-12) relative to the lagna."""
            return ((int(sign_idx) - int(lagna_sign_idx)) % 12) + 1

        def apply_timing_flag(score, wait_matches):
            """Shared GOOD/BAD-timing flag shown at the very top of the Stocks/Show All
            page — same custom-rules verdict (score + WAIT matches) that CALCULATE ASTRO
            and the Live Timing Signal below use, so all three always agree."""
            if wait_matches:
                top_timing_text.value = "🟡 WAIT — HOLD OFF TRADING TODAY  (custom WAIT rule matched)"
                top_timing_flag_container.bgcolor = C["orange"]
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
            """Runs every saved grid rule against the current chart and returns
            (matches, net_score, wait_matches).

            Every rule row can carry ANY combination of these columns — every column
            you actually set must ALL be true at once (AND) for the rule to fire;
            leaving a column at its default (Any / No / blank) simply skips that
            check. This one AND-of-filled-columns engine covers every situation the
            old named rule-types covered, plus combinations none of them could:
              D1 House / D1 Rashi / D1 List (house is one of several) / D9 House /
              D9 Rashi / D9 Aspect (D9 House = house ASPECTED, not occupied) /
              Vargottama / Same House (D1 house == D9 house) / Companion Planet+D9
              House (a second planet that must ALSO be there) / Retrograde-only /
              Weight.

            Rashi-in-House Match (struct_* fields) is a DIFFERENT kind of condition:
            it is about the CHART ITSELF, not any planet.
              • struct_tgt_list: "does the rashi sitting in Source Chart's Source
                House also sit in one of Target Chart's Target House List houses?"
              • struct_aspect (Yes/No/Any): "is the Source Chart's Source House
                aspected by ANY planet at all?" — computed once across every planet
                in that chart, not tied to a particular one.
              • struct_aspect_planets + struct_aspect_mode: a NAMED-planet version
                of the same idea — e.g. "is the Source House aspected by Mars OR
                Saturn specifically" (mode=At Least One), "by BOTH Mars AND Saturn"
                (mode=All Aspect), or "by NEITHER Mars NOR Saturn" (mode=None Aspect).
            All depend only on lagna positions and overall chart layout, never on
            a single named planet from the Planet field above. If a rule sets ONLY
            these (Planet left at ANY, no other planet-specific field set), it fires
            once for the whole chart. If combined with planet fields too, they act
            as extra AND gates applied to every planet the rest of the row is checking.

            WAIT rules are kept separate from the BUY/SELL numeric score — a single
            genuine WAIT match is a hard caution flag, not something a pile of small
            BUY matches elsewhere should be able to outweigh."""
            houses_d1 = {p: get_house_num(s, lagna_d1) for p, s in d1_pos.items() if p != "As"}
            houses_d9 = {p: get_house_num(s, lagna_d9) for p, s in d9_pos.items() if p != "As"}
            matches, wait_matches, score = [], [], 0.0
            for (rid, planet, d1_house, d1_rashi, d1_list, d9_house, d9_rashi,
                 d9_aspect, vargottama, same_house, comp_planet, comp_d9_house,
                 retro_only, weight, action, struct_src_chart, struct_src_house,
                 struct_tgt_chart, struct_tgt_list, struct_aspect,
                 struct_aspect_planets, struct_aspect_mode, rule_name, struct_src_empty) in simple_rule_list():

                # ── Rashi-in-House Match + "aspected by any/named planet" + Occupancy — chart-level facts, computed once ──
                has_named_aspect_check = bool(struct_aspect_planets) and struct_aspect_mode in ("None Aspect", "At Least One", "All Aspect")
                has_empty_check = struct_src_empty in ("Empty", "Occupied")
                struct_enabled = struct_src_house is not None and (bool(struct_tgt_list) or struct_aspect in ("Yes", "No") or has_named_aspect_check or has_empty_check)
                struct_ok = True
                if struct_enabled:
                    src_lagna = lagna_d9 if struct_src_chart == "D9" else lagna_d1
                    if struct_tgt_list:
                        tgt_lagna = lagna_d9 if struct_tgt_chart == "D9" else lagna_d1
                        src_rashi = rashi_of_house(struct_src_house, src_lagna)
                        try:
                            tgt_houses = [int(x.strip()) for x in struct_tgt_list.split(",") if x.strip()]
                        except ValueError:
                            tgt_houses = []
                        tgt_rashis = {rashi_of_house(h, tgt_lagna) for h in tgt_houses}
                        struct_ok = struct_ok and (src_rashi in tgt_rashis)
                    if struct_aspect in ("Yes", "No"):
                        src_houses_map = houses_d9 if struct_src_chart == "D9" else houses_d1
                        aspected_by_any = any(struct_src_house in planet_aspect_houses(p, h) for p, h in src_houses_map.items())
                        struct_ok = struct_ok and (aspected_by_any if struct_aspect == "Yes" else (not aspected_by_any))
                    if has_named_aspect_check:
                        # Named-planet aspect check: e.g. "not aspected by Mars AND Saturn"
                        # (mode=None Aspect), "aspected by at least one of Mars/Saturn"
                        # (At Least One), or "aspected by both Mars AND Saturn" (All Aspect).
                        src_houses_map = houses_d9 if struct_src_chart == "D9" else houses_d1
                        named_planets = [x.strip() for x in struct_aspect_planets.split(",") if x.strip()]
                        aspecting_named = [p for p in named_planets
                                            if p in src_houses_map and struct_src_house in planet_aspect_houses(p, src_houses_map[p])]
                        if struct_aspect_mode == "None Aspect":
                            struct_ok = struct_ok and (len(aspecting_named) == 0)
                        elif struct_aspect_mode == "At Least One":
                            struct_ok = struct_ok and (len(aspecting_named) >= 1)
                        elif struct_aspect_mode == "All Aspect":
                            struct_ok = struct_ok and (set(aspecting_named) == set(named_planets) and len(named_planets) > 0)
                    if has_empty_check:
                        # Occupancy: does ANY planet currently sit in Src Chart's Src House?
                        src_houses_map = houses_d9 if struct_src_chart == "D9" else houses_d1
                        is_occupied = any(h == struct_src_house for h in src_houses_map.values())
                        struct_ok = struct_ok and (is_occupied if struct_src_empty == "Occupied" else (not is_occupied))

                no_planet_filters = (d1_house is None and d1_rashi is None and not d1_list and
                                      d9_house is None and d9_rashi is None and not vargottama and
                                      not same_house and not comp_planet and not retro_only)

                if struct_enabled and planet == "ANY" and no_planet_filters:
                    # Pure chart-structure rule — fires once, not once per planet.
                    if struct_ok:
                        entry = ("(chart)", None, None, struct_src_house, None, False, False, False, action, weight)
                        if action == "WAIT":
                            wait_matches.append(entry)
                        else:
                            matches.append(entry)
                            w = weight if weight else 1.0
                            score += w if action == "BUY" else (-w if action == "SELL" else 0.0)
                    continue

                if struct_enabled and not struct_ok:
                    continue  # combined with planet fields, but the chart-structure fact is false — whole rule is out

                planets_to_check = [planet] if planet != "ANY" else list(houses_d1.keys())
                for pl in planets_to_check:
                    if pl not in houses_d1:
                        continue
                    if retro_only and pl not in retro_set:
                        continue
                    if d1_house is not None and houses_d1.get(pl) != d1_house:
                        continue
                    if d1_rashi is not None and d1_pos.get(pl) != (d1_rashi - 1):
                        continue
                    if d1_list:
                        try:
                            allowed = {int(x.strip()) for x in d1_list.split(",") if x.strip()}
                        except ValueError:
                            allowed = set()
                        if houses_d1.get(pl) not in allowed:
                            continue
                    if d9_aspect:
                        # d9_house here means "the D9 house being ASPECTED by this planet"
                        if d9_house is not None:
                            if houses_d9.get(pl) is None or d9_house not in planet_aspect_houses(pl, houses_d9.get(pl)):
                                continue
                    else:
                        if d9_house is not None and houses_d9.get(pl) != d9_house:
                            continue
                    if d9_rashi is not None and d9_pos.get(pl) != (d9_rashi - 1):
                        continue
                    if vargottama and not (d1_pos.get(pl) is not None and d1_pos.get(pl) == d9_pos.get(pl)):
                        continue
                    if same_house and not (houses_d1.get(pl) is not None and houses_d1.get(pl) == houses_d9.get(pl)):
                        continue
                    if comp_planet and comp_d9_house is not None and houses_d9.get(comp_planet) != comp_d9_house:
                        continue
                    entry = (pl, d1_house, d1_rashi, d9_house, d9_rashi, d9_aspect, vargottama, same_house, action, weight)
                    if action == "WAIT":
                        wait_matches.append(entry)
                    else:
                        matches.append(entry)
                        w = weight if weight else 1.0
                        score += w if action == "BUY" else (-w if action == "SELL" else 0.0)
            return matches, score, wait_matches

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
        last_chart_state = {"d1_pos": None, "d9_pos": None, "lagna_d1": None, "lagna_d9": None,
                             "retro_set": None, "label": None}  # last computed chart, used by the Rule Builder's TEST button

        def remember_chart_for_test(d1_pos, d9_pos, lagna_d1, lagna_d9, retro_set, label):
            last_chart_state.update({"d1_pos": d1_pos, "d9_pos": d9_pos, "lagna_d1": lagna_d1,
                                      "lagna_d9": lagna_d9, "retro_set": retro_set, "label": label})

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
                place_lat = float(current_place["latitude"])
                place_lon = float(current_place["longitude"])
                place_gmt = float(current_place["gmt_offset"])
                jd = jd_ut_from_ist(calc_time.year, calc_time.month, calc_time.day, calc_time.hour, calc_time.minute, place_gmt)
                pos, ay = calc_planet_positions(jd, place_lat, place_lon)  # user's saved Place Settings (default: Mumbai)

                d1_pos = {p: lon_to_sign_deg(l)[0] for p, l in pos.items()}
                d9_pos = {p: d9_sign(l) for p, l in pos.items()}
                lagna_idx = d1_pos["As"]
                lagna_d9  = d9_pos["As"]
                retro_set = get_retrograde_set(jd, place_lat, place_lon)
                vargottama_set = {p for p in d1_pos if p != "As" and d1_pos.get(p) == d9_pos.get(p)}

                oracle_astro_container.controls.clear()
                oracle_astro_container.controls.append(ft.Divider(height=6, color=C["divider"]))
                oracle_astro_container.controls.append(make_header("🕉️ VEDIC KUNDALI AT TIME OF CALCULATION"))
                oracle_astro_container.controls.append(ft.Text(
                    "📍 " + current_place["place_name"] + f" ({place_lat:g}, {place_lon:g}, GMT+{place_gmt:g})   " +
                    "📅 " + calc_time.strftime("%d-%m-%Y %H:%M") + "   ✨ Ayanamsa (Lahiri): " + str(round(ay, 4)) + "°" +
                    ("   ⟲ Retrograde: " + ", ".join(sorted(retro_set)) if retro_set else "") +
                    ("   ★ Vargottama: " + ", ".join(sorted(vargottama_set)) if vargottama_set else ""),
                    size=13, color=C["primary"], weight="bold"
                ))
                oracle_astro_container.controls.append(build_dual_diamond_chart_with_bars(d1_pos, lagna_idx, d9_pos, lagna_d9, retro=retro_set, vargottama=vargottama_set))

                # ── PANCHANGA (Tithi / Yoga / Karana) AT TIME OF CALCULATION ──
                tithi_name, tithi_num, paksha, yoga_name, karana_name, panch_notes = compute_panchanga(pos["Su"], pos["Mo"])
                oracle_astro_container.controls.append(ft.Container(height=6))
                oracle_astro_container.controls.append(make_header("🗓️ PANCHANGA (Tithi · Yoga · Karana)", bgcolor="#4E342E"))
                oracle_astro_container.controls.append(ft.Text(
                    f"Tithi  : {tithi_name}  ({paksha}, #{tithi_num})\n"
                    f"Yoga   : {yoga_name}\n"
                    f"Karana : {karana_name}",
                    size=13, color=C["black_txt"], weight="bold", selectable=True
                ))
                if panch_notes:
                    oracle_astro_container.controls.append(ft.Text("\n".join(panch_notes), size=11, color=C["orange"], weight="bold"))
                else:
                    oracle_astro_container.controls.append(ft.Text("✅ No classical Panchanga caution flags for this moment.", size=11, color=C["green"], weight="bold"))

                # ── CUSTOM RULES: BUY/SELL/WAIT RECOMMENDATION ──────────────
                remember_chart_for_test(d1_pos, d9_pos, lagna_idx, lagna_d9, retro_set,
                                        f"CALCULATE ASTRO @ {calc_time.strftime('%d-%m-%Y %H:%M')}")
                matches, score, wait_matches = evaluate_rules(d1_pos, d9_pos, lagna_idx, lagna_d9, retro_set)
                apply_timing_flag(score, wait_matches)  # keep the top-of-page flag in sync
                if wait_matches:
                    rec_text, rec_color = f"🟡 CUSTOM RULES: WAIT ON THIS STOCK TODAY  ({len(wait_matches)} wait-rule match{'es' if len(wait_matches) != 1 else ''})", C["orange"]
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
                def _fmt_match(entry):
                    pl, d1h, d1r, d9h, d9r, asp, varg, same, act, wt = entry
                    bits = []
                    if d1h is not None: bits.append(f"D1 House {d1h}")
                    if d1r is not None: bits.append(f"D1 {RASHI_LIST[d1r-1]}")
                    if d9h is not None: bits.append(f"D9 {'aspects House' if asp else 'House'} {d9h}")
                    if d9r is not None: bits.append(f"D9 {RASHI_LIST[d9r-1]}")
                    if varg: bits.append("Vargottama")
                    if same: bits.append("D1=D9 House")
                    where = ", ".join(bits) if bits else "any placement"
                    return f"{pl}  [{where}]  → {act}  (w={wt:g})"
                if wait_matches:
                    wait_detail = "\n".join("🟡 " + _fmt_match(m) for m in wait_matches)
                    oracle_astro_container.controls.append(ft.Text(wait_detail, size=11, color=C["orange"], weight="bold", selectable=True))
                if matches:
                    detail = "\n".join("• " + _fmt_match(m) for m in matches)
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
            ft.Text("🪐 Auto Astro (D1/D9) + Panchanga has moved to the Stocks / Show All page — tap the Stocks tab below.", size=12, color=C["hint_txt"]),
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
            place_lat = float(current_place["latitude"])
            place_lon = float(current_place["longitude"])
            place_gmt = float(current_place["gmt_offset"])
            jd = jd_ut_from_ist(now.year, now.month, now.day, now.hour, now.minute, place_gmt)
            pos, ay = calc_planet_positions(jd, place_lat, place_lon)
            d1_pos = {p: lon_to_sign_deg(l)[0] for p, l in pos.items()}
            d9_pos = {p: d9_sign(l) for p, l in pos.items()}
            lagna_idx, lagna_d9 = d1_pos["As"], d9_pos["As"]
            retro_set = get_retrograde_set(jd, place_lat, place_lon)
            remember_chart_for_test(d1_pos, d9_pos, lagna_idx, lagna_d9, retro_set,
                                    f"Live Timing Signal @ {now.strftime('%d-%m-%Y %H:%M')}")
            matches, score, wait_matches = evaluate_rules(d1_pos, d9_pos, lagna_idx, lagna_d9, retro_set)
            if wait_matches:
                return "WAIT", C["orange"], score, wait_matches
            elif score > 0:
                return "BUY", C["green"], score, wait_matches
            elif score < 0:
                return "SELL", C["red"], score, wait_matches
            else:
                return "NEUTRAL", C["accent"], score, wait_matches

        def stocks_recalc_loop(interval_seconds, stop_event):
            while not stop_event.is_set():
                label, color, score, wait_matches = compute_live_timing_signal()
                live_signal_text.value = f"⏱ LIVE TIMING SIGNAL: {label}"
                live_signal_container.bgcolor = color
                live_signal_text.color = "#FFFFFF"
                apply_timing_flag(score, wait_matches)
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
            ft.Text("🪐 AUTO ASTRO (D1/D9) — calculates the current-sky Vedic chart + Panchanga and runs your custom Rules against it, right here.", size=11, color=C["black_txt"]),
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
        fld_portfolio_entry = ft.Switch(label="📌 Mark as My Portfolio (ON)", value=False, active_color=C["green"])
        entry_status = ft.Text("", size=15, color=C["green"], weight="bold")
        akshara_preview = ft.Container(content=ft.Text("", size=14, color=C["dark_txt"]), bgcolor=C["res_bg"], padding=10, border_radius=6, visible=False)

        def load_edit(sym):
            row = db_get(sym)
            if row:
                fld_sym.value, fld_eng.value, fld_hindi.value, fld_ldate.value, fld_series.value = row[0], row[1], row[2], row[3], row[6] if len(row)>6 else "EQ"
                fld_portfolio_entry.value = bool(row[7]) if len(row) > 7 else False
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
            if ok:
                set_portfolio(sym, fld_portfolio_entry.value)  # keep the Entry form's Portfolio switch in sync with the same DB the Stocks list uses
            entry_status.value, entry_status.color = (f"Saved! {sym} Akshara={val}", C["green"]) if ok else (f"Failed: {val}", C["red"])
            if ok: fld_sym.disabled = False
            page.update()

        entry_screen = ft.Column(visible=False, controls=[
            make_header("✏️ MANAGE STOCK ENTRY"), ft.Divider(height=4, color=C["divider"]),
            fld_sym, fld_eng, ft.ElevatedButton("🌐 AUTO TRANSLITERATE HINDI", bgcolor=C["accent"], color="#FFFFFF", on_click=do_transliterate),
            fld_hindi, ft.ElevatedButton("👁️ PREVIEW SOUND WEIGHTS", bgcolor=C["secondary"], color="#FFFFFF", on_click=lambda e: (asum:=calc(fld_hindi.value.strip())) and setattr(akshara_preview.content,'value',f"Akshara: {asum[0]}\n{asum[1]}") or setattr(akshara_preview,'visible',True) or page.update()),
            akshara_preview, fld_ldate, fld_series,
            ft.Container(height=4),
            fld_portfolio_entry,
            ft.Text("This is the SAME Portfolio flag shown as a switch next to each stock on the Stocks tab — setting it here keeps both in sync.", size=10, color=C["hint_txt"]),
            entry_status,
            ft.Row([
                ft.ElevatedButton("💾 SAVE NEW", bgcolor=C["green"], color="#FFFFFF", on_click=do_save),
                ft.ElevatedButton("🔄 UPDATE", bgcolor=C["primary"], color="#FFFFFF", on_click=do_save),
                ft.ElevatedButton("❌ DELETE", bgcolor=C["red"], color="#FFFFFF", on_click=lambda e: db_delete(fld_sym.value.strip().upper()) and setattr(entry_status,'value',"Deleted!") or page.update()),
                ft.ElevatedButton("🧹 CLEAR", bgcolor=C["hint_txt"], color="#FFFFFF", on_click=lambda e: (setattr(fld_sym,'value',""), setattr(fld_sym,'disabled',False), setattr(fld_eng,'value',""), setattr(fld_hindi,'value',""), setattr(fld_ldate,'value',""), setattr(fld_portfolio_entry,'value',False), setattr(akshara_preview,'visible',False), page.update())),
            ])
        ])

        # ── SCREEN 4: ASTRO CHART ────────────────────────────────────────────
        fld_date = make_field("Date (DD-MM-YYYY)", value=datetime.now().strftime("%d-%m-%Y"))
        fld_time = make_field("Time (HH:MM)", value=datetime.now().strftime("%H:%M"))
        fld_lat  = make_field("Latitude (Decimal)", value=current_place["latitude"])
        fld_lon  = make_field("Longitude (Decimal)", value=current_place["longitude"])
        fld_gmt  = make_field("GMT Offset (hours)", hint="e.g. 5.5 for IST", value=current_place["gmt_offset"])
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
                gmt_offset = float(fld_gmt.value) if (fld_gmt.value or "").strip() else 5.5
                jd = jd_ut_from_ist(dt.year, dt.month, dt.day, hh, mm, gmt_offset)
                pos, ay = calc_planet_positions(jd, lat, lon)
                
                d1_pos = {p: lon_to_sign_deg(l)[0] for p, l in pos.items()}
                d9_pos = {p: d9_sign(l) for p, l in pos.items()}
                
                lagna_idx = d1_pos["As"]
                lagna_d9  = d9_pos["As"]
                retro_set = get_retrograde_set(jd, lat, lon)
                vargottama_set = {p for p in d1_pos if p != "As" and d1_pos.get(p) == d9_pos.get(p)}

                astro_chart_container.controls.clear()
                
                astro_chart_container.controls.append(ft.Text(
                    f"📍 Lat {lat:g}, Lon {lon:g}, GMT+{gmt_offset:g}   " +
                    "✨ SIDEREAL AYANAMSA (LAHIRI): " + str(round(ay, 4)) + "°" +
                    ("   ⟲ Retrograde: " + ", ".join(sorted(retro_set)) if retro_set else "") +
                    ("   ★ Vargottama: " + ", ".join(sorted(vargottama_set)) if vargottama_set else ""),
                    size=13, color=C["primary"], weight="bold"))
                astro_chart_container.controls.append(build_dual_diamond_chart_with_bars(d1_pos, lagna_idx, d9_pos, lagna_d9, retro=retro_set, vargottama=vargottama_set))

                # ── PANCHANGA FOR THIS DATE/TIME ──
                tithi_name, tithi_num, paksha, yoga_name, karana_name, panch_notes = compute_panchanga(pos["Su"], pos["Mo"])
                astro_chart_container.controls.append(ft.Container(height=6))
                astro_chart_container.controls.append(make_header("🗓️ PANCHANGA (Tithi · Yoga · Karana)", bgcolor="#4E342E"))
                astro_chart_container.controls.append(ft.Text(
                    f"Tithi  : {tithi_name}  ({paksha}, #{tithi_num})\n"
                    f"Yoga   : {yoga_name}\n"
                    f"Karana : {karana_name}",
                    size=13, color=C["black_txt"], weight="bold", selectable=True
                ))
                if panch_notes:
                    astro_chart_container.controls.append(ft.Text("\n".join(panch_notes), size=11, color=C["orange"], weight="bold"))
                else:
                    astro_chart_container.controls.append(ft.Text("✅ No classical Panchanga caution flags for this moment.", size=11, color=C["green"], weight="bold"))

                astro_chart_container.controls.append(ft.Container(height=8))
                astro_chart_container.controls.append(ft.ElevatedButton("✖  CLOSE CHARTS", bgcolor=C["red"], color="#FFFFFF", height=46, style=ft.ButtonStyle(text_style=ft.TextStyle(size=14, weight="bold")), on_click=do_astro_close))
                
                set_status("Charts Calculated Successfully!", C["green"])
            except Exception as ex:
                set_status(f"Error: {str(ex)}", C["red"])
            page.update()

        def do_use_saved_place(e):
            fld_lat.value = current_place["latitude"]
            fld_lon.value = current_place["longitude"]
            fld_gmt.value = current_place["gmt_offset"]
            page.update()

        astro_screen = ft.Column(visible=False, controls=[
            make_header("🕉️ VEDIC KUNDALI ENGINES"), ft.Divider(height=4, color=C["divider"]),
            ft.Row([fld_date, fld_time]), ft.Row([fld_lat, fld_lon, fld_gmt]),
            ft.TextButton("📍 Use My Saved Place Settings", style=ft.ButtonStyle(color=C["accent"]), on_click=do_use_saved_place),
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

        db_place_summary_text = ft.Text(f"📍 Current astro Place: {current_place['place_name']} ({current_place['latitude']}, {current_place['longitude']}, GMT+{current_place['gmt_offset']})", size=12, color=C["black_txt"])
        db_screen = ft.Column(visible=False, controls=[
            make_header("⚙️ DATABASE AND ENGINE SETUP"), ft.Divider(height=4, color=C["divider"]),
            ft.ElevatedButton("⚡ BUILD AUTOMATED DATABASE", bgcolor=C["orange"], color="#FFFFFF", height=54, on_click=lambda e: threading.Thread(target=build_db_thread, daemon=True).start()),
            prg_bar, prg_txt,
            ft.Divider(height=10, color=C["divider"]),
            db_place_summary_text,
            ft.ElevatedButton("📍 PLACE SETTINGS (City / Lat / Lon / GMT)", bgcolor="#455A64", color="#FFFFFF", height=48, on_click=lambda e: show_screen("place")),
        ])

        # ── SCREEN: PLACE SETTINGS ────────────────────────────────────────────
        # The reference location + GMT offset used by every automatic astro
        # calculation in the app (Oracle's CALCULATE ASTRO, the Stocks tab's Live
        # Timing Signal, and as the default prefill on the Kundali Engines page).
        # Was previously hardcoded to Mumbai (19.076, 72.877) / IST (GMT+5.5) —
        # now saved to the same SQLite database as everything else, so it persists
        # across app restarts and can be changed to any city.
        fld_place_name = make_field("City / Place Name", value=current_place["place_name"])
        fld_place_lat  = make_field("Latitude (Decimal)", hint="e.g. 19.076 for Mumbai", value=current_place["latitude"])
        fld_place_lon  = make_field("Longitude (Decimal)", hint="e.g. 72.877 for Mumbai", value=current_place["longitude"])
        fld_place_gmt  = make_field("GMT Offset (hours)", hint="e.g. 5.5 for India (IST)", value=current_place["gmt_offset"])
        place_status = ft.Text("", size=14, color=C["green"], weight="bold")

        def do_save_place(e):
            try:
                name = fld_place_name.value.strip() or "Custom Location"
                lat  = float(fld_place_lat.value)
                lon  = float(fld_place_lon.value)
                gmt  = float(fld_place_gmt.value)
                if not (-90 <= lat <= 90):
                    raise ValueError("Latitude must be between -90 and 90")
                if not (-180 <= lon <= 180):
                    raise ValueError("Longitude must be between -180 and 180")
                if not (-12 <= gmt <= 14):
                    raise ValueError("GMT offset must be between -12 and +14")
                save_place_settings(name, lat, lon, gmt)
                current_place.update({"place_name": name, "latitude": str(lat), "longitude": str(lon), "gmt_offset": str(gmt)})
                # Keep the Kundali Engines page's fields and the Data-tab summary in sync with the new saved default
                fld_lat.value, fld_lon.value, fld_gmt.value = str(lat), str(lon), str(gmt)
                db_place_summary_text.value = f"📍 Current astro Place: {name} ({lat:g}, {lon:g}, GMT+{gmt:g})"
                place_status.value = f"✅ Saved! {name} ({lat:g}, {lon:g}, GMT+{gmt:g}) is now used for all astro calculations."
                place_status.color = C["green"]
                set_status(f"Place Settings saved: {name}", C["green"])
            except Exception as ex:
                place_status.value = f"⚠️ {str(ex)}"
                place_status.color = C["red"]
            page.update()

        def do_reset_place(e):
            fld_place_name.value = PLACE_DEFAULTS["place_name"]
            fld_place_lat.value  = PLACE_DEFAULTS["latitude"]
            fld_place_lon.value  = PLACE_DEFAULTS["longitude"]
            fld_place_gmt.value  = PLACE_DEFAULTS["gmt_offset"]
            place_status.value = "Reset to default (Mumbai / IST) — tap SAVE to apply."
            place_status.color = C["accent"]
            page.update()

        place_screen = ft.Column(visible=False, controls=[
            make_header("📍 PLACE SETTINGS"), ft.Divider(height=4, color=C["divider"]),
            ft.Text("This location and GMT offset is used for every automatic astro calculation — Oracle's CALCULATE ASTRO, the Stocks tab's Live Timing Signal, and as the starting default on the Kundali Engines page (which you can still override per-calculation there).", size=12, color=C["black_txt"]),
            ft.Container(height=6),
            fld_place_name, fld_place_lat, fld_place_lon, fld_place_gmt,
            ft.Text("Default when never changed: Mumbai — Latitude 19.076, Longitude 72.877, GMT+5.5 (IST).", size=11, color=C["hint_txt"]),
            place_status,
            ft.Row([
                ft.ElevatedButton("💾 SAVE PLACE", bgcolor=C["green"], color="#FFFFFF", height=48, on_click=do_save_place),
                ft.ElevatedButton("↺ RESET TO MUMBAI", bgcolor=C["hint_txt"], color="#FFFFFF", height=48, on_click=do_reset_place),
            ], spacing=10),
        ])

        # ── SCREEN 6: CUSTOM D1/D9 RULES — FULL-POWER GRID ──────────────────
        # Every rule is one card with labeled dropdowns/fields for every condition
        # the old 10 named rule-types could express. There is no rule-type name to
        # pick: every field you actually set (i.e. not left at its default of
        # Any/No/blank) must ALL be true at once for the rule to fire — leave a
        # field at its default to skip that check entirely. This one AND-of-set-
        # fields engine reproduces every old rule type as a special case (fill in
        # just the one or two fields it needed) and also allows new combinations
        # none of the old named types could (e.g. Vargottama AND a specific D1
        # house together). See the HELP page for the full field-by-field mapping
        # and worked examples.
        rules_grid_col = ft.Column(spacing=10)

        def _house_disp(v):
            return "Any" if v is None else str(v)

        def _rashi_disp(v):
            return "Any" if v is None else RASHI_LIST[v - 1]

        def _yn(v):
            return "Yes" if v else "No"

        def _yna(v):
            return v if v in ("Yes", "No") else "Any"

        def _planet_or_any_disp(v):
            return v if v else "Any"

        # Maximum-contrast field styling: pure white field, pure black bold text,
        # white border — a crisp "cutout" against the dark blue row/section
        # background. The options list also gets its own explicit black/bold
        # Text content — the popup list items otherwise fall back to Flet's
        # default dim/gray menu-item styling regardless of the field's own colors.
        def make_grid_opt(o):
            return ft.dropdown.Option(key=o, content=ft.Text(o, color="#000000", weight="bold", size=13))

        def make_grid_dd(label, value, options, width):
            return ft.Dropdown(
                label=label, label_style=ft.TextStyle(size=11, color="#000000", weight="bold"),
                value=value, options=[make_grid_opt(o) for o in options], width=width, dense=True,
                color="#000000", bgcolor="#FFFFFF",
                border_color="#FFFFFF", focused_border_color=C["orange"], border_width=2
            )

        def make_grid_tf(label, value, hint, width):
            return ft.TextField(
                label=label, label_style=ft.TextStyle(size=11, color="#000000", weight="bold"),
                hint_text=hint, hint_style=ft.TextStyle(size=11, color="#616161"),
                value=value, width=width, dense=True,
                text_style=ft.TextStyle(size=14, color="#000000", weight="bold"),
                border_color="#FFFFFF", focused_border_color=C["orange"], border_width=2,
                bgcolor="#FFFFFF", cursor_color="#000000"
            )

        def refresh_rules_grid():
            rules_grid_col.controls.clear()
            for row in simple_rule_list():
                rules_grid_col.controls.append(build_rule_card(row))
            rules_grid_col.controls.append(build_rule_card(None))  # blank "Add New Rule" card, always last
            page.update()

        ASPECT_PLANET_CHOICES = PLANET_OPTIONS[1:]     # Su,Mo,Ma,Me,Ju,Ve,Sa,Ra,Ke (skip ANY)
        RULE_HOUSE_CHOICES = list(range(1, 13))
        ACTION_RADIO_CHOICES = [("BUY", "\U0001F7E2 BUY"), ("SELL", "\U0001F534 SELL"),
                                 ("NEUTRAL", "\u26AA Alert Only"), ("WAIT", "\U0001F7E1 WAIT (avoid trading)")]

        def describe_rule_english(planet, d1h, d1r, d1l, d9h, d9r, d9_aspect, varg, same, comp_pl, comp_h,
                                   retro, wt, action, ssc, ssh, s_empty, stc, stl, sasp, saspp, saspm):
            parts = []
            if ssh:
                chart_bit = f"{ssc or 'D9'} house {ssh}'s rashi"
                if stl:
                    chart_bit += f" is in {stc or 'D1'} house(s) {stl}"
                if s_empty and s_empty != "Any":
                    chart_bit += f", and {ssc or 'D9'} house {ssh} is {s_empty.upper()}"
                if saspp and saspm and saspm != "Any":
                    verb = {"None Aspect": "NOT aspected by", "At Least One": "aspected by at least one of",
                            "All Aspect": "aspected by ALL of"}.get(saspm, "related to")
                    chart_bit += f", and {ssc or 'D9'} house {ssh} is {verb} {saspp}"
                elif sasp and sasp != "Any":
                    chart_bit += f", and {ssc or 'D9'} house {ssh} is {'aspected' if sasp == 'Yes' else 'NOT aspected'} by any planet"
                parts.append(chart_bit)
            pl_bits = []
            if planet and planet != "ANY":
                pl_bits.append(planet)
            if d1h: pl_bits.append(f"in D1 house {d1h}")
            if d1r: pl_bits.append(f"in D1 rashi {RASHI_LIST[d1r - 1]}")
            if d1l: pl_bits.append(f"in D1 house(s) {d1l}")
            if d9h and d9_aspect: pl_bits.append(f"aspecting D9 house {d9h}")
            elif d9h: pl_bits.append(f"in D9 house {d9h}")
            if d9r: pl_bits.append(f"in D9 rashi {RASHI_LIST[d9r - 1]}")
            if varg: pl_bits.append("Vargottama")
            if same: pl_bits.append("D1 house = D9 house")
            if comp_pl: pl_bits.append(f"with {comp_pl} also in D9 house {comp_h or 'Any'}")
            if retro: pl_bits.append("retrograde")
            if pl_bits:
                parts.append(" ".join(pl_bits))
            if not parts:
                return "No conditions set yet \u2014 this rule won't do anything until you set at least one field below."
            return "IF " + "  AND  ".join(parts) + f"  \u2192  {dict(ACTION_RADIO_CHOICES).get(action, action)}  (weight {wt:g})"

        def build_rule_card(row):
            is_new = row is None
            if is_new:
                (rid, planet, d1_house, d1_rashi, d1_list, d9_house, d9_rashi,
                 d9_aspect, vargottama, same_house, comp_planet, comp_d9_house,
                 retro_only, weight, action, struct_src_chart, struct_src_house,
                 struct_tgt_chart, struct_tgt_list, struct_aspect,
                 struct_aspect_planets, struct_aspect_mode, rule_name, struct_src_empty) = (
                    None, "ANY", None, None, None, None, None, False, False, False, None, None,
                    False, 1.0, "BUY", "D9", None, "D1", None, None, None, None, "", None)
            else:
                (rid, planet, d1_house, d1_rashi, d1_list, d9_house, d9_rashi,
                 d9_aspect, vargottama, same_house, comp_planet, comp_d9_house,
                 retro_only, weight, action, struct_src_chart, struct_src_house,
                 struct_tgt_chart, struct_tgt_list, struct_aspect,
                 struct_aspect_planets, struct_aspect_mode, rule_name, struct_src_empty) = row

            fld_name = ft.TextField(
                label="Rule Name / Description (optional)", value=(rule_name or ""),
                label_style=ft.TextStyle(size=11, color="#000000", weight="bold"),
                hint_text="e.g. D9-2 unaspected by Su/Ma/Sa -> Buy",
                hint_style=ft.TextStyle(size=11, color="#616161"),
                text_style=ft.TextStyle(size=13, color="#000000", weight="bold"),
                bgcolor="#FFFFFF", border_color="#FFFFFF", focused_border_color=C["orange"],
                border_width=2, dense=True
            )

            rg_action = ft.RadioGroup(value=(action or "BUY"), content=ft.Row(
                [ft.Radio(value=v, label=lbl) for v, lbl in ACTION_RADIO_CHOICES], wrap=True, spacing=10))

            dd_ssc = make_grid_dd("Chart", (struct_src_chart or "D9"), CHART_OPTIONS, 90)
            dd_ssh = make_grid_dd("House", _house_disp(struct_src_house), HOUSE_OPTIONS, 95)
            rg_empty = ft.RadioGroup(value=(struct_src_empty or "Any"), content=ft.Row([
                ft.Radio(value="Any", label="Any"),
                ft.Radio(value="Empty", label="Empty (no planets)"),
                ft.Radio(value="Occupied", label="Occupied (has a planet)"),
            ], wrap=True, spacing=10))

            dd_stc = make_grid_dd("Target Chart", (struct_tgt_chart or "D1"), CHART_OPTIONS, 110)
            checked_houses = set()
            if struct_tgt_list:
                try:
                    checked_houses = {int(x.strip()) for x in struct_tgt_list.split(",") if x.strip()}
                except ValueError:
                    checked_houses = set()
            house_checks = {h: ft.Checkbox(label=str(h), value=(h in checked_houses)) for h in RULE_HOUSE_CHOICES}
            dd_sasp = make_grid_dd("Aspected by ANY Planet?", _yna(struct_aspect), YES_NO_ANY_OPTIONS, 190)

            checked_planets = set()
            if struct_aspect_planets:
                checked_planets = {x.strip() for x in struct_aspect_planets.split(",") if x.strip()}
            planet_checks = {p: ft.Checkbox(label=p, value=(p in checked_planets)) for p in ASPECT_PLANET_CHOICES}
            dd_saspm = make_grid_dd("Aspect Mode", (struct_aspect_mode or "Any"), ASPECT_MODE_OPTIONS, 170)

            dd_planet  = make_grid_dd("Planet", planet or "ANY", PLANET_OPTIONS, 90)
            dd_d1h     = make_grid_dd("D1 House", _house_disp(d1_house), HOUSE_OPTIONS, 95)
            dd_d1r     = make_grid_dd("D1 Rashi", _rashi_disp(d1_rashi), RASHI_OPTIONS, 130)
            fld_d1l    = make_grid_tf("D1 House List", (d1_list or ""), "e.g. 4,5,9,10,11", 150)
            dd_d9h     = make_grid_dd("D9 House", _house_disp(d9_house), HOUSE_OPTIONS, 95)
            dd_d9r     = make_grid_dd("D9 Rashi", _rashi_disp(d9_rashi), RASHI_OPTIONS, 130)
            dd_aspect  = make_grid_dd("D9 House=Aspected?", _yn(d9_aspect), YES_NO_OPTIONS, 150)
            dd_varg    = make_grid_dd("Vargottama?", _yn(vargottama), YES_NO_OPTIONS, 110)
            dd_same    = make_grid_dd("D1=D9 House?", _yn(same_house), YES_NO_OPTIONS, 120)
            dd_comp_pl = make_grid_dd("Companion Planet", _planet_or_any_disp(comp_planet), PLANET_ONLY_OPTIONS, 140)
            dd_comp_h  = make_grid_dd("Companion D9 House", _house_disp(comp_d9_house), HOUSE_OPTIONS, 150)
            dd_retro   = make_grid_dd("Retro Only?", _yn(retro_only), YES_NO_OPTIONS, 110)
            fld_wt     = make_grid_tf("Weight", (f"{weight:g}" if weight is not None else "1"), "", 80)

            advanced_visible = {"open": False}
            advanced_body = ft.Container(
                content=ft.Row([dd_planet, dd_d1h, dd_d1r, fld_d1l, dd_d9h, dd_d9r, dd_aspect,
                                 dd_varg, dd_same, dd_comp_pl, dd_comp_h, dd_retro, fld_wt],
                                spacing=6, wrap=True),
                bgcolor="#FFFFFF", border_radius=6, padding=8, visible=False
            )
            advanced_toggle_btn = ft.TextButton("\U0001F527 ADVANCED: Planet-Specific Conditions (optional) \u25BC", style=ft.ButtonStyle(color="#FFEB3B"))

            def do_toggle_advanced(e):
                advanced_visible["open"] = not advanced_visible["open"]
                advanced_body.visible = advanced_visible["open"]
                advanced_toggle_btn.text = ("\U0001F527 ADVANCED: Planet-Specific Conditions (optional) " +
                                             ("\u25B2" if advanced_visible["open"] else "\u25BC"))
                page.update()
            advanced_toggle_btn.on_click = do_toggle_advanced

            preview_text = ft.Text("", size=12, color="#FFEB3B", weight="bold", italic=True)
            status_text = ft.Text("", size=12, color="#FFEB3B", weight="bold")
            test_result_text = ft.Text("", size=12, color="#FFFFFF", weight="bold")

            def gather_values():
                d1h = None if dd_d1h.value == "Any" else int(dd_d1h.value)
                d1r = None if dd_d1r.value == "Any" else RASHI_LIST.index(dd_d1r.value) + 1
                d1l = (fld_d1l.value or "").strip() or None
                if d1l:
                    [int(x.strip()) for x in d1l.split(",") if x.strip()]
                d9h = None if dd_d9h.value == "Any" else int(dd_d9h.value)
                d9r = None if dd_d9r.value == "Any" else RASHI_LIST.index(dd_d9r.value) + 1
                comp_pl = None if dd_comp_pl.value == "Any" else dd_comp_pl.value
                comp_h  = None if dd_comp_h.value == "Any" else int(dd_comp_h.value)
                wt = float(fld_wt.value) if (fld_wt.value or "").strip() else 1.0
                ssh = None if dd_ssh.value == "Any" else int(dd_ssh.value)
                stl_houses = sorted(h for h, cb in house_checks.items() if cb.value)
                stl = ",".join(str(h) for h in stl_houses) or None
                sasp = None if dd_sasp.value == "Any" else dd_sasp.value
                saspp_list = [p for p, cb in planet_checks.items() if cb.value]
                saspp = ",".join(saspp_list) or None
                saspm = None if dd_saspm.value == "Any" else dd_saspm.value
                s_empty = None if rg_empty.value == "Any" else rg_empty.value
                return dict(planet=dd_planet.value, d1h=d1h, d1r=d1r, d1l=d1l, d9h=d9h, d9r=d9r,
                            d9_aspect=(dd_aspect.value == "Yes"), varg=(dd_varg.value == "Yes"),
                            same=(dd_same.value == "Yes"), comp_pl=comp_pl, comp_h=comp_h,
                            retro=(dd_retro.value == "Yes"), wt=wt, action=rg_action.value,
                            ssc=dd_ssc.value, ssh=ssh, s_empty=s_empty, stc=dd_stc.value, stl=stl,
                            sasp=sasp, saspp=saspp, saspm=saspm, rule_name=(fld_name.value or "").strip() or None)

            def update_preview(e=None):
                v = gather_values()
                preview_text.value = "\U0001F4DD " + describe_rule_english(
                    v["planet"], v["d1h"], v["d1r"], v["d1l"], v["d9h"], v["d9r"], v["d9_aspect"],
                    v["varg"], v["same"], v["comp_pl"], v["comp_h"], v["retro"], v["wt"], v["action"],
                    v["ssc"], v["ssh"], v["s_empty"], v["stc"], v["stl"], v["sasp"], v["saspp"], v["saspm"])
                page.update()

            def do_save(e):
                try:
                    v = gather_values()
                    if is_new:
                        simple_rule_add(v["planet"], v["d1h"], v["d1r"], v["d1l"], v["d9h"], v["d9r"],
                                         v["d9_aspect"], v["varg"], v["same"], v["comp_pl"], v["comp_h"],
                                         v["retro"], v["wt"], v["action"], v["ssc"], v["ssh"], v["stc"],
                                         v["stl"], v["sasp"], v["saspp"], v["saspm"], v["rule_name"], v["s_empty"])
                        set_status("Rule added.", C["green"])
                    else:
                        simple_rule_update(rid, v["planet"], v["d1h"], v["d1r"], v["d1l"], v["d9h"], v["d9r"],
                                            v["d9_aspect"], v["varg"], v["same"], v["comp_pl"], v["comp_h"],
                                            v["retro"], v["wt"], v["action"], v["ssc"], v["ssh"], v["stc"],
                                            v["stl"], v["sasp"], v["saspp"], v["saspm"], v["rule_name"], v["s_empty"])
                        set_status("Rule updated.", C["green"])
                    refresh_rules_grid()
                except Exception as ex:
                    status_text.value = f"\u26A0\uFE0F {str(ex)}"
                    status_text.color = "#FFEB3B"
                    page.update()

            def do_delete(e):
                simple_rule_delete(rid)
                set_status("Rule deleted.", C["orange"])
                refresh_rules_grid()

            def do_test(e):
                if last_chart_state["d1_pos"] is None:
                    test_result_text.value = "\u26A0\uFE0F No chart calculated yet \u2014 run CALCULATE ASTRO (Oracle page) or open Stocks first, then come back and tap TEST again."
                    test_result_text.color = "#FFEB3B"
                    page.update()
                    return
                v = gather_values()
                houses_d1 = {p: get_house_num(s, last_chart_state["lagna_d1"]) for p, s in last_chart_state["d1_pos"].items() if p != "As"}
                houses_d9 = {p: get_house_num(s, last_chart_state["lagna_d9"]) for p, s in last_chart_state["d9_pos"].items() if p != "As"}
                reasons = []
                ok = True
                if v["ssh"] is not None:
                    src_lagna = last_chart_state["lagna_d9"] if v["ssc"] == "D9" else last_chart_state["lagna_d1"]
                    src_rashi = rashi_of_house(v["ssh"], src_lagna)
                    if v["stl"]:
                        tgt_lagna = last_chart_state["lagna_d9"] if v["stc"] == "D9" else last_chart_state["lagna_d1"]
                        tgt_houses = [int(x) for x in v["stl"].split(",") if x.strip()]
                        tgt_rashis = {rashi_of_house(h, tgt_lagna) for h in tgt_houses}
                        passed = src_rashi in tgt_rashis
                        ok = ok and passed
                        reasons.append(f"{'\u2705' if passed else '\u274C'} Rashi-in-house: {v['ssc']} house {v['ssh']} rashi {'is' if passed else 'is NOT'} in {v['stc']} house(s) {v['stl']}")
                    if v["s_empty"]:
                        src_houses_map = houses_d9 if v["ssc"] == "D9" else houses_d1
                        occupied = any(h == v["ssh"] for h in src_houses_map.values())
                        want_occupied = (v["s_empty"] == "Occupied")
                        passed = (occupied == want_occupied)
                        ok = ok and passed
                        reasons.append(f"{'\u2705' if passed else '\u274C'} Occupancy: {v['ssc']} house {v['ssh']} is {'occupied' if occupied else 'empty'} right now (rule wants {v['s_empty']})")
                    if v["saspp"] and v["saspm"]:
                        src_houses_map = houses_d9 if v["ssc"] == "D9" else houses_d1
                        named = [x.strip() for x in v["saspp"].split(",") if x.strip()]
                        aspecting = [p for p in named if p in src_houses_map and v["ssh"] in planet_aspect_houses(p, src_houses_map[p])]
                        if v["saspm"] == "None Aspect":
                            passed = len(aspecting) == 0
                        elif v["saspm"] == "At Least One":
                            passed = len(aspecting) >= 1
                        elif v["saspm"] == "All Aspect":
                            passed = set(aspecting) == set(named) and len(named) > 0
                        else:
                            passed = True
                        ok = ok and passed
                        reasons.append(f"{'\u2705' if passed else '\u274C'} Aspect check ({v['saspm']} of {v['saspp']}): aspecting right now = {', '.join(aspecting) or 'none'}")
                if not reasons:
                    reasons.append("No Chart & House / Rashi Location / Aspect condition is set to test \u2014 TEST currently only checks those sections, not the Advanced planet-specific fields.")
                test_result_text.value = (f"TEST vs {last_chart_state['label']}:\n" + "\n".join(reasons) +
                                           f"\n\nOVERALL: {'\u2705 PASSES right now' if ok else '\u274C DOES NOT PASS right now'}")
                test_result_text.color = "#69F0AE" if ok else "#FFEB3B"
                page.update()

            watched_ctrls = [fld_name, dd_ssc, dd_ssh, dd_stc, dd_sasp, dd_saspm,
                              dd_planet, dd_d1h, dd_d1r, fld_d1l, dd_d9h, dd_d9r, dd_aspect, dd_varg,
                              dd_same, dd_comp_pl, dd_comp_h, dd_retro, fld_wt]
            for ctrl in watched_ctrls:
                if hasattr(ctrl, "on_change"):
                    ctrl.on_change = update_preview
                if isinstance(ctrl, ft.TextField):
                    ctrl.on_submit = update_preview
                    ctrl.on_blur = update_preview
            rg_action.on_change = update_preview
            rg_empty.on_change = update_preview
            for cb in list(house_checks.values()) + list(planet_checks.values()):
                cb.on_change = update_preview

            house_grid = ft.Container(
                content=ft.Row([house_checks[h] for h in RULE_HOUSE_CHOICES], wrap=True, spacing=2),
                bgcolor="#FFFFFF", border_radius=6, padding=6
            )
            planet_grid = ft.Container(
                content=ft.Row([planet_checks[p] for p in ASPECT_PLANET_CHOICES], wrap=True, spacing=2),
                bgcolor="#FFFFFF", border_radius=6, padding=6
            )
            action_box = ft.Container(content=rg_action, bgcolor="#FFFFFF", border_radius=6, padding=8)
            empty_box  = ft.Container(content=rg_empty, bgcolor="#FFFFFF", border_radius=6, padding=8)

            header_row_ctrls = [ft.Text((f"Rule #{rid}" if not is_new else "\u2795 NEW RULE"), size=14, weight="bold", color="#FFFFFF")]
            if not is_new:
                header_row_ctrls.append(ft.IconButton(icon=ft.Icons.DELETE, icon_color="#FFFFFF", on_click=do_delete))

            update_preview()

            return ft.Container(
                content=ft.Column([
                    ft.Row(header_row_ctrls, alignment="spaceBetween"),
                    fld_name,
                    ft.Text("ACTION", size=11, color="#FFEB3B", weight="bold"),
                    action_box,
                    ft.Divider(height=6, color="#FFFFFF"),
                    ft.Text("PRIMARY CHART & HOUSE", size=11, color="#FFEB3B", weight="bold"),
                    ft.Row([dd_ssc, dd_ssh], spacing=8, wrap=True),
                    ft.Text("Occupancy \u2014 does this house have a planet sitting in it?", size=11, color="#FFFFFF"),
                    empty_box,
                    ft.Divider(height=6, color="#FFFFFF"),
                    ft.Text("RASHI LOCATION CHECK \u2014 does this house's sign also sit in one of these Target Chart houses?", size=11, color="#FFEB3B", weight="bold"),
                    ft.Row([dd_stc, dd_sasp], spacing=8, wrap=True),
                    house_grid,
                    ft.Divider(height=6, color="#FFFFFF"),
                    ft.Text("ASPECT RESTRICTION \u2014 is this house aspected by these named planets?", size=11, color="#FFEB3B", weight="bold"),
                    planet_grid,
                    dd_saspm,
                    ft.Divider(height=6, color="#FFFFFF"),
                    advanced_toggle_btn,
                    advanced_body,
                    ft.Divider(height=6, color="#FFFFFF"),
                    preview_text,
                    ft.Row([
                        ft.ElevatedButton(("\U0001F4BE SAVE RULE" if is_new else "\U0001F4BE UPDATE"), bgcolor=C["green"], color="#FFFFFF", on_click=do_save),
                        ft.ElevatedButton("\U0001F9EA TEST vs Last Chart", bgcolor=C["accent"], color="#FFFFFF", on_click=do_test),
                    ], spacing=8, wrap=True),
                    status_text,
                    test_result_text,
                ], spacing=6),
                bgcolor=C["primary"], border_radius=10, padding=12,
                border=ft.border.all(2, "#FFEB3B") if is_new else None
            )

        # ── EXPORT / IMPORT (copy-paste JSON) ───────────────────────────────
        export_output = ft.Text("", size=10, color=C["black_txt"], selectable=True, font_family="monospace", visible=False)
        import_input   = ft.TextField(label="Paste Rules JSON here", multiline=True, min_lines=4, max_lines=10, value="")

        def do_export_rules(e):
            rows = simple_rule_list()
            data = []
            for (rid, planet, d1h, d1r, d1l, d9h, d9r, asp, varg, same, comp_pl, comp_h, retro, wt, act,
                 ssc, ssh, stc, stl, sasp, saspp, saspm, rname, sempty) in rows:
                data.append({
                    "rule_name": rname, "planet": planet, "d1_house": d1h, "d1_rashi": d1r, "d1_list": d1l,
                    "d9_house": d9h, "d9_rashi": d9r, "d9_aspect": asp, "vargottama": varg,
                    "same_house": same, "companion_planet": comp_pl, "companion_d9_house": comp_h,
                    "retro_only": retro, "weight": wt, "action": act,
                    "struct_src_chart": ssc, "struct_src_house": ssh, "struct_src_empty": sempty,
                    "struct_tgt_chart": stc, "struct_tgt_list": stl, "struct_aspect": sasp,
                    "struct_aspect_planets": saspp, "struct_aspect_mode": saspm
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
                    simple_rule_add(
                        item.get("planet", "ANY"), item.get("d1_house"), item.get("d1_rashi"),
                        item.get("d1_list"), item.get("d9_house"), item.get("d9_rashi"),
                        item.get("d9_aspect", 0), item.get("vargottama", 0), item.get("same_house", 0),
                        item.get("companion_planet"), item.get("companion_d9_house"),
                        item.get("retro_only", 0), float(item.get("weight", 1.0)), item.get("action", "BUY"),
                        item.get("struct_src_chart"), item.get("struct_src_house"),
                        item.get("struct_tgt_chart"), item.get("struct_tgt_list"), item.get("struct_aspect"),
                        item.get("struct_aspect_planets"), item.get("struct_aspect_mode"),
                        item.get("rule_name"), item.get("struct_src_empty")
                    )
                    count += 1
                set_status(f"Imported {count} rules.", C["green"])
                import_input.value = ""
                refresh_rules_grid()
            except Exception as ex:
                set_status(f"Import error: {str(ex)}", C["red"])
                page.update()


        HELP_TEXT = """HOW THE BUY/SELL/NEUTRAL/WAIT SIGNAL WORKS

Every rule — saved or brand new — is ONE FRIENDLY CARD on the Rules page. ANY field you actually set (leave anything else at its default — Any / No / unchecked / blank) must ALL be true at the same time for that rule to fire. Leaving a field at its default just means "don't check this" — it does not mean "must be empty." A blank ➕ NEW RULE card always sits at the bottom of the list, ready to fill in.

THE RULE CARD, TOP TO BOTTOM
• Rule Name / Description — optional label just for you, e.g. "D9-2 unaspected by Su/Ma/Sa → Buy". Purely cosmetic, doesn't affect matching.
• ACTION — a single choice: 🟢 BUY, 🔴 SELL, ⚪ Alert Only (NEUTRAL, logged but doesn't move the score), or 🟡 WAIT (a hard caution flag — see below).
• PRIMARY CHART & HOUSE — Chart (D1/D9) + House (1-12) this rule is about, plus an Occupancy choice: Any (don't check) / Empty (house must have NO planet sitting in it) / Occupied (house must have AT LEAST ONE planet in it).
• RASHI LOCATION CHECK — Target Chart + tick-boxes for which of its houses (1-12) the Primary house's rashi must also fall in, plus "Aspected by ANY Planet?" (Any/Yes/No) for the plain "any planet" version of the aspect check.
• ASPECT RESTRICTION — tick-boxes for named planets (Su, Mo, Ma, Me, Ju, Ve, Sa, Ra, Ke) plus Aspect Mode (None Aspect / At Least One / All Aspect) for the named-planet version of the aspect check.
• 🔧 ADVANCED: Planet-Specific Conditions (tap to expand) — the original planet-level fields: Planet, D1 House, D1 Rashi, D1 House List, D9 House, D9 Rashi, D9 House=Aspected?, Vargottama?, D1=D9 House?, Companion Planet + Companion D9 House, Retro Only?, Weight. Use this whenever the rule is about a SPECIFIC planet rather than the chart's structure alone.
• Live preview (yellow italic text) — a plain-English sentence that updates automatically as you change any field, so you can always see exactly what the rule currently says before saving.
• 🧪 TEST vs Last Chart — checks the Chart & House / Rashi Location / Aspect sections of this rule against whichever chart your app most recently calculated (CALCULATE ASTRO or the Live Timing Signal), and reports PASS/FAIL with the reason for each condition. Run CALCULATE ASTRO at least once first so there's a chart to test against.
• 💾 SAVE RULE / UPDATE — writes the rule to the database and refreshes the list.

FIELD-BY-FIELD MEANING (Advanced / Planet-Specific section)
• Planet — which planet this rule applies to, or ANY for every planet.
• D1 House — planet's house (1-12, counted from Lagna) in the D1 (Rashi) chart.
• D1 Rashi — planet's zodiac sign in D1, regardless of house.
• D1 House List — planet's D1 house must be ONE OF these (comma-separated, e.g. 4,5,9,10,11).
• D9 House — planet's house in the D9 (Navamsha) chart.
• D9 House = Aspected? — if Yes, "D9 House" above means the house being ASPECTED by the planet, not the house it's sitting in.
• D9 Rashi — planet's zodiac sign in D9, regardless of house.
• Vargottama? — Yes means: same rashi in both D1 and D9 (a classical strength placement).
• D1=D9 House? — Yes means: the house number is the same in both charts (any number).
• Companion Planet / Companion D9 House — an extra AND condition: a second planet that must ALSO be sitting in this D9 house for the rule to count.
• Retro Only? — Yes means the rule only fires while the planet is retrograde.
• Weight — how strongly a BUY/SELL match counts toward the score (default 1).
• Action — BUY (+weight to score), SELL (-weight to score), NEUTRAL (logged only), or WAIT (a hard caution flag — see below).

RASHI LOCATION CHECK + ASPECT RESTRICTION — A DIFFERENT KIND OF FIELD (Chart & House / Occupancy / Target Chart + tick-boxes / Aspected by Any Planet? / named-planet tick-boxes + Aspect Mode)
These card sections are NOT about any planet — they're a fact about the chart itself.
• Target House List: "does the rashi sitting in Source Chart's Source House ALSO sit in one of Target Chart's Target House List houses?" Depends only on the Lagna of each chart.
• Aspected by Any Planet?: "is the Source Chart's Source House aspected by AT LEAST ONE planet, whichever it is?" — checked once across every planet in that chart, not tied to a specific one. Leave at Any to skip this check.
• Aspect Planets + Aspect Mode: the NAMED-planet version — put comma-separated planet codes in Aspect Planets (e.g. Ma,Sa for Mars and Saturn) and pick a mode:
   - None Aspect  = the Source House must NOT be aspected by any of the listed planets (none of them may aspect it)
   - At Least One = at least one of the listed planets aspects the Source House
   - All Aspect   = every listed planet aspects the Source House
  Leave Aspect Mode at Any to skip this named-planet check entirely (use plain "Aspected by Any Planet?" instead, or neither).
• If you set ONLY this section (Planet left at ANY, nothing else above set) — the rule fires once for the whole chart, not once per planet.
• If you combine it WITH planet fields above (e.g. Planet=Ju + D1 House=9) — it becomes an extra AND requirement on top of the planet condition.
Example — "D9's house 11 rashi exists in D1's houses 4, 5, 9, 10, or 11": Src Chart=D9, Src House=11, Target Chart=D1, Target House List=4,5,9,10,11.
Example — "D9's house 11 should NOT be aspected by Mars and Saturn": Src Chart=D9, Src House=11, Aspect Planets=Ma,Sa, Aspect Mode=None Aspect.

HOW THE SCORE WORKS
The banner under CALCULATE ASTRO adds up every matching rule: +weight for BUY, -weight for SELL, 0 for NEUTRAL. WAIT is deliberately NOT part of that tally — it's a hard caution flag. If even ONE WAIT rule matches, the banner switches to "WAIT ON THIS STOCK TODAY" regardless of what the BUY/SELL score says.

This is a reference tool based on conventional interpretations, not a validated predictive model — use it as one input, not a standalone signal.

PANCHANGA (Tithi / Yoga / Karana) — shown alongside the D1/D9 chart on both the Stocks page's CALCULATE ASTRO and the Kundali Engines page. This is informational only right now — it is NOT wired into the BUY/SELL/WAIT rule engine, so it never changes the score. Caution notes (Rikta Tithi, inauspicious Yoga, Vishti/Bhadra Karana) are shown as soft flags for your own judgement.

SARVATOBHADRA — TWO DIFFERENT USES OF THE SAME NAME
The word "Sarvatobhadra" appears in this app in two unrelated places — don't confuse them:
1. BANDHA PATTERN (one of six): "सर्वतोभद्र Sarvatobhadra — All-auspicious square, balance in every direction." This is one of the six classical Bandha traversal patterns (Rathabandha, Chakrabandha, Padmabandha, Hamsabandha, Muktavali, Sarvatobhadra) mapped from a stock's Navaank (0-8), shown on the Oracle report as a symbolic overlay alongside the Graha reading. Sarvatobhadra Bandha reads as balanced/range-bound — the app's guidance is to wait for a clear breakout rather than force an entry.
2. SARVATOBHADRA VEDHA CHECK (Muhurta Shastra — Nakshatra Obstruction): a separate check, also shown on the Oracle report (STEP 9), that compares today's Nakshatra against the stock's listing-date birth Nakshatra using the classical Vedha (obstruction) pairing table — e.g. Ashwini↔Jyeshtha, Bharani↔Anuradha, and so on; Dhanishta traditionally has no pair. If today's Nakshatra and the stock's birth Nakshatra are Vedha partners, the report shows "⚠️ VEDHA PRESENT" with a warning to avoid a fresh entry today, plus the sectors affected via each Nakshatra's ruling planet (Graha). If they're clear of each other, it shows "✅ NO VEDHA." A small "Vedha" red tag also appears next to a stock's row in the Stock List when this flag is active. Like Panchanga, this is a soft caution flag — it does NOT change the BUY/SELL/WAIT score, it only tags the day/stock for your own judgement.

RAMAL PRASHNA (16-House Geomancy Chart) — Kundali Engines page, separate from the main D1/D9 rule engine.
Casts a fresh 16-house Ramal chart the moment you open it: 4 random Mother figures (each a 4-bit combination of odd/even marks) → 4 Daughter figures (the Mothers' rows transposed into columns) → 4 Nephew figures (Mothers and Daughters combined pairwise using Ramal parity-addition, where Odd+Odd=Even and Odd+Even=Odd) → a Right Witness and a Left Witness (Nephews combined pairwise the same way) → the Judge, house 15 (the two Witnesses combined) → the Final Outcome/Reconciler, house 16 (Mother 1 combined with the Judge). Each of the 16 four-bit figures ("Shakal") is looked up by name — e.g. Jamat, Tariq, Lahan, Nafki, Kajjul, Uqla, and so on — along with its nature (Mitrik = inward/accumulating, Kharij = outward/depleting, or Nishasht = neutral), ruling element (Agni/Jala/Vayu/Prithvi), and a bullish/bearish bias. The final recommendation looks at the Judge AND the Final Outcome together: both Mitrik → 🟢 high-probability BUY (strong inward alignment); Judge is Kharij → 🔴 avoid buying, favors SELL (outward depletion / possible trap); anything else (mixed) → ⚪ neutral, wait for price-action confirmation. Like Panchanga and the Sarvatobhadra Vedha check, Ramal is a separate informational tool — it is NOT wired into the main BUY/SELL/WAIT rule-engine score.

WORKED EXAMPLES (what to set, leaving everything else at its default)
• Jupiter in D1 house 9 → BUY: Planet=Ju, D1 House=9, Action=BUY
• Saturn in D9 Sagittarius → WAIT: Planet=Sa, D9 Rashi=Sagittarius, Action=WAIT
• Mars vargottama → BUY: Planet=Ma, Vargottama?=Yes, Action=BUY
• D1 house equals D9 house, any planet → NEUTRAL: Planet=ANY, D1=D9 House?=Yes, Action=NEUTRAL
• Any planet aspecting D9 house 11 → BUY: Planet=ANY, D9 House=11, D9 House = Aspected?=Yes, Action=BUY
• A planet's D9 house is 2, AND its D1 house is one of 4,5,9,10,11 → BUY: Planet=ANY (or your choice), D9 House=2, D1 House List=4,5,9,10,11, Action=BUY.
• Same idea, but only when a second planet is also confirming it: add Companion Planet + Companion D9 House.
• Mercury in D1 house 3, only while retrograde → caution: Planet=Me, D1 House=3, Retro Only?=Yes, Action=WAIT
• D9's house 11 rashi carries into D1's kendra/trikona houses, no planet involved → BUY: Src Chart=D9, Src House=11, Target Chart=D1, Target House List=4,5,9,10,11, Action=BUY
• D9 house 11's rashi in D1's houses 4,5,10,11 → SELL: Src Chart=D9, Src House=11, Target Chart=D1, Target House List=4,5,10,11, Action=SELL
• D9 house 2's rashi in D1's houses 4,5,10,11 → BUY: Src Chart=D9, Src House=2, Target Chart=D1, Target House List=4,5,10,11, Action=BUY
• Same two rules, but ALSO require that D9 house 11 (or D9 house 2) is aspected by some planet: add Aspected by Any Planet?=Yes to that rule.
• Saturn in D9 house 7 → avoid trading: Planet=Sa, D9 House=7, Action=WAIT. WAIT is this app's "avoid trading" flag — a single match overrides the BUY/SELL score and shows "WAIT ON THIS STOCK TODAY" regardless of anything else.

USER Q&A
Q: If D9's house no 7 has Saturn we should avoid trade. Can I set this rule in rule list — if yes then say 'yes', else set such rule provision setting in rule.
A: Yes.
Set it exactly like this on a rule card:
• Open 🔧 ADVANCED: Planet-Specific Conditions and set Planet = Sa, D9 House = 7
• Everything else left at Any/No/unchecked
• ACTION = WAIT

Q: If D9's 11th house rashi exists in D1's 4,5,10,11th house rashi, AND D9's 11th house should NOT be aspected by Mars and Saturn — can I set this rule? If yes, say 'yes', else make a provision for it.
A: Yes — the ASPECT RESTRICTION section has named-planet tick-boxes (e.g. tick Ma and Sa) plus an Aspect Mode dropdown (None Aspect / At Least One / All Aspect). Set it exactly like this:
• PRIMARY CHART & HOUSE: Chart=D9, House=11
• RASHI LOCATION CHECK: Target Chart=D1, tick houses 4, 5, 10, 11
• ASPECT RESTRICTION: tick Ma and Sa, Aspect Mode=None Aspect
• ACTION = BUY (or SELL/WAIT, whichever you intend)
Leave 🔧 ADVANCED untouched (Planet stays ANY) — this is a pure chart-structure rule, not tied to one named planet.

Q: (1) If D9's 2nd house rashi exists in D1's house 4, 5, 10, or 11, AND D9's 2nd house is NOT aspected by Sun, Mars, Saturn → BUY signal. (2) If D9's 11th house rashi exists in D1's house 4, 5, 10, or 11, AND D9's 11th house is NOT aspected by Mars and Saturn → SELL signal. Can these be set in the rule list? If yes, say 'yes', else make a provision.

A: Yes — the Aspect Planets field takes ANY comma-separated list of planet codes (not just two), so a 3-planet check like Su,Ma,Sa works exactly the same way as a 2-planet check like Ma,Sa. No new provision was needed; this is the same "Rashi-in-House Match" section used above, just with different Src House / Target House List / Aspect Planets / Action values. Add TWO separate rule rows:

Rule (1) — D9 house 2 → D1 kendra/trikona, unaspected by Sun/Mars/Saturn → BUY:
• PRIMARY CHART & HOUSE: Chart=D9, House=2
• RASHI LOCATION CHECK: Target Chart=D1, tick houses 4, 5, 10, 11
• ASPECT RESTRICTION: tick Su, Ma, Sa, Aspect Mode=None Aspect
• ACTION = BUY
(Leave 🔧 ADVANCED untouched — Planet stays ANY.)

Rule (2) — D9 house 11 → D1 kendra/trikona, unaspected by Mars/Saturn → SELL:
• PRIMARY CHART & HOUSE: Chart=D9, House=11
• RASHI LOCATION CHECK: Target Chart=D1, tick houses 4, 5, 10, 11
• ASPECT RESTRICTION: tick Ma, Sa, Aspect Mode=None Aspect
• ACTION = SELL
(Leave 🔧 ADVANCED untouched — Planet stays ANY.)

Tap any field on an existing rule row to change it — it saves as soon as you leave the field. Tap the trash icon to delete a row."""

        help_screen = ft.Column(visible=False, scroll="auto", controls=[
            make_header("📖 HELP / REFERENCE GUIDE"), ft.Divider(height=4, color=C["divider"]),
            ft.Text(HELP_TEXT, size=12.5, color=C["black_txt"], selectable=True),
            ft.Container(height=10),
            ft.ElevatedButton("⬅  BACK TO RULES", bgcolor=C["primary"], color="#FFFFFF", height=48, on_click=lambda e: show_screen("rules"))
        ])

        rules_screen = ft.Column(visible=False, scroll="auto", controls=[
            make_header("📜 CUSTOM D1 / D9 RULES"), ft.Divider(height=4, color=C["divider"]),
            ft.Text("Every rule — saved or new — is ONE FRIENDLY CARD below: Rule Name, Action, Chart & House (with an Empty/Occupied Occupancy check), Rashi Location houses as tick-boxes, Aspect Restriction planets as tick-boxes, an ADVANCED section for the older planet-specific fields, a live plain-English preview, and a TEST button that checks the rule against the last chart your app calculated. Leave any field at Any/No/unchecked to skip that check. A blank ➕ NEW RULE card is always at the bottom. See HELP for the full field guide and worked examples.", size=12, color=C["black_txt"]),
            ft.ElevatedButton("📖 HELP / REFERENCE GUIDE", bgcolor=C["accent"], color="#FFFFFF", height=44, on_click=lambda e: show_screen("help")),
            ft.Divider(height=6, color=C["divider"]),
            rules_grid_col,
            ft.Divider(height=6, color=C["divider"]),
            ft.Text("EXPORT / IMPORT RULES (copy-paste JSON — e.g. to test on desktop and bring back)", size=12, weight="bold", color=C["black_txt"]),
            ft.ElevatedButton("📤 EXPORT RULES (JSON)", bgcolor=C["accent"], color="#FFFFFF", height=44, on_click=do_export_rules),
            export_output,
            import_input,
            ft.ElevatedButton("📥 IMPORT RULES FROM JSON", bgcolor=C["green"], color="#FFFFFF", height=44, on_click=do_import_rules),
        ])


        # ── NAVIGATION CONTROL ────────────────────────────────────────────────
        all_screens = {"oracle": oracle_screen, "list": list_screen, "entry": entry_screen, "astro": astro_screen, "db": db_screen, "place": place_screen, "rules": rules_screen, "help": help_screen}

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

        refresh_rules_grid()

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
