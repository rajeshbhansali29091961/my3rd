import os
import sqlite3
import threading
import csv
import io
import time
import math
import sys
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
    "BRITANNIA":"ब्रिटानिया निष्कर्ष","DABUR":"डाबर इंडिया",
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
        tc = ((today.timetuple().tm_yday - ldate.timetuple().tm_yday) % 27) + 1
        tn = ["जन्म","सम्पत","विपत","क्षेम","प्रत्यरि","साधक","वध","मित्र","परम-मित्र"]
        tara = tn[(tc-1)%9] + (" GOOD" if tc%9 in(2,4,6,8,0) else " CAUTION")
    else:
        tara = "N/A"
    S  = "─" * 30
    S2 = "═" * 30
    return "\n".join([
        S2, "    BHOOVALAYA ORACLE RESULT", S2, "",
        "STEP 1: AKSHARA WEIGHT THEORY", "  (Siribhoovalaya — Jain Text)",
        "  Each Hindi sound has weight:", "  अ=1 आ=2 इ=3 ई=4 उ=5 ऊ=6",
        "  ए=7 ऐ=8 ओ=9 क=11 ब=33 र=37", "  (64 Akshara × weight = sum)", S,
        "STEP 2: NAVAANK CALCULATION", "  (Vedic Digital Root Theory)",
        "  Akshara Sum = " + str(asum), "  Digital Root (1-9) = " + str(nv), "  " + _navaank_steps(asum), S,
        "STEP 3: TEMPORAL VIBRATION", "  (Jupiter Cycle = 730 days)", "  Days elapsed since listing",
        "  Temporal = Days % 730 = " + str(tval), "  Combined = " + str(asum) + " + " + str(tval) + " = " + str(total),
        "  Sutra Index = " + str(total) + " % 9 = " + str(total % 9), S,
        "STEP 4: SUTRA PRINCIPLE", "  (Bhoovalaya Cosmic Principle)", "  " + sutra, S,
        "STEP 5: RULING GRAHA (PLANET)", "  (Vedic Financial Astrology)", "  Navaank " + str(nv) + " → " + g[0], S2,
        "  MARKET FORECAST", S2, "  Signal   : " + g[1], "  Strength : " + bars.get(g[2],"") + "  " + str(g[2]) + "/5",
        "  Sectors  : " + g[3], "  Hold For : " + g[4], "  Caution  : " + g[5], "  Best Day : " + g[6], S,
        "STEP 6: VEDIC TIMING", "  (Nakshatra + Tara Bala)", "  Today    : " + wday + " " + today.strftime("%d-%m-%Y"),
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

# ── DIAMOND CHART GENERATOR COMPONENT ──────────────────────────────────────────
SIGN_HI = ["मेष","वृष","मिथुन","कर्क","सिंह","कन्या","तुला","वृश्चिक","धनु","मकर","कुंभ","मीन"]

def make_diamond_chart(title, base_sign):
    """Draws a complete North Indian Style Diamond Chart Layout"""
    signs = [((base_sign - 1 + i) % 12) + 1 for i in range(12)]
    
    def cell(txt):
        return ft.Container(
            content=ft.Text(txt, size=11, weight="bold", color="#0D47A1", text_align=ft.TextAlign.CENTER),
            alignment=ft.alignment.center
        )

    return ft.Container(
        width=260, height=260, bgcolor="#FAFBFF", border_radius=8, border=ft.border.all(1.5, "#90CAF9"), padding=5,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5,
            controls=[
                ft.Text(title, size=13, weight="bold", color="#0D47A1"),
                ft.Stack(
                    width=220, height=220,
                    controls=[
                        ft.Container(width=220, height=220, border=ft.border.all(2, "#0D47A1")),
                        ft.Container(
                            width=220, height=220,
                            content=ft.CustomPaint(
                                painter=ft.Paint(
                                    stroke_width=2, color="#0D47A1", style=ft.PaintingStyle.STROKE,
                                    path=[
                                        ft.PaintPath.move_to(110, 0), ft.PaintPath.line_to(220, 110),
                                        ft.PaintPath.line_to(110, 220), ft.PaintPath.line_to(0, 110), ft.PaintPath.close(),
                                        ft.PaintPath.move_to(0, 0), ft.PaintPath.line_to(220, 220),
                                        ft.PaintPath.move_to(220, 0), ft.PaintPath.line_to(0, 220),
                                    ]
                                )
                            )
                        ),
                        # House spaces labels
                        ft.Container(cell(f"H1\n{SIGN_HI[signs[0]-1]}"), left=75, top=35, width=70, height=40),
                        ft.Container(cell(f"H2\n{SIGN_HI[signs[1]-1]}"), left=30, top=5, width=50, height=40),
                        ft.Container(cell(f"H3\n{SIGN_HI[signs[2]-1]}"), left=5, top=35, width=50, height=40),
                        ft.Container(cell(f"H4\n{SIGN_HI[signs[3]-1]}"), left=30, top=80, width=50, height=60),
                        ft.Container(cell(f"H5\n{SIGN_HI[signs[4]-1]}"), left=5, top=145, width=50, height=40),
                        ft.Container(cell(f"H6\n{SIGN_HI[signs[5]-1]}"), left=30, top=175, width=50, height=40),
                        ft.Container(cell(f"H7\n{SIGN_HI[signs[6]-1]}"), left=75, top=145, width=70, height=40),
                        ft.Container(cell(f"H8\n{SIGN_HI[signs[7]-1]}"), left=140, top=175, width=50, height=40),
                        ft.Container(cell(f"H9\n{SIGN_HI[signs[8]-1]}"), left=165, top=145, width=50, height=40),
                        ft.Container(cell(f"H10\n{SIGN_HI[signs[9]-1]}"), left=140, top=80, width=50, height=60),
                        ft.Container(cell(f"H11\n{SIGN_HI[signs[10]-1]}"), left=165, top=35, width=50, height=40),
                        ft.Container(cell(f"H12\n{SIGN_HI[signs[11]-1]}"), left=140, top=5, width=50, height=40),
                    ]
                )
            ]
        )
    )

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
        except: pass

        def db_count():
            try: return sqlite3.connect(db_path).execute("SELECT COUNT(*) FROM stocks").fetchone()[0]
            except: return 0

        def db_search(q):
            try:
                conn = sqlite3.connect(db_path)
                rows = conn.execute(
                    "SELECT symbol, eng_name, hindi_name, ldate, asum FROM stocks WHERE symbol LIKE ? OR eng_name LIKE ? ORDER BY symbol LIMIT 100",
                    ("%" + q + "%", "%" + q + "%")
                ).fetchall()
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
                conn.execute("INSERT OR REPLACE INTO stocks VALUES(?,?,?,?,?,?,?)", (sym, eng, hindi, ldate, asum, bk, series))
                conn.commit()
                conn.close()
                return True, asum
            except Exception as ex:
                return False, str(ex)

        def db_delete(sym):
            try:
                conn = sqlite3.connect(db_path)
                conn.execute("DELETE FROM stocks WHERE symbol=?", (sym,))
                conn.commit()
                conn.close()
                return True
            except: return False

        # ── EXIT DIALOG CONTEXT CONFIRMATION IMPLEMENTATION ───────────────────
        def handle_close_confirmed(e):
            try:
                # Close any unmanaged global connections if active before exit
                pass
            except: pass
            page.window.close()
            sys.exit(0)

        def handle_close_dismissed(e):
            exit_modal_alert.open = False
            page.update()

        exit_modal_alert = ft.AlertDialog(
            modal=True,
            title=ft.Text("Exit Application"),
            content=ft.Text("Do you want to close all resources and exit?"),
            actions=[
                ft.TextButton("Yes", on_click=handle_close_confirmed),
                ft.TextButton("No", on_click=handle_close_dismissed),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(exit_modal_alert)

        def open_exit_dialog(e):
            exit_modal_alert.open = True
            page.update()

        # ── SHARED STATUS BAR ──────────────────────────────────────────────────
        status_txt = ft.Text("Loading...", size=15, color="#FFFFFF", weight="bold")
        status_bar = ft.Container(content=status_txt, bgcolor=C["secondary"], padding=10, border_radius=6)

        prg_bar  = ft.ProgressBar(value=0, visible=False, color="#FF6F00", bgcolor="#EEEEEE")
        prg_txt  = ft.Text("", size=14, color=C["orange"], weight="bold")

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

        def make_field(label, hint="", value="", multiline=False):
            return ft.TextField(
                label=label, label_style=ft.TextStyle(size=14, color=C["primary"]),
                hint_text=hint, hint_style=ft.TextStyle(size=13, color=C["hint_txt"]),
                value=value, text_size=16, text_style=ft.TextStyle(size=16, color=C["black_txt"], weight="bold"),
                border_color=C["primary"], focused_border_color=C["accent"], border_width=2,
                bgcolor=C["inp_bg"], cursor_color=C["primary"], multiline=multiline, min_lines=1 if not multiline else 2,
            )

        def make_header(title, bgcolor=None):
            return ft.Container(
                content=ft.Text(title, size=16, color="#FFFFFF", weight="bold"),
                bgcolor=bgcolor or C["primary"], padding=ft.padding.symmetric(horizontal=12, vertical=8), border_radius=6
            )

        # ══════════════════════════════════════════════════════════════════════
        # SCREEN 1 — ORACLE SEARCH
        # ══════════════════════════════════════════════════════════════════════
        fld_oracle = make_field("NSE Stock Symbol or Name", hint="Example: RELIANCE or TCS or SBIN", value="RELIANCE")
        result_txt = ft.Text("", size=15, color=C["dark_txt"], selectable=True, font_family="monospace")
        
        # Grid layout row container for hosting dynamic North Indian Diamond Style Charts
        charts_layout_container = ft.Row(wrap=True, spacing=15, alignment=ft.MainAxisAlignment.CENTER, controls=[])

        result_box = ft.Container(
            content=ft.Column([result_txt, charts_layout_container], spacing=10),
            bgcolor=C["res_bg"], padding=14, border_radius=8,
            border=ft.border.all(2, C["primary"]), visible=False
        )

        def do_oracle(e):
            q = fld_oracle.value.strip().upper()
            if not q:
                set_status("Enter a stock symbol.", C["red"])
                return
            set_status("Searching: " + q + " ...", C["accent"])
            charts_layout_container.controls.clear()
            
            if db_count() < 5:
                set_status("Database empty! Tap BUILD DATABASE.", C["red"])
                result_txt.value = "DATABASE IS EMPTY\n\nGo to Database tab and tap BUILD DATABASE."
                result_box.visible = True
                page.update()
                return
                
            row = db_get(q)
            if not row:
                rows = db_search(q)
                if rows: row = db_get(rows[0][0])
            if row:
                sym, eng, hi, ldt, asum, bk, *_ = row
                ldate = parse_dt(ldt)
                today = datetime.now()
                days  = (today - ldate).days if ldate else 0
                tval  = days % 730
                rep   = make_report(asum, tval, ldate)
                
                # Math calculations to map base numeric lagna ranges safely between 1 and 12
                d1_base = (asum % 12) or 12
                d9_base = ((asum + tval) % 12) or 12
                
                # Append updated North Indian diamond vector layout nodes
                charts_layout_container.controls.append(make_diamond_chart("D1 Kundali", d1_base))
                charts_layout_container.controls.append(make_diamond_chart("D9 Kundali", d9_base))
                
                set_status("Found: " + sym, C["green"])
                result_txt.value = "\n".join([
                    "━" * 30, f"SYMBOL  : {sym}", f"COMPANY : {eng}", f"HINDI   : {hi}", f"LISTED  : {ldt}", "━" * 30,
                    f"AKSHARA SUM  = {asum}", f"TEMPORAL MOD = {tval}", f"COMBINED VIB = {asum + tval}", f"NAVAANK      = {(asum % 9) or 9}", "", rep,
                ])
                result_box.visible = True
            else:
                set_status("Not found: " + q, C["red"])
                result_txt.value = f"'{q}' NOT FOUND\n\nTry: RELIANCE, TCS, SBIN"
                result_box.visible = True
            page.update()

        oracle_screen = ft.Column(
            visible=True,
            controls=[
                make_header("🔮  ORACLE ANALYSIS"),
                ft.Divider(height=4, color=C["divider"]),
                ft.Text("Enter Stock Symbol or Name:", size=15, color=C["black_txt"], weight="bold"),
                fld_oracle,
                ft.ElevatedButton(
                    "🔍  SEARCH AND CALCULATE", bgcolor=C["green"], color="#FFFFFF", height=52,
                    style=ft.ButtonStyle(text_style=ft.TextStyle(size=17, weight="bold")), on_click=do_oracle
                ),
                ft.Divider(height=6, color=C["divider"]),
                result_box,
            ])

        # ══════════════════════════════════════════════════════════════════════
        # SCREEN 2 — STOCK LIST (View All)
        # ══════════════════════════════════════════════════════════════════════
        fld_list_search = make_field("Search Symbol or Company Name", hint="Leave blank to show first 100 stocks")
        list_rows = ft.Column(controls=[], spacing=2)
        list_count_txt = ft.Text("", size=14, color=C["primary"], weight="bold")

        def load_list(q=""):
            list_rows.controls.clear()
            rows = db_search(q) if q else db_search("")
            list_count_txt.value = "Showing " + str(len(rows)) + " stocks" + (" matching '" + q + "'" if q else " (first 100)")

            for i, r in enumerate(rows):
                sym, eng, hi, ldt, asum = r
                bg = C["row_odd"] if i % 2 == 0 else C["row_even"]

                def make_edit_handler(s=sym):
                    return lambda e: load_edit(s)

                row_ctrl = ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Container(content=ft.Text(sym, size=15, color="#FFFFFF", weight="bold"), bgcolor=C["primary"], padding=ft.padding.symmetric(horizontal=10, vertical=4), border_radius=4),
                            ft.Text(ldt, size=12, color=C["hint_txt"]),
                            ft.Text("Ak:" + str(asum), size=12, color=C["accent"]),
                        ]),
                        ft.Text(eng, size=14, color=C["black_txt"], weight="bold"),
                        ft.Text(hi, size=15, color=C["primary"], weight="bold"),
                        ft.Row([
                            ft.TextButton("✏️ Edit", style=ft.ButtonStyle(color=C["accent"]), on_click=make_edit_handler(sym)),
                            ft.TextButton("🔮 Analyse", style=ft.ButtonStyle(color=C["green"]), on_click=lambda e, s=sym: (setattr(fld_oracle, 'value', s), show_screen("oracle"), do_oracle(e))),
                        ]),
                    ], spacing=2),
                    bgcolor=bg, padding=8, border_radius=6, border=ft.Border(bottom=ft.BorderSide(1, C["divider"])))
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
                    ft.ElevatedButton("🔍 Search", bgcolor=C["primary"], color="#FFFFFF", height=46, style=ft.ButtonStyle(text_style=ft.TextStyle(size=15, weight="bold")), on_click=do_list_search),
                    ft.ElevatedButton("📋 Show All", bgcolor=C["accent"], color="#FFFFFF", height=46, style=ft.ButtonStyle(text_style=ft.TextStyle(size=15, weight="bold")), on_click=lambda e: load_list("")),
                ]),
                list_count_txt,
                ft.Divider(height=4, color=C["divider"]),
                list_rows,
            ])

        # ══════════════════════════════════════════════════════════════════════
        # SCREEN 3 — DATA ENTRY
        # ══════════════════════════════════════════════════════════════════════
        fld_sym = make_field("Symbol *", "e.g. RELIANCE")
        fld_eng = make_field("English Company Name *", "e.g. Reliance Industries Ltd")
        fld_hindi = make_field("Hindi Name *", "e.g. रिलायंस...")
        fld_ldate = make_field("Listing Date", "DD-MM-YYYY")
        fld_series = make_field("Series", "e.g. EQ", value="EQ")
        entry_status = ft.Text("", size=15, color=C["green"], weight="bold")
        akshara_preview = ft.Container(content=ft.Text("", size=14, color=C["dark_txt"]), bgcolor=C["res_bg"], padding=10, border_radius=6, visible=False)

        def load_edit(sym):
            row = db_get(sym)
            if row:
                fld_sym.value = row[0]
                fld_sym.disabled = True
                fld_eng.value = row[1]
                fld_hindi.value = row[2]
                fld_ldate.value = row[3]
                fld_series.value = row[6] if len(row) > 6 else "EQ"
                asum, bk = calc(row[2])
                akshara_preview.content.value = "Akshara Sum = " + str(asum) + "\n" + bk[:80]
                akshara_preview.visible = True
                entry_status.value = "Loaded: " + sym + " — Edit and tap UPDATE"
                entry_status.color = C["accent"]
                show_screen("entry")
                page.update()

        def do_transliterate(e):
            eng = fld_eng.value.strip()
            sym = fld_sym.value.strip().upper()
            if not eng: return
            entry_status.value = "Transliterating..."
            page.update()
            hi = get_hindi(sym, eng)
            fld_hindi.value = hi
            asum, bk = calc(hi)
            akshara_preview.content.value = "Akshara Sum = " + str(asum) + "\n" + bk[:80]
            akshara_preview.visible = True
            entry_status.value = "Hindi name generated!"
            page.update()

        def do_preview(e):
            hi = fld_hindi.value.strip()
            if not hi: return
            asum, bk = calc(hi)
            akshara_preview.content.value = "Akshara Sum = " + str(asum) + "\n" + bk[:120]
            akshara_preview.visible = True
            page.update()

        def do_save(e):
            sym, eng, hindi, ldate, series = fld_sym.value.strip().upper(), fld_eng.value.strip(), fld_hindi.value.strip(), fld_ldate.value.strip(), fld_series.value.strip() or "EQ"
            if not sym or not eng or not hindi: return
            ok, val = db_save(sym, eng, hindi, ldate, series)
            if ok: entry_status.value = f"Saved {sym}!"
            page.update()

        def do_update(e):
            sym, eng, hindi, ldate, series = fld_sym.value.strip().upper(), fld_eng.value.strip(), fld_hindi.value.strip(), fld_ldate.value.strip(), fld_series.value.strip() or "EQ"
            ok, val = db_save(sym, eng, hindi, ldate, series)
            if ok: entry_status.value = f"Updated {sym}!"
            page.update()

        def do_delete(e):
            sym = fld_sym.value.strip().upper()
            if db_delete(sym): do_clear(None); entry_status.value = "Deleted!"
            page.update()

        def do_clear(e):
            fld_sym.value, fld_eng.value, fld_hindi.value, fld_ldate.value = "", "", "", ""
            fld_sym.disabled, akshara_preview.visible = False, False
            page.update()

        entry_screen = ft.Column(
            visible=False,
            controls=[
                make_header("✏️ DATA ENTRY — Add / Edit Stock"),
                fld_sym, fld_eng,
                ft.ElevatedButton("🔄 Auto-Generate Hindi Name", bgcolor=C["accent"], color="#FFFFFF", on_click=do_transliterate),
                fld_hindi,
                ft.ElevatedButton("👁 Preview Akshara Calculation", bgcolor=C["secondary"], color="#FFFFFF", on_click=do_preview),
                akshara_preview, fld_ldate, fld_series, entry_status,
                ft.Row([
                    ft.ElevatedButton("💾 SAVE NEW", bgcolor=C["green"], color="#FFFFFF", on_click=do_save),
                    ft.ElevatedButton("🆙 UPDATE", bgcolor=C["accent"], color="#FFFFFF", on_click=do_update),
                    ft.ElevatedButton("❌ DELETE", bgcolor=C["red"], color="#FFFFFF", on_click=do_delete),
                    ft.ElevatedButton("🧹 CLEAR", bgcolor=C["hint_txt"], color="#FFFFFF", on_click=do_clear),
                ], wrap=True)
            ])

        # ══════════════════════════════════════════════════════════════════════
        # SCREEN 4 — DATABASE MANAGEMENT (Build From Web Script Elements)
        # ══════════════════════════════════════════════════════════════════════
        db_info_txt = ft.Text("Checking database...", size=14)

        def run_build():
            if not REQUESTS_OK:
                set_status("Requests library missing!", C["red"])
                return
            try:
                set_status("Downloading CSV database files...", C["accent"])
                res = requests.get(NSE_URL, timeout=15)
                f = io.StringIO(res.text)
                reader = csv.reader(f)
                header = next(reader)
                rows = list(reader)
                
                total_rows = len(rows)
                for index, line in enumerate(rows):
                    if len(line) < 3 or line[2].strip() != 'EQ': continue
                    sym, eng, ldate = line[0].strip(), line[1].strip(), line[2].strip()
                    hi = get_hindi(sym, eng)
                    db_save(sym, eng, hi, ldate)
                    if index % 10 == 0:
                        set_prg(index / total_rows, f"Processing stock data elements {index}/{total_rows}")
                hide_prg()
                set_status("Database population complete!", C["green"])
            except Exception as e:
                set_status(f"Error: {e}", C["red"])

        def start_db_build(e):
            threading.Thread(target=run_build, daemon=True).start()

        db_screen = ft.Column(
            visible=False,
            controls=[
                make_header("⚙️ DATABASE TOOLS"),
                db_info_txt,
                ft.ElevatedButton("🏗️ POPULATE ONLINE NSE DATABASE", bgcolor=C["orange"], color="#FFFFFF", on_click=start_db_build)
            ])

        # Navigation Controller Routing Engine
        screens = {"oracle": oracle_screen, "list": list_screen, "entry": entry_screen, "db": db_screen}

        def show_screen(name):
            for k, scr in screens.items(): scr.visible = (k == name)
            page.update()

        def nav_changed(e):
            idx = e.control.selected_index
            names = ["oracle", "list", "entry", "db"]
            if idx < len(names): show_screen(names[idx])

        page.navigation_bar = ft.NavigationBar(
            destinations=[
                ft.NavigationBarDestination(icon=ft.icons.PSYCHOLOGY, label="Oracle"),
                ft.NavigationBarDestination(icon=ft.icons.LIST, label="Stock List"),
                ft.NavigationBarDestination(icon=ft.icons.EDIT, label="Entry"),
                ft.NavigationBarDestination(icon=ft.icons.STORAGE, label="Database")
            ],
            on_change=nav_changed
        )

        # Append functional Global operational Exit buttons layout 
        exit_bar_row = ft.Row([
            ft.ElevatedButton("🚪 EXIT BHOOVALAYA TERMINAL", bgcolor=C["red"], color="#FFFFFF", on_click=open_exit_dialog)
        ], alignment=ft.MainAxisAlignment.END)

        page.add(status_bar, prg_bar, prg_txt, oracle_screen, list_screen, entry_screen, db_screen, ft.Divider(height=10), exit_bar_row)
        
        n = db_count()
        set_status(f"System Operational Context Ready — {n} stocks loaded.", C["green"])

    except Exception as err:
        page.add(ft.Text(f"Fatal Startup Crash Vector: {err}", color="red"))
        page.update()

ft.app(target=main)
