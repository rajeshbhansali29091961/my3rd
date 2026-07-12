import os
import sqlite3
import threading
import csv
import io
import time
import math
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
NAK = [
    "अश्विनी","भरणी","कृत्तिका","रोहिणी","मृगशिरा","आर्द्रा",
    "पुनर्वसु","पुष्य","आश्लेषा","मघा","पूर्वाफाल्गुनी","उत्तराफाल्गुनी",
    "हस्त","चित्रा","स्वाति","विशाखा","अनुराधा","ज्येष्ठा",
    "मूल","पूर्वाषाढ़ा","उत्तराषाढ़ा","श्रवण","धनिष्ठा","शतभिषा",
    "पूर्वाभाद्रपद","उत्तराभाद्रपद","रेवती"
]
CURATED = {
    "SBIN":"भारतीय स्टेट बैंक","HDFCBANK":"एचडीएफसी बैंक",
    "ICICIBANK":"आईसीआईसीआई बैंक","AXISBANK":"एक्सिस बैंक",
    "RELIANCE":"रिलायंस","TCS":"टाटा कंसल्टेंसी सर्विसेज",
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
    "ADANIENT":"अदानी एंटरप्राइजेज","ADANIGREEN":"अदानी ग्रीन एनर्जी",
    "DLF":"डीएलएफ","GODREJPROP":"गोदरेज प्रॉपर्टीज",
    "BRITANNIA":"ब्रिटानिया इंडस्ट्रीज","DABUR":"डाबर इंडिया",
    "MARICO":"मेरिको","NESTLEIND":"नेस्ले इंडिया",
    "HEROMOTOCO":"हीरो मोटोकॉर्प","EICHERMOT":"आयशर मोटर्स",
    "ASHOKLEY":"अशोक लेलैंड","TVSMOTOR":"टीवीएस motor",
    "CONCOR":"कंटेनर कॉर्पोरेशन","BHEL":"भारत हेवी इलेक्ट्रिकल्स",
    "APOLLOHOSP":"अपोलो हॉस्पिटल्स","DIVISLAB":"दिविस लेबोरेटरीज",
    "BIOCON":"बायोकॉन","LUPIN":"ल्यूपिन",
    "AUROPHARMA":"ऑरोबिंदो फार्मा","TORNTPHARM":"टोरेंट फार्मा",
}
WD = {
    "LIMITED":"लिमिटेड","LTD":"लिमिटेड","BANK":"बैंक",
    "INDUSTRIES":"इंडस्ट्रीज","INDUSTRY":"उद्योग",
    "INDIA":"INDIA","INDIAN":"इंडियन","POWER":"पावर",
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
    "CONSTRUCTION":"कंструкक्शन","INFRASTRUCTURE":"इन्फ्रास्ट्रक्चर",
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
    "MANAGEMENT":"मैनेजमेंट","CONSULTING":"कंसलिटींग",
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

def make_report(asum, tval, ldate, elapsed_days):
    nv    = (asum % 9) or 9
    g     = GRAHA[(nv - 1) % 9]
    total = asum + tval
    sutra = SUTRA_MAP.get(total % 9, "")
    today = datetime.now()
    nak   = NAK[today.timetuple().tm_yday % 27]
    wday  = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][today.weekday()]
    bars  = {1:"★☆☆☆☆",2:"★★☆☆•",3:"★★★☆☆",4:"★★★★☆",5:"★★★★★"}
    if ldate:
        tc = ((today.timetuple().tm_yday - ldate.timetuple().tm_yday) % 27) + 1
        tn = ["जन्म","सम्पत","विपत","क्षेम","प्रत्यरि","साधक","वध","मित्र","परम-मित्र"]
        tara = tn[(tc-1)%9] + (" GOOD" if tc%9 in(2,4,6,8,0) else " CAUTION")
    else:
        tara = "N/A"
    S  = "─" * 30
    S2 = "═" * 30
    return "\n".join([
        S2, "    BHOOVALAYA ORACLE RESULT", S2, "",
        f"  LISTING DATE : {ldate.strftime('%d-%m-%Y') if ldate else 'N/A'}",
        f"  DAYS LAPSED  : {elapsed_days} Days", "",
        "STEP 1: AKSHARA WEIGHT THEORY", "  (Siribhoovalaya — Jain Text)",
        "  Each Hindi sound has weight:", "  अ=1 आ=2 इ=3 ई=4 उ=5 ऊ=6",
        "  ए=7 ऐ=8 ओ=9 क=11 ब=33 र=37", "  (64 Akshara × weight = sum)", S,
        "STEP 2: NAVAANK CALCULATION", "  (Vedic Digital Root Theory)",
        "  Akshara Sum = " + str(asum), "  Digital Root (1-9) = " + str(nv),
        "  " + _navaank_steps(asum), S,
        "STEP 3: TEMPORAL VIBRATION", "  (Jupiter Cycle = 730 days)",
        "  Days elapsed since listing = " + str(elapsed_days),
        "  Temporal = Days % 730 = " + str(tval),
        "  Combined = " + str(asum) + " + " + str(tval) + " = " + str(total),
        "  Sutra Index = " + str(total) + " % 9 = " + str(total % 9), S,
        "STEP 4: SUTRA PRINCIPLE", "  (Bhoovalaya Cosmic Principle)", "  " + sutra, S,
        "STEP 5: RULING GRAHA (PLANET)", "  (Vedic Financial Astrology)", "  Navaank " + str(nv) + " → " + g[0], S2,
        "  MARKET FORECAST", S2, "  Signal   : " + g[1],
        "  Strength : " + bars.get(g[2],"") + "  " + str(g[2]) + "/5",
        "  Sectors  : " + g[3], "  Hold For : " + g[4], "  Caution  : " + g[5], "  Best Day : " + g[6], S,
        "STEP 6: VEDIC TIMING", "  (Nakshatra + Tara Bala)",
        "  Today    : " + wday + " " + today.strftime("%d-%m-%Y"),
        "  Nakshatra: " + nak, "  Tara Bala: " + tara, "  (Even Tara = GOOD entry)", S2,
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
PLANET_NAMES = {"As":"Lagna","Su":"Sun","Mo":"Moon","Ma":"Mars","Me":"Mercury","Ju":"Jupiter","Ve":"Venus","Sa":"Saturn","Ra":"Rahu","Ke":"Ketu"}

def norm360(x): return x % 360

def jd_from_dt(year, month, day, hour=12, minute=0):
    if month <= 2:
        year -= 1
        month += 12
    A = int(year / 100)
    B = 2 - A + int(A / 4)
    return (int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + hour/24.0 + minute/1440.0 + B - 1524.5)

def lahiri_ayanamsa(jd):
    T = (jd - 2451545.0) / 36525.0
    return 23.85 + 0.013611 * T + 0.000092 * T * T

def calc_planet_positions(jd, lat=19.0544, lon=72.8405):
    T = (jd - 2451545.0) / 36525.0
    sun_t = norm360(280.46646 + 36000.76983 * T)
    moon_t = norm360(218.3164477 + 481267.88123421 * T)
    merc_t = norm360(252.2509 + 149474.0722 * T)
    ven_t  = norm360(181.9798 + 58517.8160 * T)
    mars_t = norm360(355.433 + 19140.2993 * T)
    jup_t  = norm360(34.3515 + 3034.9057 * T)
    sat_t  = norm360(50.0774 + 1222.1138 * T)
    rahu_t = norm360(125.0445 - 1934.1362*T)
    ketu_t = norm360(rahu_t + 180)
    
    eps     = math.radians(23.439291111 - 0.013004167*T)
    GMST    = norm360(280.46061837 + 360.98564736629*(jd - 2451545.0))
    LST     = math.radians(norm360(GMST + lon))
    asc_t   = math.degrees(math.atan2(math.cos(LST), -math.sin(LST)*math.cos(eps) - math.tan(math.radians(lat))*math.sin(eps))) % 360

    ay = lahiri_ayanamsa(jd)
    return {
        "As": (asc_t - ay) % 360, "Su": (sun_t  - ay) % 360, "Mo": (moon_t - ay) % 360,
        "Me": (merc_t - ay) % 360, "Ve": (ven_t  - ay) % 360, "Ma": (mars_t - ay) % 360,
        "Ju": (jup_t  - ay) % 360, "Sa": (sat_t  - ay) % 360, "Ra": (rahu_t - ay) % 360, "Ke": (ketu_t - ay) % 360,
    }, ay

def lon_to_sign_deg(lon): return int((lon % 360) / 30), round(lon % 30, 2)

def d9_sign(lon):
    sign, deg = lon_to_sign_deg(lon)
    nav_num   = int(deg / (30.0 / 9))
    start_map = {0:0, 1:9, 2:6, 3:3, 4:0, 5:9, 6:6, 7:3, 8:0, 9:9, 10:6, 11:3}
    return (start_map[sign] + nav_num) % 12

def build_diamond_chart(positions, lagna_sign, title, chart_size=320):
    W, p = chart_size, 8
    x0, y0, x1, y1 = p, p, W - p, W - p
    cx, cy = W // 2, W // 2
    
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
    for planet, s_idx in positions.items(): sign_planets[int(s_idx)].append(planet)
    
    lagna_s = int(lagna_sign)
    def get_house_sign(h_num): return (lagna_s + h_num - 1) % 12

    shapes = [cv.Fill(paint=ft.Paint(color="#FCFDFE"))]
    for h_num, info in HOUSES_GEOM.items():
        is_lagna = (h_num == 1)
        bg_color = "#FFF8E1" if is_lagna else "#F4F8FA"
        stroke_color = "#B71C1C" if is_lagna else "#1A237E"
        stroke_w = 2.0 if is_lagna else 1.2
        pts = info["poly"]
        path_data = [cv.Path.MoveTo(pts[0][0], pts[0][1])]
        for pt in pts[1:]: path_data.append(cv.Path.LineTo(pt[0], pt[1]))
        path_data.append(cv.Path.Close())
        shapes.append(cv.Path(path_data, paint=ft.Paint(color=bg_color, style=ft.PaintingStyle.FILL)))
        shapes.append(cv.Path(path_data, paint=ft.Paint(color=stroke_color, stroke_width=stroke_w, style=ft.PaintingStyle.STROKE)))

    grid_paint = ft.Paint(color="#1A237E", stroke_width=1.5, style=ft.PaintingStyle.STROKE)
    shapes.extend([
        cv.Line(x0, y0, x1, y1, paint=grid_paint), cv.Line(x1, y0, x0, y1, paint=grid_paint),
        cv.Line(cx, y0, x0, cy, paint=grid_paint), cv.Line(x0, cy, cx, y1, paint=grid_paint),
        cv.Line(cx, y1, x1, cy, paint=grid_paint), cv.Line(x1, cy, cx, y0, paint=grid_paint),
        cv.Rect(x=x0, y=y0, width=W-(2*p), height=W-(2*p), paint=grid_paint)
    ])

    for h_num, info in HOUSES_GEOM.items():
        sign_idx = get_house_sign(h_num)
        planets_here = sign_planets.get(sign_idx, [])
        tx, ty = info["txt"]
        shapes.append(cv.Text(x=tx - 6, y=ty - 10, text=str(sign_idx + 1), style=ft.TextStyle(size=12, color="#263238", weight="bold")))
        shapes.append(cv.Text(x=tx + 5, y=ty - 8, text=f"({SIGN_ABB[sign_idx]})", style=ft.TextStyle(size=8, color="#78909C")))
        if planets_here:
            px, py = info["planets"]
            planets_txt = " ".join(planets_here)
            shapes.append(cv.Text(x=px - (len(planets_txt) * 3), y=py, text=planets_txt, style=ft.TextStyle(size=11, color="#D32F2F", weight="bold")))

    shapes.append(cv.Text(x=cx - 30, y=cy - 8, text=title, style=ft.TextStyle(size=10, color="#1A237E", weight="bold", bgcolor="#E8EAF6")))
    return cv.Canvas(shapes=shapes, width=W, height=W)

# ── MAIN APP ───────────────────────────────────────────────────────────────────
def main(page: ft.Page):
    try:
        page.title, page.bgcolor, page.padding, page.scroll = "Bhoovalaya Oracle", C["bg"], 8, "auto"
        db_path = os.path.join(os.getenv("FLET_APP_STORAGE_DATA", "."), "bhuvalaya.db")

        # Database Setup
        conn = sqlite3.connect(db_path)
        conn.execute("""CREATE TABLE IF NOT EXISTS stocks(
            symbol TEXT PRIMARY KEY, eng_name TEXT, hindi_name TEXT, ldate TEXT, asum INTEGER, breakdown TEXT, series TEXT DEFAULT 'EQ')""")
        conn.commit()
        conn.close()

        def db_count(): return sqlite3.connect(db_path).execute("SELECT COUNT(*) FROM stocks").fetchone()[0]
        def db_search(q): return sqlite3.connect(db_path).execute("SELECT symbol, eng_name, hindi_name, ldate, asum FROM stocks WHERE symbol LIKE ? OR eng_name LIKE ? ORDER BY symbol LIMIT 100", ("%"+q+"%", "%"+q+"%")).fetchall()
        def db_get(sym): return sqlite3.connect(db_path).execute("SELECT * FROM stocks WHERE symbol=?", (sym,)).fetchone()
        def db_save(sym, eng, hindi, ldate, series="EQ"):
            asum, bk = calc(hindi)
            try:
                c = sqlite3.connect(db_path)
                c.execute("INSERT OR REPLACE INTO stocks VALUES(?,?,?,?,?,?,?)", (sym, eng, hindi, ldate, asum, bk, series))
                c.commit(); c.close()
                return True, asum
            except Exception as ex: return False, str(ex)

        status_txt = ft.Text("Loading...", size=15, color="#FFFFFF", weight="bold")
        status_bar = ft.Container(content=status_txt, bgcolor=C["secondary"], padding=10, border_radius=6)
        prg_bar, prg_txt = ft.ProgressBar(value=0, visible=False, color="#FF6F00", bgcolor="#EEEEEE"), ft.Text("", size=14, color=C["orange"], weight="bold")

        def set_status(msg, color=None): status_txt.value, status_bar.bgcolor = msg, color or C["secondary"]; page.update()
        def set_prg(pct, msg=""): prg_bar.visible, prg_bar.value, prg_txt.value = True, pct, msg; page.update()
        def hide_prg(): prg_bar.visible, prg_txt.value = False, ""; page.update()
        def make_field(label, hint="", value="", multiline=False):
            return ft.TextField(label=label, label_style=ft.TextStyle(size=14, color=C["primary"]), hint_text=hint, hint_style=ft.TextStyle(size=13, color=C["hint_txt"]), value=value, text_style=ft.TextStyle(size=16, color=C["black_txt"], weight="bold"), border_color=C["primary"], focused_border_color=C["accent"], border_width=2, bgcolor=C["inp_bg"], multiline=multiline, min_lines=1 if not multiline else 2)
        def make_header(title, bgcolor=None): return ft.Container(content=ft.Text(title, size=16, color="#FFFFFF", weight="bold"), bgcolor=bgcolor or C["primary"], padding=ft.padding.symmetric(horizontal=12, vertical=8), border_radius=6)

        # ── SCREEN 1: ORACLE SEARCH ───────────────────────────────────────────
        fld_oracle = make_field("NSE Stock Symbol or Name", hint="Example: RELIANCE or TCS", value="RELIANCE")
        result_txt = ft.Text("", size=15, color=C["dark_txt"], selectable=True, font_family="monospace")
        result_box = ft.Container(content=result_txt, bgcolor=C["res_bg"], padding=14, border_radius=8, border=ft.Border(top=ft.BorderSide(2, C["primary"]), bottom=ft.BorderSide(2, C["primary"]), left=ft.BorderSide(2, C["primary"]), right=ft.BorderSide(2, C["primary"])), visible=False)

        def do_oracle(e):
            q = fld_oracle.value.strip().upper()
            if not q: set_status("Enter a stock symbol.", C["red"]); return
            if db_count() < 1: set_status("Database empty! Build database first.", C["red"]); return
            
            row = db_get(q) or (rows := db_search(q) and db_get(rows[0][0]))
            if row:
                sym, eng, hi, ldt, asum, bk, *_ = row
                ldate = parse_dt(ldt)
                days_lapsed = (datetime.now() - ldate).days if ldate else 0
                tval  = days_lapsed % 730
                rep   = make_report(asum, tval, ldate, days_lapsed)
                set_status(f"Calculated: {sym}", C["green"])
                result_txt.value = rep
                result_box.visible = True
            else:
                set_status(f"Not found: {q}", C["red"])
            page.update()

        oracle_screen = ft.Column(visible=True, controls=[
            make_header("🔮 BHOOVALAYA ORACLE ENGINE"), ft.Divider(height=4, color=C["divider"]),
            fld_oracle,
            ft.ElevatedButton("🔍 SEARCH AND PREDICT", bgcolor=C["primary"], color="#FFFFFF", elevation=4, height=52, style=ft.ButtonStyle(text_style=ft.TextStyle(size=16, weight="bold")), on_click=do_oracle),
            ft.Divider(height=6, color=C["divider"]), result_box
        ])

        # ── SCREEN 2: STOCK LIST ──────────────────────────────────────────────
        fld_list_search, list_rows, list_count_txt = make_field("Search Symbol or Company Name"), ft.Column(controls=[], spacing=2), ft.Text("", size=14, color=C["primary"], weight="bold")
        
        def load_list(q=""):
            list_rows.controls.clear()
            rows = db_search(q)
            list_count_txt.value = f"Showing {len(rows)} stocks"
            for i, r in enumerate(rows):
                sym, eng, hi, ldt, asum = r
                list_rows.controls.append(ft.Container(
                    content=ft.Column([
                        ft.Row([ft.Container(content=ft.Text(sym, size=14, color="#FFFFFF", weight="bold"), bgcolor=C["primary"], padding=4, border_radius=4), ft.Text(f"Listed: {ldt}", size=12, color=C["hint_txt"]), ft.Text(f"Akshara: {asum}", size=12, color=C["accent"])]),
                        ft.Text(eng, size=13, color=C["black_txt"], weight="bold"), ft.Text(hi, size=14, color=C["green"], weight="bold"),
                        ft.Row([ft.TextButton("✏️ Edit", on_click=lambda e, s=sym: load_edit(s)), ft.TextButton("🔮 Analyze", on_click=lambda e, s=sym: (setattr(fld_oracle, 'value', s), show_screen("oracle"), do_oracle(e)))])
                    ]), bgcolor=C["row_odd"] if i%2==0 else C["row_even"], padding=8, border_radius=6))
            page.update()

        list_screen = ft.Column(visible=False, controls=[
            make_header("📋 NSE EQUITY STOCK LIST"), fld_list_search,
            ft.Row([
                ft.ElevatedButton("🔍 SEARCH", bgcolor=C["primary"], color="#FFFFFF", elevation=4, on_click=lambda e: load_list(fld_list_search.value.strip().upper())),
                ft.ElevatedButton("📋 SHOW ALL", bgcolor=C["accent"], color="#FFFFFF", elevation=4, on_click=lambda e: load_list(""))
            ]), list_count_txt, list_rows
        ])

        # ── SCREEN 3: DATA ENTRY ──────────────────────────────────────────────
        fld_sym, fld_eng, fld_hindi, fld_ldate, fld_series = make_field("Symbol *"), make_field("English Name *"), make_field("Hindi Name *"), make_field("Listing Date (DD-MM-YYYY)"), make_field("Series", value="EQ")
        entry_status, akshara_preview = ft.Text("", size=14, color=C["green"], weight="bold"), ft.Container(content=ft.Text(""), bgcolor=C["res_bg"], padding=8, visible=False)

        def load_edit(sym):
            row = db_get(sym)
            if row:
                fld_sym.value, fld_eng.value, fld_hindi.value, fld_ldate.value, fld_series.value = row[0], row[1], row[2], row[3], row[6]
                fld_sym.disabled = True
                show_screen("entry")

        entry_screen = ft.Column(visible=False, controls=[
            make_header("✏️ MANAGE STOCK DATA ENTRY"), fld_sym, fld_eng,
            ft.ElevatedButton("🌐 AUTO TRANSLITERATE HINDI", bgcolor=C["accent"], color="#FFFFFF", elevation=4, on_click=lambda e: (setattr(fld_hindi, 'value', get_hindi(fld_sym.value.upper(), fld_eng.value)), setattr(akshara_preview.content, 'value', f"Weight: {calc(fld_hindi.value)[0]}"), setattr(akshara_preview, 'visible', True), page.update())),
            fld_hindi, akshara_preview, fld_ldate, fld_series, entry_status,
            ft.Row([
                ft.ElevatedButton("💾 SAVE NEW", bgcolor=C["green"], color="#FFFFFF", elevation=4, on_click=lambda e: db_save(fld_sym.value.upper(), fld_eng.value, fld_hindi.value, fld_ldate.value, fld_series.value) and set_status("Saved!", C["green"])),
                ft.ElevatedButton("🔄 UPDATE", bgcolor=C["primary"], color="#FFFFFF", elevation=4, on_click=lambda e: db_save(fld_sym.value.upper(), fld_eng.value, fld_hindi.value, fld_ldate.value, fld_series.value) and set_status("Updated!", C["green"])),
                ft.ElevatedButton("🧹 CLEAR", bgcolor=C["hint_txt"], color="#FFFFFF", elevation=4, on_click=lambda e: (setattr(fld_sym,'value',""), setattr(fld_sym,'disabled',False), setattr(fld_eng,'value',""), setattr(fld_hindi,'value',""), setattr(fld_ldate,'value',""), page.update()))
            ])
        ])

        # ── SCREEN 4: ASTRO CHART ────────────────────────────────────────────
        fld_date, fld_time, fld_lat, fld_lon = make_field("Date", value=datetime.now().strftime("%d-%m-%Y")), make_field("Time", value=datetime.now().strftime("%H:%M")), make_field("Latitude", value="19.0544"), make_field("Longitude", value="72.8405")
        astro_chart_container = ft.Column(spacing=20, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        def do_astro(e):
            try:
                dt = parse_dt(fld_date.value)
                tm = fld_time.value.split(":")
                pos, ay = calc_planet_positions(jd_from_dt(dt.year, dt.month, dt.day, int(tm[0]), int(tm[1])), float(fld_lat.value), float(fld_lon.value))
                astro_chart_container.controls.clear()
                
                # Render D1 Rasi Chart
                astro_chart_container.controls.append(make_header("📍 D1 RASI CHART", bgcolor=C["primary"]))
                astro_chart_container.controls.append(ft.Container(content=build_diamond_chart({p: lon_to_sign_deg(l)[0] for p, l in pos.items()}, lon_to_sign_deg(pos["As"])[0], "D1 RASI")))
                
                # Split Divider
                astro_chart_container.controls.append(ft.Divider(height=10, color=C["divider"]))
                
                # Render D9 Navamsha Chart strictly separated
                astro_chart_container.controls.append(make_header("📐 D9 NAVAMSHA CHART", bgcolor=C["secondary"]))
                astro_chart_container.controls.append(ft.Container(content=build_diamond_chart({p: d9_sign(l) for p, l in pos.items()}, d9_sign(pos["As"]), "D9 NAVAMSHA")))
                set_status("Charts Drawn!", C["green"])
            except Exception as ex: set_status(f"Error: {ex}", C["red"])

        astro_screen = ft.Column(visible=False, controls=[
            make_header("🕉️ VEDIC KUNDALI ENGINES"), ft.Row([fld_date, fld_time]), ft.Row([fld_lat, fld_lon]),
            ft.ElevatedButton("🕉️ GENERATE SEPARATE CHARTS", bgcolor=C["green"], color="#FFFFFF", elevation=4, height=52, on_click=do_astro),
            astro_chart_container
        ])

        # ── SCREEN 5: DATABASE BUILD ─────────────────────────────────────────
        def build_db_thread():
            try:
                set_status("Downloading official listing dates from NSE India...", C["accent"])
                res = requests.get(NSE_URL, timeout=15)
                r = csv.reader(io.StringIO(res.text))
                next(r) # skip header row
                rows = list(r)
                total = len(rows)
                
                db_c = sqlite3.connect(db_path)
                for idx, row in enumerate(rows):
                    if not row or len(row) < 7: continue
                    sym, eng, series, ldt = row[0].strip(), row[1].strip(), row[2].strip(), row[6].strip()
                    if series != "EQ": continue
                    
                    # Store data along with official listing date (ldt) from Column 7
                    hi = get_hindi(sym, eng)
                    asum, bk = calc(hi)
                    db_c.execute("INSERT OR REPLACE INTO stocks VALUES(?,?,?,?,?,?,?)", (sym, eng, hi, ldt, asum, bk, series))
                    if idx % 10 == 0: set_prg(idx/total, f"Processing {sym} ({ldt})")
                db_c.commit(); db_c.close()
                hide_prg(); set_status(f"Success! Database complete.", C["green"])
            except Exception as ex: hide_prg(); set_status(f"Failed: {ex}", C["red"])

        db_screen = ft.Column(visible=False, controls=[
            make_header("⚙️ ENGINE SYSTEM SETUP"),
            ft.ElevatedButton("⚡ BUILD AUTOMATED DATABASE WITH NSE DATES", bgcolor=C["orange"], color="#FFFFFF", elevation=4, height=54, on_click=lambda e: threading.Thread(target=build_db_thread, daemon=True).start()),
            prg_bar, prg_txt
        ])

        # ── NAVIGATION INTERACTION CONTROL ─────────────────────────────────────
        all_screens = {"oracle": oracle_screen, "list": list_screen, "entry": entry_screen, "astro": astro_screen, "db": db_screen}
        def show_screen(name):
            for k, v in all_screens.items(): v.visible = (k == name)
            page.update()

        nav_bar = ft.NavigationBar(
            destinations=[
                ft.NavigationBarDestination(icon=ft.Icons.PSYCHOLOGY, label="Oracle"),
                ft.NavigationBarDestination(icon=ft.Icons.FORMAT_LIST_BULLETED, label="Stocks"),
                ft.NavigationBarDestination(icon=ft.Icons.EDIT_NOTE, label="Entry"),
                ft.NavigationBarDestination(icon=ft.Icons.STARS, label="Kundali"),
                ft.NavigationBarDestination(icon=ft.Icons.STORAGE, label="Database"),
            ],
            on_change=lambda e: show_screen(["oracle", "list", "entry", "astro", "db"][int(e.data)]),
            bgcolor="#E8EAF6"
        )

        page.add(status_bar, oracle_screen, list_screen, entry_screen, astro_screen, db_screen, nav_bar)
        set_status(f"Engine Ready — {db_count()} stocks configured.", C["green"])
    except Exception as err:
        page.add(ft.Container(content=ft.Text(f"Fatal Setup Error:\n{err}", color="#FFFFFF"), bgcolor=C["red"], padding=20))
        page.update()

if __name__ == "__main__":
    ft.app(target=main)
