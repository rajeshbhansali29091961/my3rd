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
    "RELIANCE":"रिलायंस इंडस्ट्रीज","TCS":"टाटा कंसल्टेंसी सर्विसेज",
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
    "HINDALCO":"हिंडाल्को इंडस्ट्रीज","VEDL":"वेदांता",
    "TATAPOWER":"टाटा पावर","ADANIPOWER":"अदानी पावर",
    "ADANIENT":"अदानी एंटरप्राइजेज","ADANIGREEN":"अदानी ग्रीन एनर्जी",
    "DLF":"डीएलएफ","GODREJPROP":"गोदरेज प्रॉपर्टीज",
    "BRITANNIA":"ब्रिटानिया इंडस्ट्रीज","DABUR":"डाबर इंडिया",
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
            out.append(WD.get(cw,
                "".join(PR.get(c,"") for c in cw)))
        return " ".join(out)
    try:
        url = ("https://translate.googleapis.com/translate_a/single"
               "?client=gtx&sl=en&tl=hi&dt=t&q="
               + requests.utils.quote(eng))
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
                "https://inputtools.google.com/request?text="
                + cw + "&ime=transliteration_en_hi&num=1",
                timeout=4).json()
            out.append(r[1][0][1][0] if r[0]=="SUCCESS"
                       else "".join(PR.get(c,"") for c in cw))
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
    total = asum + tval
    sutra = SUTRA_MAP.get(total % 9, "")
    today = datetime.now()
    nak   = NAK[today.timetuple().tm_yday % 27]
    wday  = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][today.weekday()]
    bars  = {1:"★☆☆☆☆",2:"★★☆☆☆",3:"★★★☆☆",4:"★★★★☆",5:"★★★★★"}
    if ldate:
        tc = ((today.timetuple().tm_yday -
               ldate.timetuple().tm_yday) % 27) + 1
        tn = ["जन्म","सम्पत","विपत","क्षेम","प्रत्यरि",
              "साधक","वध","मित्र","परम-मित्र"]
        tara = tn[(tc-1)%9] + (
            " GOOD" if tc%9 in(2,4,6,8,0) else " CAUTION")
    else:
        tara = "N/A"
    S  = "─" * 30
    S2 = "═" * 30
    return "\n".join([
        S2,
        "    BHOOVALAYA ORACLE RESULT",
        S2,
        "",
        "STEP 1: AKSHARA WEIGHT THEORY",
        "  (Siribhoovalaya — Jain Text)",
        "  Each Hindi sound has weight:",
        "  अ=1 आ=2 इ=3 ई=4 उ=5 ऊ=6",
        "  ए=7 ऐ=8 ओ=9 क=11 ब=33 र=37",
        "  (64 Akshara × weight = sum)",
        S,
        "STEP 2: NAVAANK CALCULATION",
        "  (Vedic Digital Root Theory)",
        "  Akshara Sum = " + str(asum),
        "  Digital Root (1-9) = " + str(nv),
        "  " + _navaank_steps(asum),
        S,
        "STEP 3: TEMPORAL VIBRATION",
        "  (Jupiter Cycle = 730 days)",
        "  Days elapsed since listing",
        "  Temporal = Days % 730 = " + str(tval),
        "  Combined = " + str(asum) + " + " + str(tval)
          + " = " + str(total),
        "  Sutra Index = " + str(total) + " % 9 = "
          + str(total % 9),
        S,
        "STEP 4: SUTRA PRINCIPLE",
        "  (Bhoovalaya Cosmic Principle)",
        "  " + sutra,
        S,
        "STEP 5: RULING GRAHA (PLANET)",
        "  (Vedic Financial Astrology)",
        "  Navaank " + str(nv) + " → " + g[0],
        S2,
        "  MARKET FORECAST",
        S2,
        "  Signal   : " + g[1],
        "  Strength : " + bars.get(g[2],"") + "  " + str(g[2]) + "/5",
        "  Sectors  : " + g[3],
        "  Hold For : " + g[4],
        "  Caution  : " + g[5],
        "  Best Day : " + g[6],
        S,
        "STEP 6: VEDIC TIMING",
        "  (Nakshatra + Tara Bala)",
        "  Today    : " + wday + " " + today.strftime("%d-%m-%Y"),
        "  Nakshatra: " + nak,
        "  Tara Bala: " + tara,
        "  (Even Tara = GOOD entry)",
        S2,
        "  Research only. Not SEBI advice.",
        S2,
    ])

def _navaank_steps(n):
    """Show digital root reduction steps."""
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
SIGN_ABB  = ["Ar","Ta","Ge","Ca","Le","Vi",
             "Li","Sc","Sg","Cp","Aq","Pi"]
SIGN_HI   = ["मेष","वृष","मिथुन","कर्क","सिंह","कन्या",
             "तुला","वृश्चिक","धनु","मकर","कुंभ","मीन"]
SIGN_FULL = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo",
             "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
PLANET_NAMES = {
    "As":"Lagna","Su":"Sun-सूर्य","Mo":"Moon-चंद्र",
    "Ma":"Mars-मंगल","Me":"Mercury-बुध","Ju":"Jupiter-गुरु",
    "Ve":"Venus-शुक्र","Sa":"Saturn-शनि",
    "Ra":"Rahu-राहु","Ke":"Ketu-केतु"
}
# South Indian chart: sign_index -> (row, col)
SI_POS = {
    0:(0,1),1:(0,2),2:(0,3),3:(1,3),
    4:(2,3),5:(3,3),6:(3,2),7:(3,1),
    8:(3,0),9:(2,0),10:(1,0),11:(0,0)
}

def norm360(x):
    return x % 360

def jd_from_dt(year, month, day, hour=12, minute=0):
    """Julian Day Number from date/time."""
    if month <= 2:
        year -= 1
        month += 12
    A = int(year / 100)
    B = 2 - A + int(A / 4)
    return (int(365.25 * (year + 4716))
            + int(30.6001 * (month + 1))
            + day + hour/24.0 + minute/1440.0
            + B - 1524.5)

def lahiri_ayanamsa(jd):
    """Lahiri (Chitrapaksha) Ayanamsa in degrees."""
    T = (jd - 2451545.0) / 36525.0
    return 23.85 + 0.013611 * T + 0.000092 * T * T

def calc_planet_positions(jd, lat=19.076, lon=72.877):
    """
    Calculate sidereal planetary longitudes using simplified VSOP87.
    Returns dict of planet abbreviation -> longitude (0-360 sidereal).
    lat/lon default = Mumbai, India.
    """
    T = (jd - 2451545.0) / 36525.0

    # ── Sun ────────────────────────────────────────────────────────────────────
    L0   = norm360(280.46646 + 36000.76983 * T)
    M_su = math.radians(norm360(357.52911 + 35999.05029 * T))
    C_su = ((1.914602 - 0.004817*T - 0.000014*T*T) * math.sin(M_su)
            + (0.019993 - 0.000101*T) * math.sin(2*M_su)
            + 0.000289 * math.sin(3*M_su))
    sun_t = norm360(L0 + C_su)

    # ── Moon ───────────────────────────────────────────────────────────────────
    L_mo  = norm360(218.3164477 + 481267.88123421 * T)
    D_mo  = math.radians(norm360(297.8501921 + 445267.1114034 * T))
    M_mo  = math.radians(norm360(134.9633964 + 477198.8675055 * T))
    M_su2 = math.radians(norm360(357.5291092 + 35999.0502909 * T))
    moon_t = norm360(
        L_mo
        + 6.289  * math.sin(M_mo)
        - 1.274  * math.sin(2*D_mo - M_mo)
        + 0.658  * math.sin(2*D_mo)
        - 0.214  * math.sin(2*M_mo)
        - 0.186  * math.sin(M_su2)
    )

    # ── Mercury ────────────────────────────────────────────────────────────────
    L_me  = norm360(252.2509 + 149474.0722 * T)
    M_me  = math.radians(norm360(168.6562 + 149472.5153 * T))
    merc_t = norm360(L_me + 23.440*math.sin(M_me)
                     + 2.912*math.sin(2*M_me)
                     + 0.513*math.sin(3*M_me))

    # ── Venus ──────────────────────────────────────────────────────────────────
    L_ve  = norm360(181.9798 + 58517.8160 * T)
    M_ve  = math.radians(norm360(212.9346 + 58517.8039 * T))
    ven_t  = norm360(L_ve + 47.682*math.sin(M_ve)
                     + 1.319*math.sin(2*M_ve))

    # ── Mars ───────────────────────────────────────────────────────────────────
    L_ma  = norm360(355.433 + 19140.2993 * T)
    M_ma  = math.radians(norm360(19.373 + 19140.2973 * T))
    mars_t = norm360(L_ma + 10.691*math.sin(M_ma)
                     + 0.623*math.sin(2*M_ma)
                     + 0.050*math.sin(3*M_ma))

    # ── Jupiter ────────────────────────────────────────────────────────────────
    L_ju  = norm360(34.3515 + 3034.9057 * T)
    M_ju  = math.radians(norm360(20.9961 + 3034.9056 * T))
    jup_t  = norm360(L_ju + 5.555*math.sin(M_ju)
                     + 0.168*math.sin(2*M_ju))

    # ── Saturn ─────────────────────────────────────────────────────────────────
    L_sa  = norm360(50.0774 + 1222.1138 * T)
    M_sa  = math.radians(norm360(317.0207 + 1221.5515 * T))
    sat_t  = norm360(L_sa + 6.393*math.sin(M_sa)
                     + 0.170*math.sin(2*M_sa))

    # ── Rahu / Ketu (Mean Node) ────────────────────────────────────────────────
    rahu_t = norm360(125.0445 - 1934.1362*T + 0.0020708*T*T)
    ketu_t = norm360(rahu_t + 180)

    # ── Ascendant (Lagna) ──────────────────────────────────────────────────────
    eps     = math.radians(23.439291111 - 0.013004167*T)
    GMST    = norm360(280.46061837
                      + 360.98564736629*(jd - 2451545.0)
                      + 0.000387933*T*T)
    LST     = math.radians(norm360(GMST + lon))
    lat_r   = math.radians(lat)
    asc_t   = math.degrees(math.atan2(
        math.cos(LST),
        -math.sin(LST)*math.cos(eps) - math.tan(lat_r)*math.sin(eps)
    )) % 360

    # ── Apply Lahiri Ayanamsa ──────────────────────────────────────────────────
    ay = lahiri_ayanamsa(jd)
    sid = {
        "As": (asc_t - ay) % 360,
        "Su": (sun_t  - ay) % 360,
        "Mo": (moon_t - ay) % 360,
        "Me": (merc_t - ay) % 360,
        "Ve": (ven_t  - ay) % 360,
        "Ma": (mars_t - ay) % 360,
        "Ju": (jup_t  - ay) % 360,
        "Sa": (sat_t  - ay) % 360,
        "Ra": (rahu_t - ay) % 360,
        "Ke": (ketu_t - ay) % 360,
    }
    return sid, ay

def lon_to_sign_deg(lon):
    """Return (sign_index 0-11, degree_in_sign)."""
    lon = lon % 360
    return int(lon / 30), round(lon % 30, 2)

def d9_sign(lon):
    """Calculate Navamsa (D9) sign index (0-11)."""
    sign, deg = lon_to_sign_deg(lon)
    nav_num   = int(deg / (30.0 / 9))   # 0-8
    start_map = {
        0:0, 1:9, 2:6,  3:3,
        4:0, 5:9, 6:6,  7:3,
        8:0, 9:9, 10:6, 11:3
    }
    return (start_map[sign] + nav_num) % 12

def build_chart_grid(positions, title="D1 RASI CHART"):
    """
    Build South Indian style chart grid.
    positions = {planet: sign_index}
    Returns a 4x4 list of lists of strings.
    """
    # Map sign -> list of planets in that sign
    sign_planets = {i: [] for i in range(12)}
    for planet, sign_idx in positions.items():
        sign_planets[sign_idx].append(planet)

    # Build 4x4 grid
    grid = [["" for _ in range(4)] for _ in range(4)]

    for sign_idx, (row, col) in SI_POS.items():
        planets_here = sign_planets.get(sign_idx, [])
        sign_name    = SIGN_ABB[sign_idx]
        hindi_name   = SIGN_HI[sign_idx]
        planet_str   = " ".join(planets_here)
        cell_text    = sign_name + "/" + hindi_name
        if planet_str:
            cell_text += "\n" + planet_str
        grid[row][col] = cell_text

    grid[1][1] = title
    grid[1][2] = ""
    grid[2][1] = ""
    grid[2][2] = ""
    return grid


# ── MAIN APP ───────────────────────────────────────────────────────────────────
def main(page: ft.Page):
    try:
        page.title   = "Bhoovalaya Oracle"
        page.bgcolor = C["bg"]
        page.padding = 8
        page.scroll  = "auto"

        # ── DB SETUP ───────────────────────────────────────────────────────────
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
                series      TEXT DEFAULT 'EQ')""")
            conn.commit()
            conn.close()
        except Exception as dbe:
            pass

        def db_count():
            try:
                return sqlite3.connect(db_path).execute(
                    "SELECT COUNT(*) FROM stocks").fetchone()[0]
            except: return 0

        def db_search(q):
            try:
                conn = sqlite3.connect(db_path)
                rows = conn.execute(
                    "SELECT symbol, eng_name, hindi_name, ldate, asum "
                    "FROM stocks WHERE symbol LIKE ? OR eng_name LIKE ? "
                    "ORDER BY symbol LIMIT 100",
                    ("%" + q + "%", "%" + q + "%")
                ).fetchall()
                conn.close()
                return rows
            except: return []

        def db_get(sym):
            try:
                conn = sqlite3.connect(db_path)
                row  = conn.execute(
                    "SELECT * FROM stocks WHERE symbol=?",
                    (sym,)).fetchone()
                conn.close()
                return row
            except: return None

        def db_save(sym, eng, hindi, ldate, series="EQ"):
            asum, bk = calc(hindi)
            try:
                conn = sqlite3.connect(db_path)
                conn.execute(
                    "INSERT OR REPLACE INTO stocks "
                    "VALUES(?,?,?,?,?,?,?)",
                    (sym, eng, hindi, ldate, asum, bk, series))
                conn.commit()
                conn.close()
                return True, asum
            except Exception as ex:
                return False, str(ex)

        def db_delete(sym):
            try:
                conn = sqlite3.connect(db_path)
                conn.execute(
                    "DELETE FROM stocks WHERE symbol=?", (sym,))
                conn.commit()
                conn.close()
                return True
            except: return False

        # ── SHARED STATUS BAR ──────────────────────────────────────────────────
        status_txt = ft.Text(
            "Loading...", size=15,
            color="#FFFFFF", weight="bold")
        status_bar = ft.Container(
            content=status_txt,
            bgcolor=C["secondary"],
            padding=10, border_radius=6)

        prg_bar  = ft.ProgressBar(
            value=0, visible=False,
            color="#FF6F00", bgcolor="#EEEEEE")
        prg_txt  = ft.Text(
            "", size=14,
            color=C["orange"], weight="bold")

        def set_status(msg, color=None):
            status_txt.value   = msg
            status_bar.bgcolor = color or C["secondary"]
            page.update()

        def set_prg(pct, msg=""):
            prg_bar.visible = True
            prg_bar.value   = pct
            prg_txt.value   = msg
            page.update()

        def hide_prg():
            prg_bar.visible = False
            prg_txt.value   = ""
            page.update()

        # ── HELPER: make text field ────────────────────────────────────────────
        def make_field(label, hint="", value="", multiline=False):
            return ft.TextField(
                label=label,
                label_style=ft.TextStyle(
                    size=14, color=C["primary"]),
                hint_text=hint,
                hint_style=ft.TextStyle(
                    size=13, color=C["hint_txt"]),
                value=value,
                text_size=16,
                text_style=ft.TextStyle(
                    size=16, color=C["black_txt"],
                    weight="bold"),
                border_color=C["primary"],
                focused_border_color=C["accent"],
                border_width=2,
                bgcolor=C["inp_bg"],
                cursor_color=C["primary"],
                multiline=multiline,
                min_lines=1 if not multiline else 2,
            )

        # ── HELPER: section header ─────────────────────────────────────────────
        def make_header(title, bgcolor=None):
            return ft.Container(
                content=ft.Text(
                    title, size=16,
                    color="#FFFFFF", weight="bold"),
                bgcolor=bgcolor or C["primary"],
                padding=ft.padding.symmetric(
                    horizontal=12, vertical=8),
                border_radius=6)

        # ══════════════════════════════════════════════════════════════════════
        # SCREEN 1 — ORACLE SEARCH
        # ══════════════════════════════════════════════════════════════════════
        fld_oracle = make_field(
            "NSE Stock Symbol or Name",
            hint="Example: RELIANCE or TCS or SBIN",
            value="RELIANCE")

        result_txt = ft.Text(
            "", size=15,
            color=C["dark_txt"],
            selectable=True,
            font_family="monospace")

        result_box = ft.Container(
            content=result_txt,
            bgcolor=C["res_bg"],
            padding=14,
            border_radius=8,
            border=ft.Border(
                top=ft.BorderSide(2, C["primary"]),
                bottom=ft.BorderSide(2, C["primary"]),
                left=ft.BorderSide(2, C["primary"]),
                right=ft.BorderSide(2, C["primary"])),
            visible=False)

        def do_oracle(e):
            q = fld_oracle.value.strip().upper()
            if not q:
                set_status("Enter a stock symbol.", C["red"])
                return
            set_status("Searching: " + q + " ...", C["accent"])
            if db_count() < 5:
                set_status("Database empty! Tap BUILD DATABASE.", C["red"])
                result_txt.value = (
                    "DATABASE IS EMPTY\n\n"
                    "Go to Database tab and\n"
                    "tap BUILD DATABASE button.\n\n"
                    "Needs internet — 5 to 15 minutes.")
                result_box.visible = True
                page.update()
                return
            row = db_get(q)
            if not row:
                rows = db_search(q)
                if rows:
                    row = db_get(rows[0][0])
            if row:
                sym, eng, hi, ldt, asum, bk, *_ = row
                ldate = parse_dt(ldt)
                today = datetime.now()
                days  = (today - ldate).days if ldate else 0
                tval  = days % 730
                rep   = make_report(asum, tval, ldate)
                set_status("Found: " + sym, C["green"])
                result_txt.value = "\n".join([
                    "━" * 30,
                    "SYMBOL  : " + sym,
                    "COMPANY : " + eng,
                    "HINDI   : " + hi,
                    "LISTED  : " + ldt,
                    "━" * 30,
                    "AKSHARA SUM  = " + str(asum),
                    "TEMPORAL MOD = " + str(tval),
                    "COMBINED VIB = " + str(asum + tval),
                    "NAVAANK      = " + str((asum % 9) or 9),
                    "",
                    rep,
                ])
                result_box.visible = True
            else:
                set_status("Not found: " + q, C["red"])
                result_txt.value = (
                    "'" + q + "' NOT FOUND\n\n"
                    "Try: RELIANCE TCS SBIN\n"
                    "     INFY WIPRO ITC LT")
                result_box.visible = True
            page.update()

        oracle_screen = ft.Column(
            visible=True,
            controls=[
                make_header("🔮  ORACLE ANALYSIS"),
                ft.Divider(height=4, color=C["divider"]),
                ft.Text("Enter Stock Symbol or Name:",
                        size=15, color=C["black_txt"],
                        weight="bold"),
                fld_oracle,
                ft.ElevatedButton(
                    "🔍  SEARCH AND CALCULATE",
                    bgcolor=C["green"], color="#FFFFFF",
                    height=52,
                    style=ft.ButtonStyle(text_style=ft.TextStyle(
                        size=17, weight="bold")),
                    on_click=do_oracle),
                ft.Divider(height=6, color=C["divider"]),
                result_box,
            ])

        # ══════════════════════════════════════════════════════════════════════
        # SCREEN 2 — STOCK LIST (View All)
        # ══════════════════════════════════════════════════════════════════════
        fld_list_search = make_field(
            "Search Symbol or Company Name",
            hint="Leave blank to show first 100 stocks")

        list_rows = ft.Column(
            controls=[],
            spacing=2)

        list_count_txt = ft.Text(
            "", size=14,
            color=C["primary"], weight="bold")

        def load_list(q=""):
            list_rows.controls.clear()
            rows = db_search(q) if q else db_search("")
            list_count_txt.value = (
                "Showing " + str(len(rows)) + " stocks"
                + (" matching '" + q + "'" if q else
                   " (first 100)"))

            for i, r in enumerate(rows):
                sym, eng, hi, ldt, asum = r
                bg = C["row_odd"] if i % 2 == 0 else C["row_even"]

                def make_edit_handler(s=sym):
                    def handler(e):
                        load_edit(s)
                    return handler

                row_ctrl = ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Container(
                                content=ft.Text(
                                    sym, size=15,
                                    color="#FFFFFF",
                                    weight="bold"),
                                bgcolor=C["primary"],
                                padding=ft.padding.symmetric(
                                    horizontal=10, vertical=4),
                                border_radius=4),
                            ft.Text(
                                ldt, size=12,
                                color=C["hint_txt"]),
                            ft.Text(
                                "Ak:" + str(asum),
                                size=12, color=C["accent"]),
                        ]),
                        ft.Text(
                            eng, size=14,
                            color=C["black_txt"],
                            weight="bold"),
                        ft.Text(
                            hi, size=15,
                            color=C["primary"],
                            weight="bold"),
                        ft.Row([
                            ft.TextButton(
                                "✏️ Edit",
                                style=ft.ButtonStyle(
                                    color=C["accent"]),
                                on_click=make_edit_handler(sym)),
                            ft.TextButton(
                                "🔮 Analyse",
                                style=ft.ButtonStyle(
                                    color=C["green"]),
                                on_click=lambda e, s=sym: (
                                    setattr(fld_oracle, 'value', s),
                                    show_screen("oracle"),
                                    do_oracle(e))),
                        ]),
                    ], spacing=2),
                    bgcolor=bg,
                    padding=8,
                    border_radius=6,
                    border=ft.Border(
                        bottom=ft.BorderSide(1, C["divider"])))
                list_rows.controls.append(row_ctrl)
            page.update()

        def do_list_search(e):
            load_list(fld_list_search.value.strip().upper())

        list_screen = ft.Column(
            visible=False,
            controls=[
                make_header("📋  STOCK LIST  (NSE India)"),
                ft.Divider(height=4, color=C["divider"]),
                fld_list_search,
                ft.Row([
                    ft.ElevatedButton(
                        "🔍 Search",
                        bgcolor=C["primary"], color="#FFFFFF",
                        height=46,
                        style=ft.ButtonStyle(
                            text_style=ft.TextStyle(
                                size=15, weight="bold")),
                        on_click=do_list_search),
                    ft.ElevatedButton(
                        "📋 Show All",
                        bgcolor=C["accent"], color="#FFFFFF",
                        height=46,
                        style=ft.ButtonStyle(
                            text_style=ft.TextStyle(
                                size=15, weight="bold")),
                        on_click=lambda e: load_list("")),
                ]),
                list_count_txt,
                ft.Divider(height=4, color=C["divider"]),
                list_rows,
            ])

        # ══════════════════════════════════════════════════════════════════════
        # SCREEN 3 — DATA ENTRY (Add / Edit / Delete)
        # ══════════════════════════════════════════════════════════════════════
        fld_sym   = make_field("Symbol *", "e.g. RELIANCE")
        fld_eng   = make_field("English Company Name *",
                               "e.g. Reliance Industries Ltd")
        fld_hindi = make_field("Hindi Name *",
                               "e.g. रिलायंस इंडस्ट्रीज")
        fld_ldate = make_field("Listing Date", "DD-MM-YYYY")
        fld_series = make_field("Series", "e.g. EQ", value="EQ")

        entry_status = ft.Text(
            "", size=15, color=C["green"], weight="bold")

        akshara_preview = ft.Container(
            content=ft.Text(
                "", size=14, color=C["dark_txt"]),
            bgcolor=C["res_bg"],
            padding=10, border_radius=6,
            visible=False)

        def load_edit(sym):
            row = db_get(sym)
            if row:
                fld_sym.value    = row[0]
                fld_sym.disabled = True
                fld_eng.value    = row[1]
                fld_hindi.value  = row[2]
                fld_ldate.value  = row[3]
                fld_series.value = row[6] if len(row) > 6 else "EQ"
                asum, bk         = calc(row[2])
                akshara_preview.content.value = (
                    "Akshara Sum = " + str(asum) + "\n" + bk[:80])
                akshara_preview.visible = True
                entry_status.value  = "Loaded: " + sym + " — Edit and tap UPDATE"
                entry_status.color  = C["accent"]
                show_screen("entry")
                page.update()

        def do_transliterate(e):
            eng = fld_eng.value.strip()
            sym = fld_sym.value.strip().upper()
            if not eng:
                entry_status.value = "Enter English name first."
                entry_status.color = C["red"]
                page.update()
                return
            entry_status.value = "Transliterating... please wait"
            entry_status.color = C["accent"]
            page.update()
            hi = get_hindi(sym, eng)
            fld_hindi.value = hi
            asum, bk        = calc(hi)
            akshara_preview.content.value = (
                "Akshara Sum = " + str(asum) + "\n" + bk[:80])
            akshara_preview.visible = True
            entry_status.value = "Hindi name generated!"
            entry_status.color = C["green"]
            page.update()

        def do_preview(e):
            hi = fld_hindi.value.strip()
            if not hi:
                entry_status.value = "Enter Hindi name first."
                entry_status.color = C["red"]
                page.update()
                return
            asum, bk = calc(hi)
            akshara_preview.content.value = (
                "Akshara Sum = " + str(asum) + "\n" + bk[:120])
            akshara_preview.visible = True
            entry_status.value = "Akshara = " + str(asum) + "  Navaank = " + str((asum%9) or 9)
            entry_status.color = C["primary"]
            page.update()

        def do_save(e):
            sym   = fld_sym.value.strip().upper()
            eng   = fld_eng.value.strip()
            hindi = fld_hindi.value.strip()
            ldate = fld_ldate.value.strip()
            series = fld_series.value.strip() or "EQ"
            if not sym or not eng or not hindi:
                entry_status.value = "Symbol, English and Hindi name are required!"
                entry_status.color = C["red"]
                page.update()
                return
            ok, val = db_save(sym, eng, hindi, ldate, series)
            if ok:
                entry_status.value = "Saved! " + sym + "  Akshara = " + str(val)
                entry_status.color = C["green"]
                fld_sym.disabled   = False
            else:
                entry_status.value = "Save failed: " + str(val)
                entry_status.color = C["red"]
            page.update()

        def do_update(e):
            sym   = fld_sym.value.strip().upper()
            eng   = fld_eng.value.strip()
            hindi = fld_hindi.value.strip()
            ldate = fld_ldate.value.strip()
            series = fld_series.value.strip() or "EQ"
            if not sym:
                entry_status.value = "No symbol loaded!"
                entry_status.color = C["red"]
                page.update()
                return
            ok, val = db_save(sym, eng, hindi, ldate, series)
            if ok:
                entry_status.value = "Updated! " + sym + "  Akshara = " + str(val)
                entry_status.color = C["green"]
                fld_sym.disabled   = False
            else:
                entry_status.value = "Update failed: " + str(val)
                entry_status.color = C["red"]
            page.update()

        def do_delete(e):
            sym = fld_sym.value.strip().upper()
            if not sym:
                entry_status.value = "No symbol loaded to delete!"
                entry_status.color = C["red"]
                page.update()
                return
            if db_delete(sym):
                entry_status.value = "Deleted: " + sym
                entry_status.color = C["orange"]
                do_clear(None)
            else:
                entry_status.value = "Delete failed!"
                entry_status.color = C["red"]
            page.update()

        def do_clear(e):
            fld_sym.value    = ""
            fld_eng.value    = ""
            fld_hindi.value  = ""
            fld_ldate.value  = ""
            fld_series.value = "EQ"
            fld_sym.disabled = False
            akshara_preview.visible = False
            entry_status.value = "Form cleared."
            entry_status.color = C["hint_txt"]
            page.update()

        entry_screen = ft.Column(
            visible=False,
            controls=[
                make_header("✏️  DATA ENTRY — Add / Edit Stock"),
                ft.Divider(height=4, color=C["divider"]),
                ft.Text(
                    "Fields marked * are required",
                    size=13, color=C["hint_txt"]),
                fld_sym,
                fld_eng,
                ft.ElevatedButton(
                    "🔄  Auto-Generate Hindi Name",
                    bgcolor=C["accent"], color="#FFFFFF",
                    height=46,
                    style=ft.ButtonStyle(
                        text_style=ft.TextStyle(
                            size=15, weight="bold")),
                    on_click=do_transliterate),
                fld_hindi,
                ft.ElevatedButton(
                    "👁  Preview Akshara Calculation",
                    bgcolor=C["secondary"], color="#FFFFFF",
                    height=46,
                    style=ft.ButtonStyle(
                        text_style=ft.TextStyle(
                            size=15, weight="bold")),
                    on_click=do_preview),
                akshara_preview,
                fld_ldate,
                fld_series,
                ft.Divider(height=6, color=C["divider"]),
                ft.Row([
                    ft.ElevatedButton(
                        "💾 SAVE NEW",
                        bgcolor=C["green"], color="#FFFFFF",
                        height=50,
                        style=ft.ButtonStyle(
                            text_style=ft.TextStyle(
                                size=15, weight="bold")),
                        on_click=do_save,
                        expand=True),
                    ft.ElevatedButton(
                        "📝 UPDATE",
                        bgcolor=C["accent"], color="#FFFFFF",
                        height=50,
                        style=ft.ButtonStyle(
                            text_style=ft.TextStyle(
                                size=15, weight="bold")),
                        on_click=do_update,
                        expand=True),
                ]),
                ft.Row([
                    ft.ElevatedButton(
                        "🗑 DELETE",
                        bgcolor=C["red"], color="#FFFFFF",
                        height=46,
                        style=ft.ButtonStyle(
                            text_style=ft.TextStyle(
                                size=14, weight="bold")),
                        on_click=do_delete,
                        expand=True),
                    ft.ElevatedButton(
                        "🧹 CLEAR",
                        bgcolor=C["hint_txt"], color="#FFFFFF",
                        height=46,
                        style=ft.ButtonStyle(
                            text_style=ft.TextStyle(
                                size=14, weight="bold")),
                        on_click=do_clear,
                        expand=True),
                ]),
                entry_status,
            ])

        # ══════════════════════════════════════════════════════════════════════
        # SCREEN 4 — DATABASE BUILD
        # ══════════════════════════════════════════════════════════════════════
        build_result = ft.Text(
            "", size=15,
            color=C["dark_txt"],
            selectable=True)

        def do_build(e):
            def worker():
                try:
                    set_status("Step 1/4: Connecting to NSE...", C["orange"])
                    set_prg(0.02, "Connecting to NSE India server...")
                    build_result.value = (
                        "BUILD STARTED\n\n"
                        "Connecting to NSE India...\n"
                        "Please keep app open.\n"
                        "Do not press back button.\n\n"
                        "Progress bar shows % complete.")
                    page.update()

                    hdrs = {"User-Agent": "Mozilla/5.0 (Android)"}
                    resp = requests.get(
                        NSE_URL, headers=hdrs, timeout=60)
                    resp.raise_for_status()

                    # Filter EQ series only like original code
                    all_rows = list(csv.DictReader(io.StringIO(
                        resp.content.decode("utf-8", errors="ignore"))))
                    rows = []
                    for r in all_rows:
                        nm = {k.strip().upper(): (v.strip() if v else "")
                              for k, v in r.items()}
                        series = nm.get("SERIES","").strip()
                        if series == "EQ" or not series:
                            rows.append(nm)

                    total = len(rows)
                    set_status("Step 2/4: Got " + str(total) + " EQ stocks!", C["orange"])
                    set_prg(0.10, "Downloaded " + str(total) + " EQ series stocks...")
                    build_result.value = (
                        "BUILD IN PROGRESS\n\n"
                        "Downloaded: " + str(total) + " EQ stocks\n\n"
                        "Translating to Hindi...\n"
                        "Calculating Akshara values...\n\n"
                        "Progress bar filling above.\n"
                        "Takes 5-15 minutes.\n"
                        "Please wait...")
                    page.update()

                    conn2 = sqlite3.connect(db_path)
                    cur   = conn2.cursor()
                    done  = 0

                    for i, nm in enumerate(rows):
                        sym = nm.get("SYMBOL","").strip()
                        eng = nm.get("NAME OF COMPANY",
                              nm.get("COMPANY NAME","")).strip()
                        ldt = nm.get("DATE OF LISTING",
                                     "01-01-2000").strip()
                        ser = nm.get("SERIES","EQ").strip()
                        if not sym or sym.lower() == "symbol":
                            continue
                        hi       = get_hindi(sym, eng)
                        asum, bk = calc(hi)
                        cur.execute(
                            "INSERT OR REPLACE INTO stocks "
                            "VALUES(?,?,?,?,?,?,?)",
                            (sym, eng, hi, ldt, asum, bk, ser))
                        done += 1
                        if i % 25 == 0:
                            conn2.commit()
                            pct = 0.10 + (i / max(total, 1)) * 0.90
                            set_status(
                                "Processing " + str(i) + "/" + str(total)
                                + " — " + sym, C["orange"])
                            set_prg(pct,
                                str(int(pct*100)) + "% done — " + sym)

                    conn2.commit()
                    conn2.close()
                    set_prg(1.0, "Complete! " + str(done) + " stocks ready!")
                    set_status("Ready! " + str(done) + " EQ stocks.", C["green"])
                    build_result.value = (
                        "BUILD COMPLETE!\n\n"
                        "EQ stocks processed: " + str(done) + "\n\n"
                        "Go to STOCK LIST tab to view.\n"
                        "Go to ORACLE tab to analyse.\n\n"
                        "Search examples:\n"
                        "  RELIANCE\n  TCS\n  SBIN\n  INFY")
                    page.update()

                except Exception as ex:
                    hide_prg()
                    set_status("Build failed! Check internet.", C["red"])
                    build_result.value = (
                        "BUILD FAILED\n\n"
                        "Error: " + str(ex) + "\n\n"
                        "Check internet and try again.")
                    page.update()

            set_status("Starting build...", C["orange"])
            build_result.value = (
                "PREPARING BUILD...\n\n"
                "Connecting to NSE India.\n"
                "Please wait...")
            page.update()
            threading.Thread(target=worker, daemon=True).start()

        build_screen = ft.Column(
            visible=False,
            controls=[
                make_header("🔄  DATABASE — Build & Manage"),
                ft.Divider(height=4, color=C["divider"]),
                ft.Container(
                    content=ft.Text(
                        "Downloads all NSE EQ series stocks\n"
                        "with Hindi names into local database.\n"
                        "Needs internet. Takes 5-15 minutes.",
                        size=14, color=C["dark_txt"]),
                    bgcolor=C["res_bg"],
                    padding=10, border_radius=6),
                ft.Divider(height=4, color=C["divider"]),
                ft.ElevatedButton(
                    "🔄  BUILD DATABASE  (first time)",
                    bgcolor=C["orange"], color="#FFFFFF",
                    height=54,
                    style=ft.ButtonStyle(
                        text_style=ft.TextStyle(
                            size=17, weight="bold")),
                    on_click=do_build),
                ft.Divider(height=6, color=C["divider"]),
                build_result,
            ])

        # ══════════════════════════════════════════════════════════════════════
        # NAVIGATION
        # ══════════════════════════════════════════════════════════════════════
        # ══════════════════════════════════════════════════════════════════════
        # SCREEN 5 — HELP / THEORY REFERENCE
        # ══════════════════════════════════════════════════════════════════════
        HELP_TEXT = """
╔══════════════════════════════╗
   BHOOVALAYA ORACLE — THEORY
   COMPLETE REFERENCE GUIDE
╚══════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
THEORY 1: BHOOVALAYA AKSHARA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ancient Jain text by Sage
Kumudendu (9th century AD).
Assigns weight to each Sanskrit
Devanagari sound (Akshara):

  अ=1  आ=2  इ=3  ई=4  उ=5
  ऊ=6  ए=7  ऐ=8  ओ=9  औ=10
  क=11 ख=12 ग=13 घ=14 ङ=15
  च=16 छ=17 ज=18 झ=19 ञ=20
  ट=21 ठ=22 ड=23 ढ=24 ण=25
  त=26 थ=27 द=28 ध=29 न=30
  प=31 फ=32 ब=33 भ=34 म=35
  य=36 र=37 ल=38 व=39 श=40
  ष=41 स=42 ह=43
  ि=2  ा=2  े=7  ै=8
  ो=9  ौ=10 ्=0  ं=1

Example — रिलायंस:
  र=37 ि=2 ल=38 ा=2 य=36
  ं=1 स=42
  Sum = 37+2+38+2+36+1+42 = 158

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
THEORY 2: NAVAANK (DIGITAL ROOT)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Vedic Numerology — reduce any
number to single digit 1 to 9:

  158 → 1+5+8 = 14
  14  → 1+4   = 5  ← Navaank

Navaank → Ruling Planet:
  1 = सूर्य  (Sun)
  2 = चंद्र  (Moon)
  3 = गुरु   (Jupiter)
  4 = राहु   (Rahu)
  5 = बुध    (Mercury)
  6 = शुक्र  (Venus)
  7 = केतु   (Ketu)
  8 = शनि    (Saturn)
  9 = मंगल   (Mars)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
THEORY 3: TEMPORAL VIBRATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
730 = Two Jupiter cycles
     (each cycle = 365 days)

  Formula: Days since listing
           on NSE % 730

  Captures stock's current
  position in its life cycle.

Example — RELIANCE:
  Listed: 29-11-1995
  Days elapsed: ~10,000+
  10000 % 730 = 260 (Temporal)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
THEORY 4: COMBINED VIBRATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Combined = Akshara + Temporal
  Sutra    = Combined % 9

9 Sutras (Cosmic Principles):
  0 = अनंत   (Infinite/Eternal)
  1 = शक्ति  (Power/Energy)
  2 = ज्ञान  (Knowledge/Wisdom)
  3 = धर्म   (Righteousness)
  4 = वैराग्य (Detachment)
  5 = ऐश्वर्य (Prosperity)
  6 = यश     (Fame/Glory)
  7 = श्री   (Wealth)
  8 = वीर्य  (Strength/Vigor)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
THEORY 5: GRAHA MARKET MAPPING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Vedic Financial Astrology maps
each planet to market behavior:

  Sun     → BULLISH (5/5)
    PSU · Govt · Energy · Gold
    Hold: 1-4 Weeks
    Best: Sunday

  Moon    → VOLATILE (2/5)
    FMCG · Dairy · Retail
    Hold: 1-3 Days
    Best: Monday

  Jupiter → STRONGLY BULLISH (5/5)
    Banking · Education
    Hold: 1-6 Months
    Best: Thursday

  Rahu    → SPECULATIVE (3/5)
    Tech · Pharma · Foreign
    Hold: With Caution
    Best: Saturday

  Mercury → BULLISH (4/5)
    IT · Telecom · Media
    Hold: 1-3 Weeks
    Best: Wednesday

  Venus   → BULLISH (4/5)
    FMCG · Luxury · Hotels
    Hold: 2-8 Weeks
    Best: Friday

  Ketu    → BEARISH (2/5)
    Old Economy · Exit Zone
    Hold: Avoid Entry
    Best: Tuesday (exit only)

  Saturn  → SLOW BULLISH (3/5)
    Infra · Metals · Coal
    Hold: 3-12 Months
    Best: Saturday

  Mars    → BULLISH (4/5)
    Metals · Defence · Energy
    Hold: 1-7 Days
    Best: Tuesday

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
THEORY 6: TARA BALA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
From Vedic Panchanga system.
Counts Nakshatras from stock
listing date to today:

  Count % 9 = Tara type:
  1=जन्म      2=सम्पत ✅GOOD
  3=विपत      4=क्षेम ✅GOOD
  5=प्रत्यरि  6=साधक ✅GOOD
  7=वध        8=मित्र ✅GOOD
  0=परम-मित्र ✅GOOD

  Even numbers = GOOD entry
  Odd numbers  = Be cautious

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
THEORY 7: NAKSHATRA TIMING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
27 Nakshatras = 1 lunar cycle

  Today Nakshatra =
  Day of Year % 27

  27 Nakshatras:
  अश्विनी भरणी कृत्तिका
  रोहिणी मृगशिरा आर्द्रा
  पुनर्वसु पुष्य आश्लेषा
  मघा पूर्वाफाल्गुनी
  उत्तराफाल्गुनी हस्त
  चित्रा स्वाति विशाखा
  अनुराधा ज्येष्ठा मूल
  पूर्वाषाढ़ा उत्तराषाढ़ा
  श्रवण धनिष्ठा शतभिषा
  पूर्वाभाद्रपद
  उत्तराभाद्रपद रेवती

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPLETE ORACLE FLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Company Name (English)
         ↓
  Hindi Transliteration
         ↓
  Akshara Sum (Theory 1)
         ↓
  Navaank / Digital Root
         (Theory 2)
         ↓
  Ruling Planet (Graha)
         ↓
  Market Bias + Sectors
  + Holding Period (Theory 5)
         +
  Temporal Vibration
  Days % 730 (Theory 3)
         ↓
  Sutra Principle (Theory 4)
         +
  Tara Bala (Theory 6)
         +
  Today Nakshatra (Theory 7)
         ↓
  ══════════════════════════
   FINAL ORACLE FORECAST
  ══════════════════════════

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IMPORTANT DISCLAIMER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This app is for study and
research purposes only.

This is NOT SEBI registered
investment advice.

Always consult a qualified
financial advisor before
making any investment.

Past performance does not
guarantee future results.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        help_screen = ft.Column(
            visible=False,
            controls=[
                make_header("❓  HELP — Theory & Reference", C["primary"]),
                ft.Divider(height=4, color=C["divider"]),
                ft.Container(
                    content=ft.Text(
                        HELP_TEXT,
                        size=14,
                        color=C["dark_txt"],
                        selectable=True,
                        font_family="monospace",
                    ),
                    bgcolor=C["res_bg"],
                    padding=14,
                    border_radius=8,
                    border=ft.Border(
                        top=ft.BorderSide(2, C["primary"]),
                        bottom=ft.BorderSide(2, C["primary"]),
                        left=ft.BorderSide(2, C["primary"]),
                        right=ft.BorderSide(2, C["primary"]),
                    ),
                ),
            ])


        # ══════════════════════════════════════════════════════════════════════
        # SCREEN 6 — ASTRO (D1 + D9 CHART)
        # ══════════════════════════════════════════════════════════════════════
        today_dt = datetime.now()

        fld_date = make_field(
            "Date (DD-MM-YYYY)",
            hint="e.g. 09-07-2026",
            value=today_dt.strftime("%d-%m-%Y"))

        fld_time = make_field(
            "Time (HH:MM) 24-hour",
            hint="e.g. 14:30",
            value=today_dt.strftime("%H:%M"))

        fld_lat = make_field(
            "Latitude (N+  S-)",
            hint="Mumbai = 19.076",
            value="19.076")

        fld_lon = make_field(
            "Longitude (E+  W-)",
            hint="Mumbai = 72.877",
            value="72.877")

        fld_place = make_field(
            "Place Name",
            hint="e.g. Mumbai, India",
            value="Mumbai, India")

        astro_result   = ft.Text(
            "", size=14, color=C["dark_txt"],
            selectable=True, font_family="monospace")

        astro_result_box = ft.Container(
            content=astro_result,
            bgcolor=C["res_bg"], padding=10,
            border_radius=6, visible=False,
            border=ft.Border(
                top=ft.BorderSide(2, C["primary"]),
                bottom=ft.BorderSide(2, C["primary"]),
                left=ft.BorderSide(2, C["primary"]),
                right=ft.BorderSide(2, C["primary"]),
            ))

        d1_grid_col  = ft.Column(controls=[], visible=False)
        d9_grid_col  = ft.Column(controls=[], visible=False)

        # North Indian Chart: Houses are FIXED, signs ROTATE based on Lagna
        # Grid positions for each house number:
        #  H12 | H1  | H2  | H3
        #  H11 | [C] | [C] | H4
        #  H10 | [C] | [C] | H5
        #   H9 | H8  | H7  | H6
        NI_HOUSE_POS = {
            12:(0,0), 1:(0,1),  2:(0,2),  3:(0,3),
            11:(1,0),                      4:(1,3),
            10:(2,0),                      5:(2,3),
             9:(3,0), 8:(3,1),  7:(3,2),  6:(3,3),
        }

        def house_sign(lagna_sign, house_num):
            """Get sign index for given house in North Indian chart."""
            return (lagna_sign + house_num - 1) % 12

        def make_ni_cell(house_num, sign_idx, planets,
                         is_lagna=False, cell_w=82, cell_h=72):
            """Create one North Indian chart cell."""
            bg        = "#FFE0E0" if is_lagna else C["inp_bg"]
            bdr_col   = "#D32F2F" if is_lagna else C["primary"]
            txt_col   = "#D32F2F" if is_lagna else C["primary"]
            ctrls = []
            # House number small
            ctrls.append(ft.Text(
                str(house_num),
                size=9, color=C["hint_txt"]))
            # Sign name
            ctrls.append(ft.Text(
                SIGN_ABB[sign_idx],
                size=12, color=txt_col, weight="bold"))
            # Hindi sign
            ctrls.append(ft.Text(
                SIGN_HI[sign_idx],
                size=11, color=txt_col))
            # Planets
            if planets:
                ctrls.append(ft.Text(
                    " ".join(planets),
                    size=12, color="#B71C1C", weight="bold"))
            return ft.Container(
                content=ft.Column(
                    controls=ctrls,
                    spacing=0,
                    horizontal_alignment="center"),
                width=cell_w, height=cell_h,
                bgcolor=bg,
                border=ft.Border(
                    top=ft.BorderSide(1, bdr_col),
                    bottom=ft.BorderSide(1, bdr_col),
                    left=ft.BorderSide(1, bdr_col),
                    right=ft.BorderSide(1, bdr_col)),
                padding=3,
                alignment=ft.alignment.center)

        def make_ni_center(line1, line2,
                           cell_w=82, cell_h=72):
            """Create center decorative cell."""
            return ft.Container(
                content=ft.Column([
                    ft.Text(line1, size=11,
                            color=C["primary"],
                            weight="bold",
                            text_align="center"),
                    ft.Text(line2, size=10,
                            color=C["accent"],
                            text_align="center"),
                ], spacing=2,
                horizontal_alignment="center"),
                width=cell_w, height=cell_h,
                bgcolor="#EEF4FF",
                border=ft.Border(
                    top=ft.BorderSide(1, C["divider"]),
                    bottom=ft.BorderSide(1, C["divider"]),
                    left=ft.BorderSide(1, C["divider"]),
                    right=ft.BorderSide(1, C["divider"])),
                padding=4,
                alignment=ft.alignment.center)

        def render_chart(grid_col, positions, title):
            """
            Render North Indian Vedic chart.
            positions = {planet_abbr: sign_index_0to11}
            Lagna sign is taken from positions["As"]
            """
            grid_col.controls.clear()

            # Title header
            grid_col.controls.append(ft.Container(
                content=ft.Text(
                    title, size=15,
                    color="#FFFFFF", weight="bold",
                    text_align="center"),
                bgcolor=C["primary"],
                padding=8, border_radius=6,
                alignment=ft.alignment.center))

            lagna_sign = int(positions.get("As", 0))

            # Map sign_index -> planets list
            sign_planets = {i: [] for i in range(12)}
            for planet, s_idx in positions.items():
                sign_planets[int(s_idx)].append(planet)

            # Build 4x4 grid row by row
            # Row 0: H12 H1 H2 H3
            # Row 1: H11 C  C  H4
            # Row 2: H10 C  C  H5
            # Row 3: H9  H8 H7 H6
            rows_def = [
                [12, 1,  2,  3 ],
                [11, -1, -1, 4 ],
                [10, -1, -1, 5 ],
                [9,  8,  7,  6 ],
            ]
            center_labels = [
                ("NORTH", "INDIAN"),
                ("VEDIC", "CHART"),
                (title[:6], ""),
                ("D1/D9", "CHART"),
            ]
            center_count = [0]

            for row_def in rows_def:
                row_ctrls = []
                for house_num in row_def:
                    if house_num == -1:
                        # Center cell
                        lbl = center_labels[center_count[0] % 4]
                        center_count[0] += 1
                        row_ctrls.append(
                            make_ni_center(lbl[0], lbl[1]))
                    else:
                        s_idx     = house_sign(lagna_sign, house_num)
                        planets_h = sign_planets.get(s_idx, [])
                        is_lgn    = (house_num == 1)
                        row_ctrls.append(make_ni_cell(
                            house_num, s_idx,
                            planets_h, is_lgn))
                grid_col.controls.append(
                    ft.Row(controls=row_ctrls, spacing=0))

            # Legend
            grid_col.controls.append(ft.Container(
                content=ft.Text(
                    "H1(Red)=Lagna  As=Ascendant  Ra=Rahu  Ke=Ketu",
                    size=11, color=C["hint_txt"],
                    text_align="center"),
                padding=4))

            grid_col.visible = True

        def do_calc_astro(e):
            try:
                set_status("Calculating chart...", C["accent"])

                # Parse date
                date_str = fld_date.value.strip()
                time_str = fld_time.value.strip()
                lat  = float(fld_lat.value.strip())
                lon2 = float(fld_lon.value.strip())

                try:
                    dt = datetime.strptime(
                        date_str + " " + time_str, "%d-%m-%Y %H:%M")
                except Exception:
                    try:
                        dt = datetime.strptime(
                            date_str + " " + time_str, "%Y-%m-%d %H:%M")
                    except Exception:
                        set_status("Date format error! Use DD-MM-YYYY", C["red"])
                        return

                # IST = UTC+5:30
                hour_utc = dt.hour - 5
                min_utc  = dt.minute - 30
                if min_utc < 0:
                    min_utc += 60
                    hour_utc -= 1
                if hour_utc < 0:
                    hour_utc += 24

                jd = jd_from_dt(dt.year, dt.month, dt.day,
                                 hour_utc, min_utc)

                sid, ay = calc_planet_positions(jd, lat, lon2)

                # Build planet table
                planet_lines = []
                planet_lines.append("═" * 36)
                planet_lines.append("PLANET POSITIONS (Sidereal/Lahiri)")
                planet_lines.append("Date : " + date_str + "  " + time_str + " IST")
                planet_lines.append("Place: " + fld_place.value.strip())
                planet_lines.append("Lat  : " + str(lat) + "  Lon: " + str(lon2))
                planet_lines.append("Ayanamsa (Lahiri): " + str(round(ay, 4)) + "°")
                planet_lines.append("─" * 36)
                planet_lines.append(
                    f"{'Planet':<10} {'Sign':<8} {'HiSign':<8} {'Deg':>6}")
                planet_lines.append("─" * 36)

                d1_positions = {}
                d9_positions = {}

                order = ["As","Su","Mo","Me","Ve","Ma","Ju","Sa","Ra","Ke"]
                for p in order:
                    lon_p  = sid[p]
                    s_idx, deg = lon_to_sign_deg(lon_p)
                    d9_idx = d9_sign(lon_p)
                    d1_positions[p] = s_idx
                    d9_positions[p] = d9_idx
                    planet_lines.append(
                        f"{PLANET_NAMES.get(p,p):<10} "
                        f"{SIGN_ABB[s_idx]:<8} "
                        f"{SIGN_HI[s_idx]:<8} "
                        f"{deg:>5.1f}°")

                planet_lines.append("═" * 36)
                planet_lines.append("As = Lagna (Ascendant)")
                planet_lines.append("Ra = Rahu  Ke = Ketu")
                planet_lines.append("Lahiri Ayanamsa applied")
                planet_lines.append("Location default = Mumbai IST")
                planet_lines.append("═" * 36)

                astro_result.value = "\n".join(planet_lines)
                astro_result_box.visible = True

                # Render D1
                render_chart(d1_grid_col, d1_positions, "D1 RASI CHART")
                # Render D9
                render_chart(d9_grid_col, d9_positions, "D9 NAVAMSA")

                set_status("Charts calculated!", C["green"])
                page.update()

            except Exception as ex:
                set_status("Calc error: " + str(ex), C["red"])
                astro_result.value = "ERROR: " + str(ex)
                astro_result_box.visible = True
                page.update()

        astro_screen = ft.Column(
            visible=False,
            controls=[
                make_header("🪐  VEDIC ASTRO CHART — D1 & D9",
                            C["primary"]),
                ft.Divider(height=4, color=C["divider"]),
                ft.Container(
                    content=ft.Column([
                        ft.Text(
                            "📍 Default: Mumbai, India",
                            size=14, color=C["dark_txt"],
                            weight="bold"),
                        ft.Text(
                            "Lat 19.076°N  Lon 72.877°E",
                            size=13, color=C["dark_txt"]),
                        ft.Text(
                            "⏰ Time in IST (India Standard Time UTC+5:30)",
                            size=12, color=C["hint_txt"]),
                    ], spacing=2),
                    bgcolor=C["res_bg"],
                    padding=10, border_radius=6),
                ft.Divider(height=4, color=C["divider"]),

                # ── INPUT FIELDS ───────────────────────────────────────────
                ft.Text("Date & Time:", size=14,
                        color=C["primary"], weight="bold"),
                ft.Row([
                    ft.Column([fld_date], expand=True),
                    ft.Column([fld_time], expand=True),
                ], spacing=6),

                ft.Text("Location:", size=14,
                        color=C["primary"], weight="bold"),
                fld_place,
                ft.Row([
                    ft.Column([fld_lat], expand=True),
                    ft.Column([fld_lon], expand=True),
                ], spacing=6),

                ft.Divider(height=6, color=C["divider"]),

                ft.ElevatedButton(
                    "🪐  CALCULATE D1 & D9 CHARTS",
                    bgcolor=C["primary"], color="#FFFFFF",
                    height=56,
                    style=ft.ButtonStyle(
                        text_style=ft.TextStyle(
                            size=17, weight="bold")),
                    on_click=do_calc_astro),

                ft.Divider(height=8, color=C["divider"]),

                # ── PLANET TABLE ───────────────────────────────────────────
                astro_result_box,

                ft.Divider(height=10, color=C["divider"]),

                # ── D1 CHART ───────────────────────────────────────────────
                ft.Container(
                    content=ft.Text(
                        "━━  D1 RASI CHART (जन्म कुंडली)  ━━",
                        size=15, color=C["primary"],
                        weight="bold",
                        text_align="center"),
                    padding=6),
                ft.Container(
                    content=ft.Text(
                        "Shows actual planetary positions at birth/query time.",
                        size=12, color=C["hint_txt"]),
                    padding=ft.padding.only(bottom=4)),
                d1_grid_col,

                ft.Divider(height=14, color=C["divider"]),

                # ── D9 CHART ───────────────────────────────────────────────
                ft.Container(
                    content=ft.Text(
                        "━━  D9 NAVAMSA CHART (नवांश कुंडली)  ━━",
                        size=15, color=C["primary"],
                        weight="bold",
                        text_align="center"),
                    padding=6),
                ft.Container(
                    content=ft.Text(
                        "Each sign divided into 9 parts of 3°20'. "
                        "Shows spouse, dharma & soul purpose.",
                        size=12, color=C["hint_txt"]),
                    padding=ft.padding.only(bottom=4)),
                d9_grid_col,

                ft.Divider(height=10, color=C["divider"]),
                ft.Container(
                    content=ft.Text(
                        "Calculations use Lahiri Ayanamsa (Sidereal). Accuracy +/-1-2 deg. For research only.",
                        size=12, color=C["hint_txt"],
                        text_align="center"),
                    bgcolor=C["res_bg"],
                    padding=8, border_radius=6),
            ])

        screens = {
            "oracle": oracle_screen,
            "list":   list_screen,
            "entry":  entry_screen,
            "build":  build_screen,
            "help":   help_screen,
            "astro":  astro_screen,
        }

        nav_buttons = {}

        def show_screen(name):
            for k, s in screens.items():
                s.visible = (k == name)
            for k, b in nav_buttons.items():
                b.bgcolor = C["primary"] if k == name else "#BDBDBD"
                b.color   = "#FFFFFF"
            if name == "list" and db_count() > 0:
                load_list("")
            page.update()

        def make_nav(label, name):
            btn = ft.ElevatedButton(
                text=label,
                bgcolor="#BDBDBD",
                color="#FFFFFF",
                height=46,
                expand=True,
                style=ft.ButtonStyle(
                    text_style=ft.TextStyle(
                        size=13, weight="bold")),
                on_click=lambda e, n=name: show_screen(n))
            nav_buttons[name] = btn
            return btn

        nav_bar = ft.Row([
            make_nav("🔮\nOracle", "oracle"),
            make_nav("📋\nStocks", "list"),
            make_nav("✏️\nEntry",  "entry"),
            make_nav("🔄\nBuild",  "build"),
            make_nav("🪐\nAstro",  "astro"),
            make_nav("❓\nHelp",   "help"),
        ], spacing=2)

        # ── BUILD PAGE ─────────────────────────────────────────────────────────
        def do_quit(e):
            page.window_close()

        page.add(ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text(
                        "🔮 BHOOVALAYA STOCK ORACLE",
                        size=18, color="#FFFFFF",
                        weight="bold"),
                    ft.Text(
                        "Vedic Akshara + Financial Astrology",
                        size=11, color="#BBDEFB"),
                ], expand=True, spacing=2),
                ft.ElevatedButton(
                    "✕ QUIT",
                    bgcolor="#B71C1C",
                    color="#FFFFFF",
                    height=40,
                    style=ft.ButtonStyle(
                        text_style=ft.TextStyle(
                            size=13, weight="bold")),
                    on_click=do_quit),
            ], alignment="spaceBetween"),
            bgcolor=C["primary"],
            padding=12, border_radius=0))

        page.add(status_bar)
        page.add(prg_bar)
        page.add(prg_txt)
        page.add(ft.Divider(height=2, color=C["divider"]))
        page.add(nav_bar)
        page.add(ft.Divider(height=4, color=C["divider"]))
        page.add(oracle_screen)
        page.add(list_screen)
        page.add(entry_screen)
        page.add(build_screen)
        page.add(astro_screen)
        page.add(help_screen)
        page.update()

        # Set oracle as default active tab
        show_screen("oracle")

        # ── STARTUP MESSAGE ────────────────────────────────────────────────────
        n = db_count()
        if n < 5:
            set_status("No database. Go to Build tab.", C["red"])
            result_txt.value = (
                "WELCOME!\n\n"
                "App is working correctly.\n\n"
                "SETUP STEPS:\n"
                "1. Tap BUILD tab below\n"
                "2. Tap BUILD DATABASE button\n"
                "3. Wait 5-15 minutes\n"
                "4. Come back to ORACLE tab\n"
                "5. Search any NSE symbol\n\n"
                "Or tap ENTRY tab to add\n"
                "stocks manually one by one.")
            result_box.visible = True
            page.update()
        else:
            set_status("Ready — " + str(n) + " stocks loaded.", C["green"])
            result_txt.value = (
                "WELCOME BACK!\n\n"
                + str(n) + " stocks in database.\n\n"
                "Type symbol and tap SEARCH.\n\n"
                "Examples:\n"
                "  RELIANCE  TCS  SBIN\n"
                "  INFY  WIPRO  ITC  LT")
            result_box.visible = True
            page.update()

    except Exception as err:
        try:
            page.controls.clear()
            page.add(ft.Container(
                content=ft.Text(
                    "STARTUP ERROR:\n" + str(err),
                    size=15, color="#FFFFFF",
                    selectable=True),
                bgcolor=C["red"],
                padding=16, border_radius=8))
            page.update()
        except: pass


ft.app(target=main)
