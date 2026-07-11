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

try:
    import flet.canvas as cv
    CANVAS_OK = True
except Exception:
    CANVAS_OK = False

import flet as ft

# ── AKSHARA CONSTANTS ──────────────────────────────────────────────────────────
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
    "RELIANCE":"रिलायंस कुंजी","TCS":"टाटा कंसल्टेंसी सर्विसेज",
    "INFY":"इन्फोसिस","WIPRO":"विप्रो",
    "NTPC":"राष्ट्रीय ताप विद्युत निगम",
    "ONGC":"तेल और प्राकृतिक गैस निगम",
    "TATASTEEL":"टाटा स्टील","COALINDIA":"कोल इंडिया",
    "HINDUNILVR":"हिंदुस्तान यूनिलीवर","ITC":"आईटीसी",
    "LT":"लार्क एंड टुब्रो","MARUTI":"मारुति सुजुकी",
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
    "HEROMOTOCO":"हीरो मोटोकॉर्प","HINDPETRO":"हिंदुस्तान पेट्रोलियम","VEDL":"वेदांता",
    "HINDALCO":"हिंडाल्को इंडस्ट्रीज","SAIL":"स्टील अथॉरिटी ऑफ इंडिया",
    "BRITANNIA":"ब्रिटानिया इंडस्ट्रीज","DABUR":"डाबर इंडिया",
    "MARICO":"मेरिको","NESTLEIND":"नेस्ले इंडिया",
    "TATAPOWER":"टाटा पावर","ADANIENT":"अदानी एंटरप्राइजेज",
    "DLF":"डीएलएफ","APOLLOHOSP":"अपोलो हॉस्पिटल्स",
}
WD = {
    "LIMITED":"लिमिटेड","LTD":"लिमिटेड","BANK":"बैंक",
    "INDUSTRIES":"इंडस्ट्रीज","INDUSTRY":"उद्योग",
    "INDIA":"इंडिया","INDIAN":"इंडियन","POWER":"पावर",
    "ENERGY":"एनर्जी","FINANCE":"फाइनेंस","STEEL":"स्टील",
    "MOTORS":"मोटर्स","MOTOR":"मोटर",
    "TECHNOLOGIES":"टेक्नोलॉजीज","SERVICES":"सर्विसेज",
    "AND":"एंड","&":"एंड","PHARMA":"फार्मा",
    "CEMENT":"सीमेंट","OIL":"ऑयल","GAS":"गैस",
    "TELECOM":"टेलीकॉम","GROUP":"ग्रुप",
    "CHEMICALS":"केमिकल्स","NATIONAL":"नेशनल",
    "CORPORATION":"कॉर्पोरेशन","MEDIA":"मीडिया",
    "HEALTHCARE":"हेल्थकेयर","CAPITAL":"कैपिटल",
    "AUTO":"ऑटो","ELECTRONICS":"इलेक्ट्रॉनिक्स",
    "CONSTRUCTION":"कंस्ट्रक्शन","PETROLEUM":"पेट्रोलियम",
    "ENTERPRISES":"एंटरप्राइजेज","INSURANCE":"इंश्योरेंस",
    "REALTY":"रियल्टी","SOLAR":"सोलर","GLOBAL":"ग्लोबल",
    "FOODS":"फूड्स","TEXTILE":"टेक्सटाइल","COMPANY":"कंपनी",
}
PR = {
    'A':'ए','B':'ब','C':'क','D':'ड','E':'इ','F':'फ',
    'G':'ग','H':'ह','I':'इ','J':'ज','K':'क','L':'ल',
    'M':'म','N':'न','O':'ओ','P':'प','Q':'क','R':'र',
    'S':'स','T':'ट','U':'य','V':'व','W':'व','X':'क्स',
    'Y':'य','Z':'ज'
}
NSE_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"

# ── ASTROLOGY CONSTANTS ────────────────────────────────────────────────────────
SIGN_ABB  = ["Ar","Ta","Ge","Ca","Le","Vi",
             "Li","Sc","Sg","Cp","Aq","Pi"]
SIGN_HI   = ["मेष","वृष","मिथुन","कर्क","सिंह","कन्या",
             "तुला","वृश्चिक","धनु","मकर","कुंभ","मीन"]
PLANET_NAMES = {
    "As":"Lag","Su":"Su","Mo":"Mo","Ma":"Ma","Me":"Me",
    "Ju":"Ju","Ve":"Ve","Sa":"Sa","Ra":"Ra","Ke":"Ke"
}

# ── COLOR PALETTE ──────────────────────────────────────────────────────────────
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
            out.append(WD.get(cw,"".join(PR.get(c,"") for c in cw)))
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

def navaank_steps(n):
    steps = []
    current = n
    while current > 9:
        digits = [int(d) for d in str(current)]
        steps.append(str(current) + "=" + "+".join(str(d) for d in digits))
        current = sum(digits)
    if steps:
        return " → ".join(steps) + " → " + str(current)
    return str(current)

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
        S2,"    BHOOVALAYA ORACLE RESULT",S2,
        "STEP 1: AKSHARA WEIGHT (Siribhoovalaya)",
        "  अ=1 आ=2 इ=3 क=11 र=37 स=42...",
        S,
        "STEP 2: NAVAANK (Vedic Digital Root)",
        "  Akshara Sum = " + str(asum),
        "  " + navaank_steps(asum) + "  → Navaank=" + str(nv),
        S,
        "STEP 3: TEMPORAL (Jupiter Cycle 730d)",
        "  Days elapsed → Mod 730 = " + str(tval),
        "  Combined = "+str(asum)+"+"+str(tval)+"="+str(total),
        "  Sutra = "+str(total)+"÷9 rem="+str(total%9),
        S,
        "STEP 4: SUTRA PRINCIPLE",
        "  " + sutra,
        S,
        "STEP 5: RULING GRAHA",
        "  Navaank " + str(nv) + " → " + g[0],
        S2,
        "  MARKET FORECAST",S2,
        "  Signal   : " + g[1],
        "  Strength : " + bars.get(g[2],"") + " " + str(g[2]) + "/5",
        "  Sectors  : " + g[3],
        "  Hold For : " + g[4],
        "  Caution  : " + g[5],
        "  Best Day : " + g[6],
        S,
        "STEP 6: VEDIC TIMING",
        "  "+wday+" "+today.strftime("%d-%m-%Y"),
        "  Nakshatra: " + nak,
        "  Tara Bala: " + tara,
        S2,"Research only. Not SEBI advice.",S2,
    ])

# ── ASTROLOGY CALCULATIONS ─────────────────────────────────────────────────────
def norm360(x): return x % 360

def jd_from_dt(year, month, day, hour=12, minute=0):
    if month <= 2:
        year -= 1; month += 12
    A = int(year/100); B = 2 - A + int(A/4)
    return (int(365.25*(year+4716)) + int(30.6001*(month+1))
            + day + hour/24.0 + minute/1440.0 + B - 1524.5)

def lahiri_ayanamsa(jd):
    T = (jd - 2451545.0) / 36525.0
    return 23.85 + 0.013611*T + 0.000092*T*T

def calc_planet_positions(jd, lat=19.076, lon=72.877):
    T = (jd - 2451545.0) / 36525.0
    L0   = norm360(280.46646 + 36000.76983*T)
    M_su = math.radians(norm360(357.52911 + 35999.05029*T))
    C_su = ((1.914602-0.004817*T)*math.sin(M_su)
            + 0.019993*math.sin(2*M_su) + 0.000289*math.sin(3*M_su))
    sun_t = norm360(L0 + C_su)
    L_mo  = norm360(218.3164477 + 481267.88123421*T)
    D_mo  = math.radians(norm360(297.8501921 + 445267.1114034*T))
    M_mo  = math.radians(norm360(134.9633964 + 477198.8675055*T))
    M_su2 = math.radians(norm360(357.5291092 + 35999.0502909*T))
    moon_t = norm360(L_mo + 6.289*math.sin(M_mo) - 1.274*math.sin(2*D_mo-M_mo)
                     + 0.658*math.sin(2*D_mo) - 0.214*math.sin(2*M_mo)
                     - 0.186*math.sin(M_su2))
    L_me = norm360(252.2509+149474.0722*T)
    M_me = math.radians(norm360(168.6562+149472.5153*T))
    merc_t = norm360(L_me+23.440*math.sin(M_me)+2.912*math.sin(2*M_me)+0.513*math.sin(3*M_me))
    L_ve = norm360(181.9798+58517.8160*T)
    M_ve = math.radians(norm360(212.9346+58517.8039*T))
    ven_t = norm360(L_ve+47.682*math.sin(M_ve)+1.319*math.sin(2*M_ve))
    L_ma = norm360(355.433+19140.2993*T)
    M_ma = math.radians(norm360(19.373+19140.2973*T))
    mars_t = norm360(L_ma+10.691*math.sin(M_ma)+0.623*math.sin(2*M_ma)+0.050*math.sin(3*M_ma))
    L_ju = norm360(34.3515+3034.9057*T)
    M_ju = math.radians(norm360(20.9961+3034.9056*T))
    jup_t = norm360(L_ju+5.555*math.sin(M_ju)+0.168*math.sin(2*M_ju))
    L_sa = norm360(50.0774+1222.1138*T)
    M_sa = math.radians(norm360(317.0207+1221.5515*T))
    sat_t = norm360(L_sa+6.393*math.sin(M_sa)+0.170*math.sin(2*M_sa))
    rahu_t = norm360(125.0445-1934.1362*T+0.0020708*T*T)
    ketu_t = norm360(rahu_t+180)
    eps   = math.radians(23.439291111-0.013004167*T)
    GMST  = norm360(280.46061837+360.98564736629*(jd-2451545.0)+0.000387933*T*T)
    LST   = math.radians(norm360(GMST+lon))
    lat_r = math.radians(lat)
    asc_t = math.degrees(math.atan2(
        math.cos(LST),
        -math.sin(LST)*math.cos(eps) - math.tan(lat_r)*math.sin(eps)
    )) % 360
    ay = lahiri_ayanamsa(jd)
    sid = {
        "As":(asc_t-ay)%360,"Su":(sun_t-ay)%360,"Mo":(moon_t-ay)%360,
        "Me":(merc_t-ay)%360,"Ve":(ven_t-ay)%360,"Ma":(mars_t-ay)%360,
        "Ju":(jup_t-ay)%360,"Sa":(sat_t-ay)%360,
        "Ra":(rahu_t-ay)%360,"Ke":(ketu_t-ay)%360,
    }
    return sid, ay

def lon_to_sign_deg(lon):
    lon = lon % 360
    return int(lon/30), round(lon%30, 2)

def d9_sign(lon):
    sign, deg = lon_to_sign_deg(lon)
    nav_num = int(deg/(30.0/9))
    start_map = {0:0,1:9,2:6,3:3,4:0,5:9,6:6,7:3,8:0,9:9,10:6,11:3}
    return (start_map[sign] + nav_num) % 12

# ── NORTH INDIAN DIAMOND CHART (Canvas-based) ──────────────────────────────────
def build_diamond_chart(positions, lagna_sign, title, chart_size=310):
    """
    Draw North Indian diamond Kundali chart using Flet Canvas.
    positions = {planet_abbr: sign_index_0_to_11}
    lagna_sign = sign index of ascendant (House 1)
    """
    W = chart_size
    p = 5  # padding

    # Key coordinate points
    TL=(p,p);   TR=(W-p,p);  BR=(W-p,W-p); BL=(p,W-p)
    T=(W//2,p); R=(W-p,W//2); B=(W//2,W-p); L=(p,W//2)
    q = W//4
    iT=(W//2, p+q)
    iR=(W-p-q, W//2)
    iB=(W//2, W-p-q)
    iL=(p+q, W//2)
    C=(W//2, W//2)

    # 12 house polygon vertices (clockwise from top = H1)
    HOUSES = {
        1: [T,  TR, iR, iT],
        2: [TR, R,  iR],
        3: [R,  BR, iB, iR],
        4: [BR, B,  iB],
        5: [B,  BL, iL, iB],
        6: [BL, L,  iL],
        7: [L,  TL, iT, iL],
        8: [TL, T,  iT],
        9: [iT, iR, C],
        10:[iR, iB, C],
        11:[iB, iL, C],
        12:[iL, iT, C],
    }

    def centroid(pts):
        return sum(x for x,y in pts)//len(pts), sum(y for x,y in pts)//len(pts)

    # Map sign_index → planets in that sign
    sign_planets = {i: [] for i in range(12)}
    for planet, s_idx in positions.items():
        sign_planets[int(s_idx)].append(PLANET_NAMES.get(planet, planet))

    # Lagna sign index
    lagna_s = int(lagna_sign)

    def house_sign(house_num):
        return (lagna_s + house_num - 1) % 12

    shapes = []

    # Background
    shapes.append(cv.Fill(
        paint=ft.Paint(color="#FAFAFA")))

    # Draw each house polygon
    for house_num, pts in HOUSES.items():
        sign_idx    = house_sign(house_num)
        planets_here = sign_planets.get(sign_idx, [])
        is_lagna    = (house_num == 1)

        bg = "#FFD6D6" if is_lagna else "#E8F0FE"
        bd = "#B71C1C" if is_lagna else "#0D47A1"

        # Fill polygon
        path_fill = [cv.Path.MoveTo(pts[0][0], pts[0][1])]
        for pt in pts[1:]:
            path_fill.append(cv.Path.LineTo(pt[0], pt[1]))
        path_fill.append(cv.Path.Close())
        shapes.append(cv.Path(path_fill,
            paint=ft.Paint(color=bg, style=ft.PaintingStyle.FILL)))

        # Stroke polygon
        path_stroke = [cv.Path.MoveTo(pts[0][0], pts[0][1])]
        for pt in pts[1:]:
            path_stroke.append(cv.Path.LineTo(pt[0], pt[1]))
        path_stroke.append(cv.Path.Close())
        shapes.append(cv.Path(path_stroke,
            paint=ft.Paint(color=bd, stroke_width=1.5,
                           style=ft.PaintingStyle.STROKE)))

        # Text label
        cx, cy = centroid(pts)
        sign_txt = SIGN_ABB[sign_idx]
        hindi_txt = SIGN_HI[sign_idx]
        planet_txt = " ".join(planets_here)
        house_txt  = str(house_num)

        # House number (small, top-left of centroid)
        shapes.append(cv.Text(
            x=cx-18, y=cy-22,
            text=house_txt,
            style=ft.TextStyle(
                size=9, color="#546E7A",
                weight="normal")))

        # Sign abbr + hindi
        shapes.append(cv.Text(
            x=cx-14, y=cy-12,
            text=sign_txt,
            style=ft.TextStyle(
                size=11,
                color="#B71C1C" if is_lagna else "#0D47A1",
                weight="bold")))

        shapes.append(cv.Text(
            x=cx-18, y=cy+1,
            text=hindi_txt,
            style=ft.TextStyle(
                size=10,
                color="#B71C1C" if is_lagna else "#1565C0",
                weight="normal")))

        # Planets (DARK BLUE bold, bigger visibility size=13)
        if planet_txt:
            shapes.append(cv.Text(
                x=cx-20, y=cy+14,
                text=planet_txt,
                style=ft.TextStyle(
                    size=13,
                    color="#0D47A1",
                    weight="bold")))

    # Title in center
    shapes.append(cv.Text(
        x=C[0]-28, y=C[1]-8,
        text=title,
        style=ft.TextStyle(
            size=9, color="#0D47A1",
            weight="bold")))

    return cv.Canvas(shapes=shapes, width=W, height=W)


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
                symbol TEXT PRIMARY KEY, eng TEXT, hindi TEXT,
                ldate TEXT, asum INTEGER, breakdown TEXT,
                series TEXT DEFAULT 'EQ')""")
            conn.commit(); conn.close()
        except: pass

        def db_count():
            try:
                return sqlite3.connect(db_path).execute(
                    "SELECT COUNT(*) FROM stocks").fetchone()[0]
            except: return 0

        def db_search(q=""):
            try:
                conn = sqlite3.connect(db_path)
                if q:
                    rows = conn.execute(
                        "SELECT symbol,eng,hindi,ldate,asum FROM stocks "
                        "WHERE symbol LIKE ? OR eng LIKE ? "
                        "ORDER BY symbol LIMIT 100",
                        ("%"+q+"%","%"+q+"%")).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT symbol,eng,hindi,ldate,asum FROM stocks "
                        "ORDER BY symbol LIMIT 100").fetchall()
                conn.close(); return rows
            except: return []

        def db_get(sym):
            try:
                conn = sqlite3.connect(db_path)
                row = conn.execute(
                    "SELECT * FROM stocks WHERE symbol=?",
                    (sym,)).fetchone()
                conn.close(); return row
            except: return None

        def db_save(sym, eng, hindi, ldate, series="EQ"):
            asum, bk = calc(hindi)
            try:
                conn = sqlite3.connect(db_path)
                conn.execute(
                    "INSERT OR REPLACE INTO stocks VALUES(?,?,?,?,?,?,?)",
                    (sym,eng,hindi,ldate,asum,bk,series))
                conn.commit(); conn.close()
                return True, asum
            except Exception as ex: return False, str(ex)

        def db_delete(sym):
            try:
                conn = sqlite3.connect(db_path)
                conn.execute("DELETE FROM stocks WHERE symbol=?",(sym,))
                conn.commit(); conn.close(); return True
            except: return False

        # ── SHARED STATUS & PROGRESS ───────────────────────────────────────────
        status_txt = ft.Text("Loading...", size=15,
                             color="#FFFFFF", weight="bold")
        status_bar = ft.Container(
            content=status_txt, bgcolor=C["secondary"],
            padding=10, border_radius=6)
        prg_bar = ft.ProgressBar(value=0, visible=False,
                                 color="#FF6F00", bgcolor="#EEEEEE")
        prg_txt = ft.Text("", size=13, color=C["orange"], weight="bold")

        def set_status(msg, color=None):
            status_txt.value = msg
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

        # ── HELPERS ────────────────────────────────────────────────────────────
        def make_field(label, hint="", value=""):
            return ft.TextField(
                label=label,
                label_style=ft.TextStyle(size=14, color=C["primary"]),
                hint_text=hint,
                hint_style=ft.TextStyle(size=13, color=C["hint_txt"]),
                value=value, text_size=16,
                text_style=ft.TextStyle(size=16, color=C["black_txt"],
                                        weight="bold"),
                border_color=C["primary"],
                focused_border_color=C["accent"],
                border_width=2, bgcolor=C["inp_bg"],
                cursor_color=C["primary"])

        def make_header(title, bgcolor=None):
            return ft.Container(
                content=ft.Text(title, size=16,
                                color="#FFFFFF", weight="bold"),
                bgcolor=bgcolor or C["primary"],
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                border_radius=6)

        def res_box(txt_ctrl):
            return ft.Container(
                content=txt_ctrl, bgcolor=C["res_bg"],
                padding=12, border_radius=8,
                border=ft.Border(
                    top=ft.BorderSide(2,C["primary"]),
                    bottom=ft.BorderSide(2,C["primary"]),
                    left=ft.BorderSide(2,C["primary"]),
                    right=ft.BorderSide(2,C["primary"])))

        # ══════════════════════════════════════════════════════════════════════
        # SCREEN 1 — ORACLE
        # ══════════════════════════════════════════════════════════════════════
        fld_oracle = make_field("NSE Stock Symbol or Name",
                                "e.g. RELIANCE or TCS", "RELIANCE")
        result_txt = ft.Text("", size=14, color=C["dark_txt"],
                             selectable=True, font_family="monospace")
        result_cont = res_box(result_txt)
        result_cont.visible = False

        def do_oracle(e):
            q = fld_oracle.value.strip().upper()
            if not q:
                set_status("Enter a stock symbol.", C["red"]); return
            set_status("Searching: " + q + " ...", C["accent"])
            if db_count() < 5:
                set_status("Database empty! Go to Build tab.", C["red"])
                result_txt.value = ("DATABASE IS EMPTY\n\n"
                    "Go to Build tab → tap BUILD DATABASE.\n"
                    "Needs internet. Takes 5-15 minutes.")
                result_cont.visible = True; page.update(); return
            row = db_get(q)
            if not row:
                rows = db_search(q)
                if rows: row = db_get(rows[0][0])
            if row:
                sym,eng,hi,ldt,asum,bk,*_ = row
                ldate = parse_dt(ldt)
                today = datetime.now()
                days  = (today-ldate).days if ldate else 0
                tval  = days % 730
                bk_items = bk.split(" ")
                bk_lines = []; line = ""
                for item in bk_items:
                    if len(line) > 30:
                        bk_lines.append(line); line = ""
                    line += item + " "
                if line: bk_lines.append(line)
                rep = make_report(asum, tval, ldate)
                set_status("Found: " + sym, C["green"])
                result_txt.value = "\n".join([
                    "═"*30, "SYMBOL  : "+sym,
                    "COMPANY : "+eng, "HINDI   : "+hi,
                    "LISTED  : "+ldt, "═"*30,
                    "AKSHARA BREAKUP:"] +
                    ["  "+ln for ln in bk_lines] + [
                    "─"*30,
                    "AKSHARA SUM  = "+str(asum),
                    "TEMPORAL MOD = "+str(tval),
                    "COMBINED VIB = "+str(asum+tval),
                    "NAVAANK      = "+str((asum%9) or 9),
                    "", rep])
                result_cont.visible = True
            else:
                set_status("Not found: "+q, C["red"])
                result_txt.value = ("'"+q+"' NOT FOUND\n\n"
                    "Try: RELIANCE TCS SBIN INFY WIPRO ITC LT")
                result_cont.visible = True
            page.update()

        oracle_screen = ft.Column(visible=True, controls=[
            make_header("🔮  ORACLE ANALYSIS"),
            ft.Divider(height=4, color=C["divider"]),
            ft.Text("Enter Stock Symbol or Name:",
                    size=15, color=C["black_txt"], weight="bold"),
            fld_oracle,
            ft.ElevatedButton("🔍  SEARCH AND CALCULATE",
                bgcolor=C["green"], color="#FFFFFF", height=52,
                style=ft.ButtonStyle(text_style=ft.TextStyle(
                    size=17, weight="bold")),
                on_click=do_oracle),
            ft.Divider(height=6, color=C["divider"]),
            result_cont,
        ])

        # ══════════════════════════════════════════════════════════════════════
        # SCREEN 2 — STOCK LIST
        # ══════════════════════════════════════════════════════════════════════
        fld_list_search = make_field("Search Symbol or Company",
                                     "Leave blank for first 100")
        list_rows  = ft.Column(controls=[], spacing=2)
        list_count = ft.Text("", size=14, color=C["primary"], weight="bold")

        def load_list(q=""):
            list_rows.controls.clear()
            rows = db_search(q)
            list_count.value = ("Showing "+str(len(rows))+" stocks"
                + (" matching '"+q+"'" if q else " (first 100)"))
            for i, r in enumerate(rows):
                sym,eng,hi,ldt,asum = r
                bg = C["inp_bg"] if i%2==0 else "#FFFFFF"
                def mk_edit(s=sym):
                    def h(e): load_edit(s)
                    return h
                def mk_analyse(s=sym):
                    def h(e):
                        fld_oracle.value = s
                        show_screen("oracle")
                        do_oracle(e)
                    return h
                list_rows.controls.append(ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Container(
                                content=ft.Text(sym, size=14,
                                    color="#FFFFFF", weight="bold"),
                                bgcolor=C["primary"],
                                padding=ft.padding.symmetric(
                                    horizontal=8,vertical=3),
                                border_radius=4),
                            ft.Text(ldt, size=11, color=C["hint_txt"]),
                            ft.Text("Ak:"+str(asum), size=11,
                                    color=C["accent"]),
                        ]),
                        ft.Text(eng, size=14, color=C["black_txt"],
                                weight="bold"),
                        ft.Text(hi, size=14, color=C["primary"],
                                weight="bold"),
                        ft.Row([
                            ft.TextButton("✏️ Edit",
                                style=ft.ButtonStyle(color=C["accent"]),
                                on_click=mk_edit(sym)),
                            ft.TextButton("🔮 Analyse",
                                style=ft.ButtonStyle(color=C["green"]),
                                on_click=mk_analyse(sym)),
                        ]),
                    ], spacing=2),
                    bgcolor=bg, padding=8, border_radius=6,
                    border=ft.Border(
                        bottom=ft.BorderSide(1,C["divider"]))))
            page.update()

        list_screen = ft.Column(visible=False, controls=[
            make_header("📋  STOCK LIST — NSE India"),
            ft.Divider(height=4, color=C["divider"]),
            fld_list_search,
            ft.Row([
                ft.ElevatedButton("🔍 Search",
                    bgcolor=C["primary"], color="#FFFFFF", height=46,
                    style=ft.ButtonStyle(text_style=ft.TextStyle(
                        size=15,weight="bold")),
                    on_click=lambda e: load_list(
                        fld_list_search.value.strip().upper())),
                ft.ElevatedButton("📋 Show All",
                    bgcolor=C["accent"], color="#FFFFFF", height=46,
                    style=ft.ButtonStyle(text_style=ft.TextStyle(
                        size=15,weight="bold")),
                    on_click=lambda e: load_list("")),
            ]),
            list_count,
            ft.Divider(height=4, color=C["divider"]),
            list_rows,
        ])

        # ══════════════════════════════════════════════════════════════════════
        # SCREEN 3 — DATA ENTRY
        # ══════════════════════════════════════════════════════════════════════
        fld_sym   = make_field("Symbol *", "e.g. RELIANCE")
        fld_eng   = make_field("English Name *", "e.g. Reliance Industries Ltd")
        fld_hindi = make_field("Hindi Name *", "e.g. रिलायंस इंडस्ट्रीज")
        fld_ldate = make_field("Listing Date", "DD-MM-YYYY")
        fld_series= make_field("Series", "e.g. EQ", "EQ")
        entry_st  = ft.Text("", size=15, color=C["green"], weight="bold")
        ak_prev   = ft.Container(
            content=ft.Text("", size=13, color=C["dark_txt"]),
            bgcolor=C["res_bg"], padding=10,
            border_radius=6, visible=False)

        def load_edit(sym):
            row = db_get(sym)
            if row:
                fld_sym.value = row[0]; fld_sym.disabled = True
                fld_eng.value = row[1]; fld_hindi.value = row[2]
                fld_ldate.value = row[3]
                fld_series.value = row[6] if len(row)>6 else "EQ"
                asum,bk = calc(row[2])
                ak_prev.content.value = "Akshara Sum = "+str(asum)+"\n"+bk[:80]
                ak_prev.visible = True
                entry_st.value = "Loaded: "+sym+" — Edit and tap UPDATE"
                entry_st.color = C["accent"]
                show_screen("entry"); page.update()

        def do_translit(e):
            eng = fld_eng.value.strip()
            sym = fld_sym.value.strip().upper()
            if not eng:
                entry_st.value = "Enter English name first."
                entry_st.color = C["red"]; page.update(); return
            entry_st.value = "Transliterating..."; entry_st.color = C["accent"]
            page.update()
            hi = get_hindi(sym, eng)
            fld_hindi.value = hi
            asum,bk = calc(hi)
            ak_prev.content.value = "Akshara Sum = "+str(asum)+"\n"+bk[:80]
            ak_prev.visible = True
            entry_st.value = "Hindi name generated!"; entry_st.color = C["green"]
            page.update()

        def do_preview(e):
            hi = fld_hindi.value.strip()
            if not hi:
                entry_st.value = "Enter Hindi name first."
                entry_st.color = C["red"]; page.update(); return
            asum,bk = calc(hi)
            ak_prev.content.value = "Akshara Sum = "+str(asum)+"\n"+bk[:120]
            ak_prev.visible = True
            entry_st.value = "Akshara="+str(asum)+"  Navaank="+str((asum%9) or 9)
            entry_st.color = C["primary"]; page.update()

        def do_save(e):
            sym=fld_sym.value.strip().upper()
            eng=fld_eng.value.strip()
            hindi=fld_hindi.value.strip()
            ldate=fld_ldate.value.strip()
            ser=fld_series.value.strip() or "EQ"
            if not (sym and eng and hindi):
                entry_st.value = "Symbol, English and Hindi are required!"
                entry_st.color = C["red"]; page.update(); return
            ok,val = db_save(sym,eng,hindi,ldate,ser)
            entry_st.value = ("Saved! "+sym+"  Ak="+str(val) if ok
                              else "Save failed: "+str(val))
            entry_st.color = C["green"] if ok else C["red"]
            if ok: fld_sym.disabled = False
            page.update()

        def do_update(e):
            sym=fld_sym.value.strip().upper()
            if not sym:
                entry_st.value = "No symbol loaded!"
                entry_st.color = C["red"]; page.update(); return
            ok,val = db_save(sym,fld_eng.value.strip(),
                             fld_hindi.value.strip(),
                             fld_ldate.value.strip(),
                             fld_series.value.strip() or "EQ")
            entry_st.value = ("Updated! "+sym+"  Ak="+str(val) if ok
                              else "Update failed: "+str(val))
            entry_st.color = C["green"] if ok else C["red"]
            if ok: fld_sym.disabled = False
            page.update()

        def do_delete(e):
            sym = fld_sym.value.strip().upper()
            if not sym:
                entry_st.value = "No symbol to delete!"
                entry_st.color = C["red"]; page.update(); return
            if db_delete(sym):
                entry_st.value = "Deleted: "+sym
                entry_st.color = C["orange"]
                do_clear(None)
            else:
                entry_st.value = "Delete failed!"
                entry_st.color = C["red"]
            page.update()

        def do_clear(e):
            fld_sym.value=fld_eng.value=fld_hindi.value=""
            fld_ldate.value=""; fld_series.value="EQ"
            fld_sym.disabled=False; ak_prev.visible=False
            entry_st.value="Form cleared."; entry_st.color=C["hint_txt"]
            page.update()

        entry_screen = ft.Column(visible=False, controls=[
            make_header("✏️  DATA ENTRY — Add / Edit Stock"),
            ft.Divider(height=4, color=C["divider"]),
            ft.Text("Fields marked * are required",
                    size=13, color=C["hint_txt"]),
            fld_sym, fld_eng,
            ft.ElevatedButton("🔄  Auto-Generate Hindi Name",
                bgcolor=C["accent"], color="#FFFFFF", height=46,
                style=ft.ButtonStyle(text_style=ft.TextStyle(
                    size=15,weight="bold")), on_click=do_translit),
            fld_hindi,
            ft.ElevatedButton("👁  Preview Akshara Calculation",
                bgcolor=C["secondary"], color="#FFFFFF", height=46,
                style=ft.ButtonStyle(text_style=ft.TextStyle(
                    size=15,weight="bold")), on_click=do_preview),
            ak_prev, fld_ldate, fld_series,
            ft.Divider(height=6, color=C["divider"]),
            ft.Row([
                ft.ElevatedButton("💾 SAVE NEW",
                    bgcolor=C["green"], color="#FFFFFF", height=50,
                    style=ft.ButtonStyle(text_style=ft.TextStyle(
                        size=15,weight="bold")),
                    on_click=do_save, expand=True),
                ft.ElevatedButton("📝 UPDATE",
                    bgcolor=C["accent"], color="#FFFFFF", height=50,
                    style=ft.ButtonStyle(text_style=ft.TextStyle(
                        size=15,weight="bold")),
                    on_click=do_update, expand=True),
            ]),
            ft.Row([
                ft.ElevatedButton("🗑 DELETE",
                    bgcolor=C["red"], color="#FFFFFF", height=46,
                    style=ft.ButtonStyle(text_style=ft.TextStyle(
                        size=14,weight="bold")),
                    on_click=do_delete, expand=True),
                ft.ElevatedButton("🧹 CLEAR",
                    bgcolor=C["hint_txt"], color="#FFFFFF", height=46,
                    style=ft.ButtonStyle(text_style=ft.TextStyle(
                        size=14,weight="bold")),
                    on_click=do_clear, expand=True),
            ]),
            entry_st,
        ])

        # ══════════════════════════════════════════════════════════════════════
        # SCREEN 4 — BUILD DATABASE
        # ══════════════════════════════════════════════════════════════════════
        build_res = ft.Text("", size=14, color=C["dark_txt"], selectable=True)

        def do_build(e):
            def worker():
                try:
                    set_status("Connecting to NSE India...", C["orange"])
                    set_prg(0.02, "Downloading NSE equity list...")
                    build_res.value = ("BUILD STARTED\n\n"
                        "Connecting to NSE India server...\n"
                        "Please keep app open.\n"
                        "Do not press back button.")
                    page.update()
                    hdrs = {"User-Agent":"Mozilla/5.0 (Android)"}
                    resp = requests.get(NSE_URL, headers=hdrs, timeout=60)
                    resp.raise_for_status()
                    all_rows = list(csv.DictReader(io.StringIO(
                        resp.content.decode("utf-8", errors="ignore"))))
                    rows = []
                    for r in all_rows:
                        nm = {k.strip().upper():(v.strip() if v else "")
                              for k,v in r.items()}
                        ser = nm.get("SERIES","").strip()
                        if ser == "EQ" or not ser: rows.append(nm)
                    total = len(rows)
                    set_status("Downloaded "+str(total)+" EQ stocks!", C["orange"])
                    set_prg(0.10, "Translating "+str(total)+" stocks to Hindi...")
                    build_res.value = ("BUILD IN PROGRESS\n\n"
                        "Downloaded: "+str(total)+" EQ stocks\n\n"
                        "Translating to Hindi\n"
                        "Calculating Akshara values...\n\n"
                        "Progress bar filling above.\n"
                        "Takes 5-15 minutes. Please wait...")
                    page.update()
                    conn2 = sqlite3.connect(db_path)
                    cur   = conn2.cursor(); done = 0
                    for i,nm in enumerate(rows):
                        sym = nm.get("SYMBOL","").strip()
                        eng = nm.get("NAME OF COMPANY",
                              nm.get("COMPANY NAME","")).strip()
                        ldt = nm.get("DATE OF LISTING","01-01-2000").strip()
                        ser = nm.get("SERIES","EQ").strip()
                        if not sym or sym.lower()=="symbol": continue
                        hi = get_hindi(sym, eng)
                        asum,bk = calc(hi)
                        cur.execute(
                            "INSERT OR REPLACE INTO stocks VALUES(?,?,?,?,?,?,?)",
                            (sym,eng,hi,ldt,asum,bk,ser))
                        done += 1
                        if i%25==0:
                            conn2.commit()
                            pct = 0.10+(i/max(total,1))*0.90
                            set_status("Processing "+str(i)+"/"+str(total)
                                       +" — "+sym, C["orange"])
                            set_prg(pct, str(int(pct*100))+"% — "+sym)
                    conn2.commit(); conn2.close()
                    set_prg(1.0, "Complete! "+str(done)+" stocks ready!")
                    set_status("Ready! "+str(done)+" stocks.", C["green"])
                    build_res.value = ("BUILD COMPLETE!\n\n"
                        "EQ stocks processed: "+str(done)+"\n\n"
                        "Go to ORACLE tab to analyse.\n"
                        "Go to STOCKS tab to view all.\n\n"
                        "Try: RELIANCE TCS SBIN INFY")
                    page.update()
                except Exception as ex:
                    hide_prg()
                    set_status("Build failed! Check internet.", C["red"])
                    build_res.value = ("BUILD FAILED\n\n"
                        "Error: "+str(ex)+"\n\n"
                        "Check internet and try again.")
                    page.update()
            set_status("Starting build...", C["orange"])
            build_res.value = "PREPARING BUILD...\nPlease wait..."
            page.update()
            threading.Thread(target=worker, daemon=True).start()

        build_screen = ft.Column(visible=False, controls=[
            make_header("🔄  DATABASE — Build & Manage"),
            ft.Divider(height=4, color=C["divider"]),
            ft.Container(
                content=ft.Column([
                    ft.Text("Downloads all NSE EQ series stocks",
                            size=14, color=C["dark_txt"]),
                    ft.Text("with Hindi names into local database.",
                            size=14, color=C["dark_txt"]),
                    ft.Text("Needs internet. Takes 5-15 minutes.",
                            size=13, color=C["hint_txt"]),
                ], spacing=2),
                bgcolor=C["res_bg"], padding=10, border_radius=6),
            ft.Divider(height=6, color=C["divider"]),
            ft.ElevatedButton("🔄  BUILD DATABASE  (first time)",
                bgcolor=C["orange"], color="#FFFFFF", height=54,
                style=ft.ButtonStyle(text_style=ft.TextStyle(
                    size=17,weight="bold")), on_click=do_build),
            ft.Divider(height=6, color=C["divider"]),
            build_res,
        ])

        # ══════════════════════════════════════════════════════════════════════
        # SCREEN 5 — ASTRO (D1 + D9 Diamond Charts)
        # ══════════════════════════════════════════════════════════════════════
        today_dt = datetime.now()
        fld_date  = make_field("Date (DD-MM-YYYY)",
                               "e.g. 09-07-2026",
                               today_dt.strftime("%d-%m-%Y"))
        fld_time  = make_field("Time (HH:MM) 24-hr IST",
                               "e.g. 14:30",
                               today_dt.strftime("%H:%M"))
        fld_place = make_field("Place Name",
                               "e.g. Mumbai, India",
                               "Mumbai, India")
        fld_lat   = make_field("Latitude (N+  S-)",
                               "Mumbai=19.076", "19.076")
        fld_lon   = make_field("Longitude (E+  W-)",
                               "Mumbai=72.877", "72.877")

        astro_res_txt = ft.Text("", size=13, color=C["dark_txt"],
                                selectable=True, font_family="monospace")
        astro_res_box = ft.Container(
            content=astro_res_txt, bgcolor=C["res_bg"], padding=10,
            border_radius=6, visible=False,
            border=ft.Border(
                top=ft.BorderSide(2,C["primary"]),
                bottom=ft.BorderSide(2,C["primary"]),
                left=ft.BorderSide(2,C["primary"]),
                right=ft.BorderSide(2,C["primary"])))

        # Interactive scroll handler to return to inputs
        def scroll_to_astro_inputs(e):
            fld_date.focus()
            page.update()

        d1_container = ft.Container(visible=False)
        d9_container = ft.Container(visible=False)

        def do_calc_astro(e):
            try:
                set_status("Calculating Vedic charts...", C["accent"])
                date_str = fld_date.value.strip()
                time_str = fld_time.value.strip()
                lat  = float(fld_lat.value.strip())
                lon2 = float(fld_lon.value.strip())
                try:
                    dt = datetime.strptime(
                        date_str+" "+time_str, "%d-%m-%Y %H:%M")
                except:
                    try:
                        dt = datetime.strptime(
                            date_str+" "+time_str, "%Y-%m-%d %H:%M")
                    except:
                        set_status("Date format error! Use DD-MM-YYYY HH:MM",
                                   C["red"]); return
                # Convert IST to UTC (IST = UTC+5:30)
                total_min = dt.hour*60 + dt.minute - 330
                if total_min < 0: total_min += 1440
                h_utc = total_min // 60
                m_utc = total_min % 60
                jd = jd_from_dt(dt.year, dt.month, dt.day, h_utc, m_utc)
                sid, ay = calc_planet_positions(jd, lat, lon2)

                # Build planet table
                lines = ["═"*34,
                         "PLANET POSITIONS — SIDEREAL/LAHIRI",
                         "Date : "+date_str+"  "+time_str+" IST",
                         "Place: "+fld_place.value.strip(),
                         "Ayanamsa: "+str(round(ay,3))+"°  (Lahiri)",
                         "─"*34,
                         f"{'Planet':<12} {'Sign':<6} {'Hindi':<8} {'Deg':>5}"]
                lines.append("─"*34)

                d1_pos = {}; d9_pos = {}
                order = ["As","Su","Mo","Me","Ve","Ma","Ju","Sa","Ra","Ke"]
                p_full = {"As":"Lagna","Su":"Sun सूर्य","Mo":"Moon चंद्र",
                          "Ma":"Mars मंगल","Me":"Merc बुध","Ju":"Jupt गुरु",
                          "Ve":"Venu शुक्र","Sa":"Satn शनि",
                          "Ra":"Rahu राहु","Ke":"Ketu केतु"}
                for p in order:
                    lon_p = sid[p]
                    s_idx, deg = lon_to_sign_deg(lon_p)
                    d9_idx = d9_sign(lon_p)
                    d1_pos[p] = s_idx; d9_pos[p] = d9_idx
                    lines.append(f"{p_full.get(p,p):<12} "
                                 f"{SIGN_ABB[s_idx]:<6} "
                                 f"{SIGN_HI[s_idx]:<8} "
                                 f"{deg:>5.1f}°")
                lines += ["═"*34,
                          "As=Lagna Ra=Rahu Ke=Ketu",
                          "Lahiri Ayanamsa (Sidereal)",
                          "Accuracy: approx +/-1-2 degrees",
                          "═"*34]

                astro_res_txt.value = "\n".join(lines)
                astro_res_box.visible = True

                # D1 Diamond Chart Draw
                lagna_sign = d1_pos.get("As", 0)
                if CANVAS_OK:
                    d1_canvas = build_diamond_chart(
                        d1_pos, lagna_sign, "D1 RASI")
                    d1_container.content = d1_canvas
                else:
                    d1_container.content = ft.Text(
                        "Canvas not available for chart",
                        color=C["red"])
                d1_container.visible = True

                # D9 Diamond Chart Draw
                lagna_d9 = d9_pos.get("As", 0)
                if CANVAS_OK:
                    d9_canvas = build_diamond_chart(
                        d9_pos, lagna_d9, "D9 NAVAMSA")
                    d9_container.content = d9_canvas
                else:
                    d9_container.content = ft.Text(
                        "Canvas not available",
                        color=C["red"])
                d9_container.visible = True

                set_status("D1 & D9 Charts calculated!", C["green"])
                page.update()
            except Exception as ex:
                set_status("Calc error: "+str(ex), C["red"])
                astro_res_txt.value = "ERROR: "+str(ex)
                astro_res_box.visible = True
                page.update()

        astro_screen = ft.Column(visible=False, controls=[
            make_header("🪐  VEDIC ASTRO — D1 & D9 DIAMOND CHART",
                        C["primary"]),
            ft.Divider(height=4, color=C["divider"]),
            ft.Container(content=ft.Column([
                ft.Text("📍 Default: Mumbai, India",
                        size=14, color=C["dark_txt"], weight="bold"),
                ft.Text("19.076°N  72.877°E  IST (UTC+5:30)",
                        size=13, color=C["hint_txt"]),
            ], spacing=2), bgcolor=C["res_bg"], padding=8, border_radius=6),
            ft.Divider(height=4, color=C["divider"]),
            ft.Text("Date & Time (IST):", size=14,
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
                "🪐  CALCULATE D1 & D9 DIAMOND CHARTS",
                bgcolor=C["primary"], color="#FFFFFF", height=56,
                style=ft.ButtonStyle(text_style=ft.TextStyle(
                    size=16,weight="bold")),
                on_click=do_calc_astro),
            ft.Divider(height=8, color=C["divider"]),
            astro_res_box,
            ft.Divider(height=10, color=C["divider"]),
            
            # --- D1 Rasi Section ---
            ft.Container(content=ft.Text(
                "━━  D1 RASI CHART (जन्म कुंडली)  ━━",
                size=15, color=C["primary"], weight="bold",
                text_align="center"), padding=6),
            ft.Container(content=ft.Text(
                "H1 (Red) = Lagna  |  Houses go clockwise from top",
                size=12, color=C["hint_txt"]),
                padding=ft.padding.only(bottom=4)),
            d1_container,
            ft.ElevatedButton("⬅️ Back to Astro Input Form", 
                             icon=ft.icons.ARROW_UPWARD,
                             bgcolor=C["secondary"], color="#FFFFFF",
                             on_click=scroll_to_astro_inputs),
            
            ft.Divider(height=14, color=C["divider"]),
            
            # --- D9 Navamsa Section ---
            ft.Container(content=ft.Text(
                "━━  D9 NAVAMSA CHART (नवांश कुंडली)  ━━",
                size=15, color=C["primary"], weight="bold",
                text_align="center"), padding=6),
            ft.Container(content=ft.Text(
                "Each sign ÷ 9 parts of 3°20'  |  Soul & Dharma chart",
                size=12, color=C["hint_txt"]),
                padding=ft.padding.only(bottom=4)),
            d9_container,
            ft.ElevatedButton("⬅️ Back to Astro Input Form", 
                             icon=ft.icons.ARROW_UPWARD,
                             bgcolor=C["secondary"], color="#FFFFFF",
                             on_click=scroll_to_astro_inputs),
            
            ft.Divider(height=8, color=C["divider"]),
            ft.Container(content=ft.Text(
                "North Indian Diamond Style  |  Lahiri Ayanamsa\n"
                "Research only. Not financial or astrological advice.",
                size=11, color=C["hint_txt"], text_align="center"),
                bgcolor=C["res_bg"], padding=8, border_radius=6),
        ])

        # ══════════════════════════════════════════════════════════════════════
        # SCREEN 6 — HELP / THEORY
        # ══════════════════════════════════════════════════════════════════════
        HELP_TEXT = (
            "╔══════════════════════════════╗\n"
            "   BHOOVALAYA ORACLE — THEORY\n"
            "   COMPLETE REFERENCE GUIDE\n"
            "╚══════════════════════════════╝\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "THEORY 1: BHOOVALAYA AKSHARA\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Ancient Jain text by Sage\n"
            "Kumudendu (9th century AD).\n"
            "Each Devanagari sound = weight:\n"
            "  अ=1 आ=2 इ=3 ई=4 उ=5 ऊ=6\n"
            "  ए=7 ऐ=8 ओ=9 औ=10\n"
            "  क=11 ख=12 ग=13 घ=14...\n"
            "  प=31 र=37 ल=38 स=42 ह=43\n\n"
            "Example — रिलायंस:\n"
            "  र=37 ि=2 ल=38 ा=2 य=36\n"
            "  ं=1 स=42  Sum = 158\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "THEORY 2: NAVAANK (Digital Root)\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Reduce to single digit 1-9:\n"
            "  158→1+5+8=14→1+4=5 (Navaank)\n\n"
            "Navaank → Ruling Planet:\n"
            "  1=Sun  2=Moon  3=Jupiter\n"
            "  4=Rahu 5=Mercury 6=Venus\n"
            "  7=Ketu 8=Saturn 9=Mars\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "THEORY 3: TEMPORAL VIBRATION\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "730 = Two Jupiter cycles\n"
            "  Days since NSE listing % 730\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "THEORY 4: SUTRA PRINCIPLE\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Combined = Akshara + Temporal\n"
            "Sutra = Combined % 9\n\n"
            "  0=अनंत  1=शक्ति  2=ज्ञान\n"
            "  3=धर्म  4=वैराग्य 5=ऐश्वर्य\n"
            "  6=यश   7=श्री   8=वीर्य\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "THEORY 5: GRAHA MARKET MAPPING\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Sun → BULLISH 5/5\n"
            "  PSU Govt Energy Gold\n"
            "  Hold 1-4 Wks | Best: Sunday\n\n"
            "Moon → VOLATILE 2/5\n"
            "  FMCG Dairy Retail\n"
            "  Hold 1-3 Days | Best: Monday\n\n"
            "Jupiter → STRONGLY BULLISH 5/5\n"
            "  Banking Education\n"
            "  Hold 1-6 Months | Best: Thu\n\n"
            "Rahu → SPECULATIVE 3/5\n"
            "  Tech Pharma Foreign\n"
            "  Caution | Best: Saturday\n\n"
            "Mercury → BULLISH 4/5\n"
            "  IT Telecom Media\n"
            "  Hold 1-3 Wks | Best: Wed\n\n"
            "Venus → BULLISH 4/5\n"
            "  FMCG Luxury Hotels\n"
            "  Hold 2-8 Wks | Best: Friday\n\n"
            "Ketu → BEARISH 2/5\n"
            "  Old Economy Exit Zones\n"
            "  Avoid Entry | Best: Tuesday\n\n"
            "Saturn → SLOW BULLISH 3/5\n"
            "  Infra Metals Coal\n"
            "  Hold 3-12 Months | Best: Sat\n\n"
            "Mars → BULLISH 4/5\n"
            "  Metals Defence Energy\n"
            "  Hold 1-7 Days | Best: Tuesday\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "THEORY 6: TARA BALA\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Count Nakshatras from listing\n"
            "date to today % 9:\n"
            "  2=सम्पत 4=क्षेम 6=साधक\n"
            "  8=मित्र 0=परम-मित्र = GOOD\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "THEORY 7: NAKSHATRA TIMING\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "27 Nakshatras = 1 lunar cycle\n"
            "Today Nakshatra = DayOfYear%27\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "D1 RASI CHART\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Shows actual positions of all\n"
            "planets at birth/query time.\n"
            "H1 (RED) = Lagna (Ascendant)\n"
            "Houses go clockwise from top.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "D9 NAVAMSA CHART\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Each sign divided into 9 parts\n"
            "of 3 degrees 20 minutes each.\n"
            "108 divisions total.\n"
            "Shows spouse, dharma & soul.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "COMPLETE ORACLE FLOW\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "  English Name\n"
            "       ↓\n"
            "  Hindi Transliteration\n"
            "       ↓\n"
            "  Akshara Sum (Theory 1)\n"
            "       ↓\n"
            "  Navaank 1-9 (Theory 2)\n"
            "       ↓\n"
            "  Ruling Planet + Market Bias\n"
            "       +\n"
            "  Temporal Vibration (Th 3)\n"
            "       ↓\n"
            "  Sutra Principle (Theory 4)\n"
            "       +\n"
            "  Tara Bala (Theory 6)\n"
            "       +\n"
            "  Today Nakshatra (Theory 7)\n"
            "       ↓\n"
            "  FINAL ORACLE FORECAST\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "DISCLAIMER\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "For study and research ONLY.\n"
            "NOT SEBI registered advice.\n"
            "Consult qualified financial\n"
            "advisor before investing.\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )

        help_screen = ft.Column(visible=False, controls=[
            make_header("❓  HELP — Theory & Reference"),
            ft.Divider(height=4, color=C["divider"]),
            ft.Container(
                content=ft.Text(HELP_TEXT, size=14,
                                color=C["dark_txt"], selectable=True,
                                font_family="monospace"),
                bgcolor=C["res_bg"], padding=14, border_radius=8,
                border=ft.Border(
                    top=ft.BorderSide(2,C["primary"]),
                    bottom=ft.BorderSide(2,C["primary"]),
                    left=ft.BorderSide(2,C["primary"]),
                    right=ft.BorderSide(2,C["primary"]))),
        ])

        # ══════════════════════════════════════════════════════════════════════
        # QUIT DIALOG — Confirm Yes/No before closing
        # ══════════════════════════════════════════════════════════════════════
        def confirm_quit(e):
            def yes_quit(ev):
                dlg.open = False
                page.update()
                page.window_destroy()

            def no_quit(ev):
                dlg.open = False
                page.update()

            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("Exit App?", size=18, weight="bold",
                              color=C["primary"]),
                content=ft.Text(
                    "Are you sure you want to exit\nBhoovalaya Oracle?",
                    size=15, color=C["black_txt"]),
                actions=[
                    ft.ElevatedButton(
                        "✅  YES — EXIT",
                        bgcolor=C["red"], color="#FFFFFF",
                        style=ft.ButtonStyle(text_style=ft.TextStyle(
                            size=15, weight="bold")),
                        on_click=yes_quit),
                    ft.ElevatedButton(
                        "❌  NO — STAY",
                        bgcolor=C["green"], color="#FFFFFF",
                        style=ft.ButtonStyle(text_style=ft.TextStyle(
                            size=15, weight="bold")),
                        on_click=no_quit),
                ],
                actions_alignment="center",
            )
            page.dialog = dlg
            dlg.open = True
            page.update()

        # Handle keyboard Enter key to show confirmation pop-up
        def on_keyboard(e: ft.KeyboardEvent):
            if e.key == "Enter":
                confirm_quit(None)

        page.on_keyboard_event = on_keyboard

        # Handle Android back button also triggers quit confirm
        def on_window_event(e):
            if e.data == "close":
                confirm_quit(e)

        page.on_window_event = on_window_event

        # ══════════════════════════════════════════════════════════════════════
        # NAVIGATION
        # ══════════════════════════════════════════════════════════════════════
        screens = {
            "oracle": oracle_screen,
            "list":   list_screen,
            "entry":  entry_screen,
            "build":  build_screen,
            "astro":  astro_screen,
            "help":   help_screen,
        }
        nav_buttons = {}

        def show_screen(name):
            for k, s in screens.items():
                s.visible = (k == name)
            for k, b in nav_buttons.items():
                b.bgcolor = C["primary"] if k == name else "#9E9E9E"
                b.color   = "#FFFFFF"
            if name == "list" and db_count() > 0:
                load_list("")
            page.update()

        def make_nav(label, name):
            btn = ft.ElevatedButton(
                text=label, bgcolor="#9E9E9E",
                color="#FFFFFF", height=48, expand=True,
                style=ft.ButtonStyle(
                    text_style=ft.TextStyle(size=12,weight="bold")),
                on_click=lambda e, n=name: show_screen(n))
            nav_buttons[name] = btn
            return btn

        nav_bar = ft.Row([
            make_nav("🔮\nOracle",  "oracle"),
            make_nav("📋\nStocks",  "list"),
            make_nav("✏️\nEntry",   "entry"),
            make_nav("🔄\nBuild",   "build"),
            make_nav("🪐\nAstro",   "astro"),
            make_nav("❓\nHelp",    "help"),
        ], spacing=2)

        # ── PAGE LAYOUT ────────────────────────────────────────────────────────
        page.add(ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text("🔮 BHOOVALAYA STOCK ORACLE",
                            size=17, color="#FFFFFF", weight="bold"),
                    ft.Text("Vedic Akshara + Financial Astrology",
                            size=11, color="#BBDEFB"),
                ], expand=True, spacing=2),
                ft.ElevatedButton(
                    "✕ QUIT",
                    bgcolor="#B71C1C", color="#FFFFFF", height=38,
                    style=ft.ButtonStyle(text_style=ft.TextStyle(
                        size=13, weight="bold")),
                    on_click=confirm_quit),
            ], alignment="spaceBetween"),
            bgcolor=C["primary"], padding=12))

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

        show_screen("oracle")

        # ── STARTUP MESSAGE ────────────────────────────────────────────────────
        n = db_count()
        if n < 5:
            set_status("No database. Go to Build tab.", C["red"])
            result_txt.value = ("WELCOME!\n\n"
                "App is working correctly.\n\n"
                "FIRST TIME SETUP:\n"
                "1. Tap BUILD tab below\n"
                "2. Tap BUILD DATABASE\n"
                "3. Wait 5-15 minutes\n"
                "4. Come back to ORACLE\n"
                "5. Search any NSE symbol\n\n"
                "Tap ❓HELP for theory guide.\n"
                "Tap 🪐ASTRO for D1 D9 charts.")
            result_cont.visible = True
        else:
            set_status("Ready — "+str(n)+" stocks loaded.", C["green"])
            result_txt.value = ("WELCOME BACK!\n\n"
                +str(n)+" stocks ready.\n\n"
                "Examples:\n"
                "  RELIANCE  TCS  SBIN\n"
                "  INFY  WIPRO  ITC  LT\n\n"
                "Tap 🪐ASTRO for D1+D9 charts.\n"
                "Tap ❓HELP for theory guide.")
            result_cont.visible = True
        page.update()

    except Exception as err:
        try:
            page.controls.clear()
            page.add(ft.Container(
                content=ft.Text("STARTUP ERROR:\n"+str(err),
                                size=15, color="#FFFFFF", selectable=True),
                bgcolor=C["red"], padding=16, border_radius=8))
            page.update()
        except: pass


ft.app(target=main)
