
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
import platform
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
    'क':11,'ख':12,'ग':13,'घ':14,'ङ':15,'च':16,'छ':17,'ज':18,'झ':19,'ञ':20,
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
    "HINDALCO":"हिंडाल्को","VEDL":"वेदांता",
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
    "UNITECH":"यूनिटेक",
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
    "MEDIA":"मीडिया","HEALTHCARE":"हेल्थकेयर",
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

# ── Offline syllable-aware transliterator ───────────────────────────────────
# Used only when network transliteration (Google Input Tools) is unavailable
# or fails. Unlike PR above (one Devanagari letter per English letter, which
# produces unreadable letter-salad like "RAJESH" -> "रएजइसह"), this groups
# consonant+vowel into proper syllables with matras, e.g. "RAJESH" -> "रजेश".
# It's still a heuristic (English spelling doesn't mark long/short vowels
# reliably, so results won't always match the "textbook" spelling) but it
# stays readable Hindi instead of garbled akshara.
_TL_THREE_C = {'KSH':'क्ष','GYA':'ज्ञ','CHH':'छ'}
# Whole chunks whose pronunciation breaks the normal consonant+vowel rules below
# and are common enough in Indian company names to special-case directly:
# "CH" is usually the "ch" in "chair", but in "TECH" it's a hard "k" sound;
# a leading "U" is usually "oo", but in "UNI-" (university, union, unique...)
# it's really "yoo". Checked longest-first, before the generic digraph rules.
_TL_CHUNKS  = {'TECH':'टेक', 'UNI':'यूनि'}
_TL_TWO_C   = {'SH':'श','CH':'च','TH':'थ','PH':'फ','KH':'ख','GH':'घ','JH':'झ','NG':'ङ'}
_TL_TWO_V   = {'AA':'आ','EE':'ई','II':'ई','OO':'ऊ','UU':'ऊ'}
_TL_ONE_C   = {
    'B':'ब','C':'क','D':'ड','F':'फ','G':'ग','H':'ह','J':'ज','K':'क','L':'ल',
    'M':'म','N':'न','P':'प','Q':'क','R':'र','S':'स','T':'ट','V':'व','W':'व',
    'X':'क्स','Y':'य','Z':'ज़',
}
_TL_ONE_V   = {'A':'अ','E':'ए','I':'इ','O':'ओ','U':'उ'}
_TL_MATRA_SHORT = {'अ':'','इ':'ि','उ':'ु','ए':'े','ओ':'ो'}
_TL_MATRA_LONG  = {'आ':'ा','ई':'ी','ऊ':'ू'}

def _tl_tokenize(cw):
    """Split an uppercase English word into (kind, base_devanagari, is_long) tokens.
    kind 'X' = atomic chunk (from _TL_CHUNKS), inserted as-is, no matra combining."""
    toks, i, n = [], 0, len(cw)
    while i < n:
        c4, c3, c2, c1 = cw[i:i+4], cw[i:i+3], cw[i:i+2], cw[i:i+1]
        if c4 in _TL_CHUNKS:
            toks.append(('X', _TL_CHUNKS[c4], False)); i += 4
        elif c3 in _TL_CHUNKS:
            toks.append(('X', _TL_CHUNKS[c3], False)); i += 3
        elif c3 in _TL_THREE_C:
            toks.append(('C', _TL_THREE_C[c3], False)); i += 3
        elif c2 in _TL_TWO_C:
            toks.append(('C', _TL_TWO_C[c2], False)); i += 2
        elif c2 in _TL_TWO_V:
            toks.append(('V', _TL_TWO_V[c2], True)); i += 2
        elif c1 in _TL_ONE_C:
            toks.append(('C', _TL_ONE_C[c1], False)); i += 1
        elif c1 in _TL_ONE_V:
            toks.append(('V', _TL_ONE_V[c1], False)); i += 1
        else:
            i += 1  # skip digits/punctuation the maps don't cover
    return toks

def offline_translit(cw):
    """Heuristic offline fallback: consonant clusters take a following vowel as
    a matra; a vowel with no preceding consonant (start of word, or after
    another vowel) is written as an independent vowel letter."""
    toks = _tl_tokenize(cw)
    out, i, n = [], 0, len(toks)
    while i < n:
        kind, base, is_long = toks[i]
        if kind == 'X':
            out.append(base)
            i += 1
        elif kind == 'C':
            nxt = toks[i + 1] if i + 1 < n else None
            if nxt and nxt[0] == 'V':
                vbase, vlong = nxt[1], nxt[2]
                matra = (_TL_MATRA_LONG.get(vbase) if vlong else _TL_MATRA_SHORT.get(vbase))
                out.append(base + (matra if matra is not None else ''))
                i += 2
            else:
                out.append(base)
                i += 1
        else:
            out.append(base)
            i += 1
    return "".join(out) or "".join(PR.get(c, "") for c in cw)
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

# Digits inside a stock name (e.g. "360 ONE WAM", "5PAISA CAPITAL", "3M INDIA",
# "20 MICRONS") were previously silently DROPPED by every path below — neither the
# WD dictionary, Google Input Tools, nor the offline engine has any entry for a
# digit character, so they just vanished from the output instead of becoming a
# Hindi word. Spelling each digit out (phonetically, as it's read aloud) closes
# that gap so a result is always produced no matter what the input contains.
DIGIT_WORDS = {'0':'ज़ीरो','1':'वन','2':'टू','3':'थ्री','4':'फोर','5':'फाइव',
               '6':'सिक्स','7':'सेवन','8':'एट','9':'नाइन'}

def _digit_run_to_hindi(run):
    return " ".join(DIGIT_WORDS[d] for d in run if d in DIGIT_WORDS)

def _split_alpha_digit_runs(cw):
    """Split a token into alternating runs of digits and non-digits, in order,
    e.g. '5PAISA' -> [('5', True), ('PAISA', False)]."""
    runs, current, current_is_digit = [], cw[0], cw[0].isdigit()
    for ch in cw[1:]:
        ch_is_digit = ch.isdigit()
        if ch_is_digit == current_is_digit:
            current += ch
        else:
            runs.append((current, current_is_digit))
            current, current_is_digit = ch, ch_is_digit
    runs.append((current, current_is_digit))
    return runs

# A word with NO vowel letters at all (DCW, PVR, MRF, ...) cannot be split into
# real consonant+vowel syllables — the syllable-based offline engine has no
# choice but to glue bare consonants together (each with its silent inherent
# "a"), producing a made-up sound like "डकव" for DCW instead of how the ticker
# is actually said out loud: letter by letter, "D-C-W", the same way people say
# "N-T-P-C" or "P-V-R". Spelling such tokens out by letter name fixes this
# whether or not the network transliteration API is reachable, since Google
# Input Tools has the same fundamental problem with an unpronounceable input.
LETTER_NAMES = {
    'A':'ए','B':'बी','C':'सी','D':'डी','E':'ई','F':'एफ','G':'जी','H':'एच',
    'I':'आई','J':'जे','K':'के','L':'एल','M':'एम','N':'एन','O':'ओ','P':'पी',
    'Q':'क्यू','R':'आर','S':'एस','T':'टी','U':'यू','V':'वी','W':'डब्ल्यू',
    'X':'एक्स','Y':'वाई','Z':'ज़ेड',
}

def _is_unpronounceable_cluster(cw):
    return cw.isalpha() and len(cw) > 1 and not any(v in cw for v in "AEIOU")

def _spell_out_letters(cw):
    return "".join(LETTER_NAMES.get(ch, "") for ch in cw)

def _translit_one_word(cw):
    """CURATED is checked by the caller (get_hindi) for the whole name; this handles
    a single already-alphabetic word: unpronounceable all-consonant clusters (spelled
    letter-by-letter) > known business-term dictionary (WD) > Google Input Tools
    transliteration (sound-based) > offline syllable-aware fallback."""
    if _is_unpronounceable_cluster(cw):
        return _spell_out_letters(cw)
    if cw in WD:
        return WD[cw]
    if REQUESTS_OK:
        try:
            r = requests.get(
                "https://inputtools.google.com/request?text=" + cw + "&ime=transliteration_en_hi&num=1",
                timeout=4).json()
            return r[1][0][1][0] if r[0] == "SUCCESS" else offline_translit(cw)
        except: pass
    return offline_translit(cw)

def get_hindi(sym, eng):
    """Phonetic transliteration (sound-for-sound), NOT semantic translation — this
    matters because Akshara Sum is a phonetic weight system: translating a word's
    MEANING (e.g. "Exports" -> "निर्यात") gives a real Hindi word but the WRONG
    akshara, since it no longer sounds like the English name. Order of preference
    per word: curated whole-name override > known business-term dictionary (WD) >
    Google Input Tools transliteration (sound-based) > crude letter-map fallback.
    Any digits are spelled out phonetically rather than silently dropped, so a
    result is always produced regardless of what the input contains."""
    if sym in CURATED: return CURATED[sym]
    out = []
    for w in eng.upper().split():
        cw = w.strip("&.,()-/")
        if not cw:
            continue
        if any(ch.isdigit() for ch in cw):
            sub_out = []
            for run, is_digit in _split_alpha_digit_runs(cw):
                if is_digit:
                    piece = _digit_run_to_hindi(run)
                elif run:
                    piece = _translit_one_word(run)
                else:
                    piece = ""
                if piece:
                    sub_out.append(piece)
            if sub_out:
                out.append(" ".join(sub_out))
            continue
        out.append(_translit_one_word(cw))
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

SWISSEPH_HOUSE_SYSTEM = 'W'  # 'W' = Whole Sign (Vedic default). Change to 'P' for
                             # Placidus etc. if this app's existing chart rendering
                             # assumes a different house system than Whole Sign.

_SWE_INSTANCE = None
_SWE_LOAD_ERROR = None
_USE_APPROX_EPHEMERIS = False  # True when native libswe.so is unavailable

def _resolve_native_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "native"),
        os.path.join(here, "..", "native"),
        os.path.join(os.getcwd(), "native"),
        os.path.join(os.getenv("FLET_APP_STORAGE_DATA", ".") or ".", "native"),
    ]
    for c in candidates:
        try:
            if c and os.path.isdir(c):
                return os.path.abspath(c)
        except Exception:
            continue
    raise RuntimeError(f"native/ folder not found. Checked: {candidates}")

def _get_swisseph():
    """Lazily load libswe.so. Fail-soft: returns None (does not crash) if missing."""
    global _SWE_INSTANCE, _SWE_LOAD_ERROR
    if _SWE_INSTANCE is not None:
        return _SWE_INSTANCE
    if _SWE_LOAD_ERROR is not None:
        return None
    try:
        native_dir = _resolve_native_dir()
        machine = platform.machine().lower()
        subdir = "arm64-v8a" if ("aarch64" in machine or "arm64" in machine) else "linux-x64"
        so_path = os.path.join(native_dir, subdir, "libswe.so")
        ephe_path = os.path.join(native_dir, "ephe")
        if not os.path.exists(so_path):
            raise RuntimeError(f"libswe.so not found at {so_path}")
        os.environ["SWISSEPH_LIBRARY_PATH"] = so_path
        from swisseph_ffi import SwissEph
        swe = SwissEph()
        swe.swe_set_ephe_path(ephe_path.encode("utf-8"))
        _SWE_INSTANCE = swe
        return swe
    except Exception as ex:
        _SWE_LOAD_ERROR = str(ex)
        return None

def _lahiri_ayanamsa(jd):
    """Approximate Lahiri ayanamsa (degrees). Good to ~0.1° for modern dates."""
    T = (jd - 2451545.0) / 36525.0
    # Lahiri at J2000 ≈ 23.85°; rate ≈ 50.29"/yr
    return 23.85 + (50.290966 / 3600.0) * T * 100.0

def _approx_planet_longitudes(jd):
    """
    Pure-Python approximate geocentric tropical longitudes (degrees) using
    simplified mean elements. Accurate enough for sign/house placement in a
    trading-timing app (~1–2° for most planets; Moon ~2–3°). Used only when
    native Swiss Ephemeris is unavailable (e.g. Codespace without native/).
    """
    T = (jd - 2451545.0) / 36525.0  # centuries from J2000.0

    def norm(x):
        return x % 360.0

    # Mean longitudes / elements (Meeus-style simplified)
    L_sun = norm(280.46646 + 36000.76983 * T)
    M_sun = norm(357.52911 + 35999.05029 * T)
    C_sun = (1.914602 - 0.004817 * T) * math.sin(math.radians(M_sun)) \
            + 0.019993 * math.sin(math.radians(2 * M_sun))
    sun = norm(L_sun + C_sun)

    # Moon (very simplified)
    L_moon = norm(218.3164477 + 481267.88123421 * T)
    M_moon = norm(134.9633964 + 477198.8675055 * T)
    D = norm(297.8501921 + 445267.1114034 * T)
    F = norm(93.2720950 + 483202.0175233 * T)
    moon = norm(L_moon
                + 6.289 * math.sin(math.radians(M_moon))
                + 1.274 * math.sin(math.radians(2 * D - M_moon))
                + 0.658 * math.sin(math.radians(2 * D))
                + 0.214 * math.sin(math.radians(2 * M_moon)))

    # Mercury, Venus, Mars, Jupiter, Saturn — mean longitude + simple equation of center
    def body(L0, L1, M0, M1, C1, C2=0.0):
        L = norm(L0 + L1 * T)
        M = norm(M0 + M1 * T)
        return norm(L + C1 * math.sin(math.radians(M)) + C2 * math.sin(math.radians(2 * M)))

    me = body(252.2509, 149472.6746, 174.7948, 149472.5152, 23.4400, 2.9818)
    ve = body(181.9798, 58517.8156, 50.4161, 58517.8039, 0.7758, 0.0033)
    ma = body(355.4330, 19140.2993, 19.3730, 19139.8567, 10.6912, 0.6228)
    ju = body(34.3515, 3034.6920, 19.8950, 3034.7320, 5.5550, 0.1680)
    sa = body(50.0775, 1222.1138, 317.0200, 1222.1140, 6.4060, 0.2500)

    # Mean lunar node (Rahu) — retrograde
    ra = norm(125.04452 - 1934.136261 * T)

    return {
        "Su": sun, "Mo": moon, "Me": me, "Ve": ve,
        "Ma": ma, "Ju": ju, "Sa": sa, "Ra": ra,
        "Ke": norm(ra + 180.0),
    }

def _approx_ascendant(jd, lat, lon):
    """Approximate local sidereal time → tropical Ascendant (Whole Sign friendly)."""
    T = (jd - 2451545.0) / 36525.0
    # GMST in degrees
    gmst = norm360(280.46061837 + 360.98564736629 * (jd - 2451545.0)
                   + 0.000387933 * T * T)
    lst = norm360(gmst + lon)  # local sidereal time
    # RAMC = LST; obliquity
    eps = math.radians(23.439291 - 0.0130042 * T)
    lat_r = math.radians(lat)
    ramc = math.radians(lst)
    # Asc = atan2(cos(RAMC), -(sin(RAMC)*cos(eps) + tan(lat)*sin(eps)))
    y = math.cos(ramc)
    x = -(math.sin(ramc) * math.cos(eps) + math.tan(lat_r) * math.sin(eps))
    asc = math.degrees(math.atan2(y, x))
    return norm360(asc)

def calc_planet_positions(jd, lat=19.076, lon=72.877):
    """
    Returns (sid, ay) where sid is sidereal (Lahiri) longitudes for
    As, Su, Mo, Me, Ve, Ma, Ju, Sa, Ra, Ke and ay is ayanamsa degrees.
    Tries native Swiss Ephemeris first; falls back to pure-Python approximation
    when native/libswe.so is missing (Codespace, incomplete APK, etc.).
    """
    global _USE_APPROX_EPHEMERIS
    swe = _get_swisseph()

    if swe is not None:
        try:
            from swisseph_ffi import (
                c_double, create_string_buffer,
                SEFLG_SWIEPH, SEFLG_SPEED, SEFLG_SIDEREAL,
                SE_SUN, SE_MOON, SE_MERCURY, SE_VENUS, SE_MARS,
                SE_JUPITER, SE_SATURN, SE_MEAN_NODE,
            )
            try:
                from swisseph_ffi import SE_SIDM_LAHIRI
                sidm_lahiri = SE_SIDM_LAHIRI
            except ImportError:
                sidm_lahiri = 1
            swe.swe_set_sid_mode(sidm_lahiri, 0, 0)
            flags = SEFLG_SWIEPH | SEFLG_SPEED | SEFLG_SIDEREAL
            planet_ids = {
                "Su": SE_SUN, "Mo": SE_MOON, "Me": SE_MERCURY, "Ve": SE_VENUS,
                "Ma": SE_MARS, "Ju": SE_JUPITER, "Sa": SE_SATURN, "Ra": SE_MEAN_NODE,
            }
            sid = {}
            for key, pid in planet_ids.items():
                xx = (c_double * 6)()
                serr = create_string_buffer(256)
                ret = swe.swe_calc_ut(jd, pid, flags, xx, serr)
                if ret < 0:
                    raise RuntimeError(f"swe_calc_ut failed for {key}: {serr.value.decode(errors='ignore')}")
                sid[key] = xx[0] % 360.0
            sid["Ke"] = (sid["Ra"] + 180.0) % 360.0
            cusps = (c_double * 13)()
            ascmc = (c_double * 10)()
            swe.swe_houses_ex(jd, SEFLG_SIDEREAL, lat, lon, ord(SWISSEPH_HOUSE_SYSTEM), cusps, ascmc)
            sid["As"] = ascmc[0] % 360.0
            ay = swe.swe_get_ayanamsa_ut(jd)
            _USE_APPROX_EPHEMERIS = False
            return sid, ay
        except Exception:
            pass  # fall through to approximate engine

    # ── Pure-Python fallback (no native library required) ──
    _USE_APPROX_EPHEMERIS = True
    tropical = _approx_planet_longitudes(jd)
    ay = _lahiri_ayanamsa(jd)
    sid = {k: (v - ay) % 360.0 for k, v in tropical.items()}
    asc_trop = _approx_ascendant(jd, lat, lon)
    sid["As"] = (asc_trop - ay) % 360.0
    return sid, ay

def ephemeris_diagnostics():
    """On-device check of whether the real Swiss Ephemeris library AND its .se1
    data files are actually present and working — not just whether the app
    silently fell back after the fact. Meant to be run from a button on the
    phone itself, since GitHub Actions succeeding at build time says nothing
    about whether the files survived packaging into the installed APK."""
    lines = []
    try:
        native_dir = _resolve_native_dir()
        lines.append(f"native/ folder: {native_dir}")
    except Exception as ex:
        return "❌ native/ folder NOT FOUND on this device.\n" + str(ex) + \
               "\n\n→ The APK build did not package the native/ folder (or it didn't survive install)."

    machine = platform.machine().lower()
    subdir = "arm64-v8a" if ("aarch64" in machine or "arm64" in machine) else "linux-x64"
    so_path = os.path.join(native_dir, subdir, "libswe.so")
    ephe_path = os.path.join(native_dir, "ephe")

    lines.append(f"Device arch: {machine}  →  expecting subfolder: {subdir}")
    lines.append(("✅" if os.path.exists(so_path) else "❌ MISSING —") + f" libswe.so: {so_path}")

    if os.path.isdir(ephe_path):
        try:
            se1_files = sorted(f for f in os.listdir(ephe_path) if f.lower().endswith(".se1"))
        except Exception:
            se1_files = []
        if se1_files:
            preview = ", ".join(se1_files[:6]) + ("..." if len(se1_files) > 6 else "")
            lines.append(f"✅ ephe/ folder found ({len(se1_files)} .se1 data file(s)): {preview}")
        else:
            lines.append(f"⚠️ ephe/ folder EXISTS but has NO .se1 files inside — download step likely ran into an empty/wrong path: {ephe_path}")
    else:
        lines.append(f"❌ MISSING — ephe/ folder not found: {ephe_path}")

    swe = _get_swisseph()
    if swe is None:
        lines.append(f"❌ libswe.so failed to LOAD. Error: {_SWE_LOAD_ERROR}")
        lines.append("   → App is using the approximate pure-Python engine right now (±1-3°, can shift the D9 sign).")
        return "\n".join(lines)

    try:
        jd_test = jd_from_dt(2000, 1, 1, 12, 0)  # known reference instant
        sid, ay = calc_planet_positions(jd_test)
        if _USE_APPROX_EPHEMERIS:
            lines.append("⚠️ libswe.so loaded OK, but a real test calculation still fell back to the approximate engine.")
            lines.append("   → This means the .se1 data files are missing/corrupt/don't cover this date range, even though libswe.so itself is present.")
        else:
            lines.append(f"✅ Swiss Ephemeris test calculation SUCCEEDED (1 Jan 2000, 12:00 UT — Sun sidereal lon = {sid['Su']:.4f}°, Lahiri ayanamsa = {ay:.4f}°).")
            lines.append("   → Full-precision Swiss Ephemeris IS active on this device right now. D1/D9 charts should match AstroSage.")
    except Exception as ex:
        lines.append(f"❌ Test calculation raised an error: {ex}")
    return "\n".join(lines)

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

    # Each outer corner of the square is split into two houses by the SAME
    # diagonal line that also passes through the center — but the diagonal
    # crosses the corner region at the point exactly midway between that
    # corner and the center (NOT at the center itself, and NOT along the
    # simple corner-to-edge-midpoint line). Getting this point right is what
    # makes houses 2/3, 5/6, 8/9, 11/12 into two DISTINCT, non-overlapping
    # triangles instead of two copies of the same triangle.
    m_tl = ((x0 + cx) / 2, (y0 + cy) / 2)
    m_tr = ((x1 + cx) / 2, (y0 + cy) / 2)
    m_br = ((x1 + cx) / 2, (y1 + cy) / 2)
    m_bl = ((x0 + cx) / 2, (y1 + cy) / 2)

    HOUSES_GEOM = {
        # 4 kendra "kite" quadrants — each is its own quarter of the inner
        # diamond, bounded by the center and the two nearest corner-split points.
        1:  {"poly": [m_tl, (cx, y0), m_tr, (cx, cy)]},
        4:  {"poly": [m_bl, (x0, cy), m_tl, (cx, cy)]},
        7:  {"poly": [m_br, (cx, y1), m_bl, (cx, cy)]},
        10: {"poly": [m_tr, (x1, cy), m_br, (cx, cy)]},
        # 8 corner triangles, two per square corner, split at the m_* points.
        2:  {"poly": [(x0, y0), (cx, y0), m_tl]},
        3:  {"poly": [(x0, y0), m_tl, (x0, cy)]},
        5:  {"poly": [(x0, y1), (x0, cy), m_bl]},
        6:  {"poly": [(x0, y1), m_bl, (cx, y1)]},
        8:  {"poly": [(x1, y1), (cx, y1), m_br]},
        9:  {"poly": [(x1, y1), m_br, (x1, cy)]},
        11: {"poly": [(x1, y0), (x1, cy), m_tr]},
        12: {"poly": [(x1, y0), m_tr, (cx, y0)]},
    }
    for h_num, info in HOUSES_GEOM.items():
        xs = [pt[0] for pt in info["poly"]]
        ys = [pt[1] for pt in info["poly"]]
        info["txt"] = (sum(xs) / len(xs), sum(ys) / len(ys) - 8)
        info["planets"] = (sum(xs) / len(xs), sum(ys) / len(ys) + 10)

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
                    ("   ★ Vargottama: " + ", ".join(sorted(vargottama_set)) if vargottama_set else "") +
                    ("   ⚠️ Approx ephemeris (native libswe.so not found)" if _USE_APPROX_EPHEMERIS else ""),
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
            ramal_container.controls.append(ft.Text("16th House (Final Outcome): " + fi["name"] + "  [" + fi["nature"] 
