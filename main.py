import os
import sqlite3
import threading
import csv
import io
import time
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
}
WD = {
    "LIMITED":"लिमिटेड","LTD":"लिमिटेड","BANK":"बैंक",
    "INDUSTRIES":"इंडस्ट्रीज","INDIA":"इंडिया","POWER":"पावर",
    "ENERGY":"एनर्जी","FINANCE":"फाइनेंस","STEEL":"स्टील",
    "MOTORS":"मोटर्स","TECHNOLOGIES":"टेक्नोलॉजीज",
    "AND":"एंड","&":"एंड","SERVICES":"सर्विसेज",
    "PHARMA":"फार्मा","CEMENT":"सीमेंट","OIL":"ऑयल",
    "GAS":"गैस","TELECOM":"टेलीकॉम","GROUP":"ग्रुप",
    "CHEMICALS":"केमिकल्स","NATIONAL":"नेशनल",
    "CORPORATION":"कॉर्पोरेशन","MEDIA":"मीडिया",
    "HEALTHCARE":"हेल्थकेयर","CAPITAL":"कैपिटल",
    "AUTO":"ऑटो","ELECTRIC":"इलेक्ट्रिक",
    "ELECTRONICS":"इलेक्ट्रॉनिक्स",
    "CONSTRUCTION":"कंस्ट्रक्शन",
}
PR = {
    'A':'ए','B':'ब','C':'क','D':'ड','E':'इ','F':'फ',
    'G':'ग','H':'ह','I':'इ','J':'ज','K':'क','L':'ल',
    'M':'म','N':'न','O':'ओ','P':'प','Q':'क','R':'र',
    'S':'स','T':'ट','U':'य','V':'व','W':'व','X':'क्स',
    'Y':'य','Z':'ज'
}
NSE_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"


# ── HELPERS ────────────────────────────────────────────────────────────────────
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
    sutra = SUTRA_MAP.get((asum + tval) % 9, "")
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
            " ✅GOOD" if tc%9 in(2,4,6,8,0) else " ⚠️CAUTION")
    else:
        tara = "N/A"
    S = "─" * 30
    return "\n".join([
        S,
        "🕉  SUTRA   : " + sutra,
        "🔢 NAVAANK : " + str(nv),
        "🪐 GRAHA   : " + g[0],
        S,
        "📈 MARKET FORECAST",
        "   Signal   : " + g[1],
        "   Strength : " + bars.get(g[2],"") + " " + str(g[2]) + "/5",
        "   Sectors  : " + g[3],
        "   Hold For : " + g[4],
        "   Caution  : " + g[5],
        "   Best Day : " + g[6],
        S,
        "🌟 VEDIC TIMING",
        "   Date      : " + wday + " " + today.strftime("%d-%m-%Y"),
        "   Nakshatra : " + nak,
        "   Tara Bala : " + tara,
        S,
        "⚖️  Research only. Not SEBI advice.",
    ])


# ── MAIN ───────────────────────────────────────────────────────────────────────
def main(page: ft.Page):
    try:
        page.title   = "Bhoovalaya Oracle"
        page.bgcolor = "#0A1628"
        page.padding = 10
        page.scroll  = "auto"

        # Show title immediately
        page.add(ft.Container(
            content=ft.Text(
                "🔮 BHOOVALAYA STOCK ORACLE",
                size=22,
                color="#FFFFFF",
                weight="bold",
            ),
            bgcolor="#1A237E",
            padding=12,
            border_radius=8,
        ))
        page.add(ft.Container(
            content=ft.Text(
                "Vedic Akshara + Financial Astrology",
                size=14,
                color="#FFFFFF",
            ),
            bgcolor="#283593",
            padding=8,
            border_radius=6,
        ))
        page.add(ft.Divider(height=6))
        page.update()

        # ── DB SETUP ───────────────────────────────────────────────────────────
        storage = os.getenv("FLET_APP_STORAGE_DATA", ".")
        db_path = os.path.join(storage, "bhuvalaya.db")
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("""CREATE TABLE IF NOT EXISTS stocks(
                symbol TEXT PRIMARY KEY, eng TEXT, hindi TEXT,
                ldate TEXT, asum INTEGER, breakdown TEXT)""")
            conn.commit()
            conn.close()
        except Exception as dbe:
            page.add(ft.Text(
                "DB Error: " + str(dbe),
                size=14, color="#D32F2F"))
            page.update()

        def db_count():
            try:
                return sqlite3.connect(db_path).execute(
                    "SELECT COUNT(*) FROM stocks").fetchone()[0]
            except: return 0

        # ── STATUS BANNER ──────────────────────────────────────────────────────
        status_text = ft.Text(
            "Checking database...",
            size=15,
            color="#FFFFFF",
            weight="bold",
        )
        status_box = ft.Container(
            content=status_text,
            bgcolor="#1976D2",
            padding=10,
            border_radius=6,
        )

        prg_bar = ft.ProgressBar(
            value=0,
            visible=False,
            color="#FF6F00",
            bgcolor="#EEEEEE",
        )

        prg_text = ft.Text(
            "",
            size=15,
            color="#FFD600",
            weight="bold",
        )

        # ── SEARCH BOX ─────────────────────────────────────────────────────────
        fld_search = ft.TextField(
            label="NSE Stock Symbol or Name",
            label_style=ft.TextStyle(
                size=15, color="#1565C0"),
            hint_text="Example: RELIANCE or TCS",
            hint_style=ft.TextStyle(
                size=14, color="#757575"),
            value="RELIANCE",
            text_size=18,
            text_style=ft.TextStyle(
                size=18, color="#000000", weight="bold"),
            border_color="#1565C0",
            focused_border_color="#0D47A1",
            border_width=2,
            focused_border_width=3,
            bgcolor="#F3F6FF",
            cursor_color="#1565C0",
        )

        # ── RESULT BOX ─────────────────────────────────────────────────────────
        result_text = ft.Text(
            "",
            size=16,
            color="#FFFFFF",
            selectable=True,
            font_family="monospace",
        )
        result_box = ft.Container(
            content=result_text,
            bgcolor="#0D1B3E",
            padding=14,
            border_radius=8,
            border=ft.Border(
                top=ft.BorderSide(2, "#42A5F5"),
                bottom=ft.BorderSide(2, "#42A5F5"),
                left=ft.BorderSide(2, "#42A5F5"),
                right=ft.BorderSide(2, "#42A5F5"),
            ),
            visible=False,
        )

        # ── HELPERS ────────────────────────────────────────────────────────────
        def set_status(msg, color="#1976D2"):
            status_text.value = msg
            status_box.bgcolor = color
            page.update()

        def set_prg(pct, msg=""):
            prg_bar.visible = True
            prg_bar.value   = pct
            prg_text.value  = msg
            page.update()

        def hide_prg():
            prg_bar.visible = False
            prg_text.value  = ""
            page.update()

        def set_result(txt):
            result_text.value = txt
            result_box.visible = bool(txt)
            page.update()

        # ── SEARCH ─────────────────────────────────────────────────────────────
        def on_search(e):
            try:
                q = fld_search.value.strip().upper()
                if not q:
                    set_status(
                        "Please enter a stock symbol.", "#D32F2F")
                    return
                set_status("Searching: " + q + " ...", "#1565C0")
                if db_count() < 5:
                    set_status(
                        "Database empty! Tap BUILD DATABASE.",
                        "#D32F2F")
                    set_result(
                        "DATABASE IS EMPTY\n\n"
                        "Tap orange BUILD DATABASE button.\n"
                        "Needs internet. Takes 5-15 minutes.\n\n"
                        "After build, search any NSE symbol.")
                    return
                conn = sqlite3.connect(db_path)
                row  = conn.execute(
                    "SELECT * FROM stocks "
                    "WHERE symbol LIKE ? OR eng LIKE ?",
                    ("%" + q + "%", "%" + q + "%")
                ).fetchone()
                conn.close()
                if row:
                    sym, eng, hi, ldt, asum, bk = row
                    ldate = parse_dt(ldt)
                    today = datetime.now()
                    days  = (today - ldate).days if ldate else 0
                    tval  = days % 730
                    rep   = make_report(asum, tval, ldate)
                    set_status("✅ Found: " + sym, "#2E7D32")
                    set_result("\n".join([
                        "━" * 30,
                        "📊 SYMBOL  : " + sym,
                        "🏢 COMPANY : " + eng,
                        "🕉  HINDI   : " + hi,
                        "📅 LISTED  : " + ldt,
                        "━" * 30,
                        "🧮 AKSHARA SUM  = " + str(asum),
                        "⏳ TEMPORAL MOD = " + str(tval),
                        "🌀 COMBINED VIB = " + str(asum + tval),
                        "🔢 NAVAANK      = " + str((asum%9) or 9),
                        "",
                        rep,
                    ]))
                else:
                    set_status(
                        "❌ Not found: " + q, "#D32F2F")
                    set_result(
                        "'" + q + "' NOT FOUND\n\n"
                        "Try these examples:\n"
                        "  RELIANCE\n  TCS\n  SBIN\n"
                        "  INFY\n  WIPRO\n  ITC\n  LT\n"
                        "  NTPC\n  ONGC\n  MARUTI")
            except Exception as ex:
                set_status("Search error!", "#D32F2F")
                set_result("ERROR: " + str(ex))

        # ── BUILD ──────────────────────────────────────────────────────────────
        def on_build(e):
            def worker():
                try:
                    if not REQUESTS_OK:
                        set_status(
                            "requests module missing!", "#D32F2F")
                        set_result(
                            "BUILD FAILED\n\n"
                            "requests module not available.\n"
                            "Reinstall the app.")
                        return
                    set_status(
                        "Step 1/4: Connecting to NSE...", "#E65100")
                    set_prg(0.02,
                        "Connecting to NSE India server...")
                    set_result(
                        "BUILD STARTED\n\n"
                        "Connecting to NSE India...\n"
                        "Please keep app open.\n"
                        "Do not press back button.\n\n"
                        "Progress bar shows % complete.")
                    hdrs = {"User-Agent": "Mozilla/5.0"}
                    resp = requests.get(
                        NSE_URL, headers=hdrs, timeout=60)
                    resp.raise_for_status()
                    rows = list(csv.DictReader(io.StringIO(
                        resp.content.decode(
                            "utf-8", errors="ignore"))))
                    total = len(rows)
                    set_status(
                        "Step 2/4: Got "
                        + str(total) + " stocks!", "#E65100")
                    set_prg(0.10,
                        "Downloaded " + str(total)
                        + " stocks. Translating to Hindi...")
                    set_result(
                        "BUILD IN PROGRESS\n\n"
                        "Downloaded: "
                        + str(total) + " NSE stocks\n\n"
                        "Now translating to Hindi\n"
                        "and calculating Akshara.\n\n"
                        "Progress bar filling above.\n"
                        "Takes 5-15 minutes.\n"
                        "Please wait...")
                    conn2  = sqlite3.connect(db_path)
                    cur    = conn2.cursor()
                    done   = 0
                    for i, row in enumerate(rows):
                        nm = {
                            k.strip().upper():
                            (v.strip() if v else "")
                            for k, v in row.items()
                        }
                        sym = nm.get("SYMBOL","").strip()
                        eng = nm.get("NAME OF COMPANY",
                              nm.get("COMPANY NAME","")).strip()
                        ldt = nm.get("DATE OF LISTING",
                                     "01-01-2000").strip()
                        if not sym or sym.lower()=="symbol":
                            continue
                        hi       = get_hindi(sym, eng)
                        asum, bk = calc(hi)
                        cur.execute(
                            "INSERT OR REPLACE INTO stocks "
                            "VALUES(?,?,?,?,?,?)",
                            (sym,eng,hi,ldt,asum,bk))
                        done += 1
                        if i % 25 == 0:
                            conn2.commit()
                            pct = 0.10 + (i/max(total,1)) * 0.90
                            set_status(
                                "Processing "
                                + str(i) + "/" + str(total)
                                + " — " + sym, "#E65100")
                            set_prg(pct,
                                str(int(pct*100))
                                + "% done — " + sym)
                    conn2.commit()
                    conn2.close()
                    set_prg(1.0,
                        "✅ Complete! "
                        + str(done) + " stocks ready!")
                    set_status(
                        "✅ Ready! " + str(done) + " stocks!",
                        "#2E7D32")
                    set_result(
                        "✅ BUILD COMPLETE!\n\n"
                        "Total stocks: " + str(done) + "\n\n"
                        "Now search any symbol:\n"
                        "  RELIANCE\n  TCS\n  SBIN\n"
                        "  INFY\n  WIPRO\n  ITC")
                except Exception as ex:
                    hide_prg()
                    set_status(
                        "❌ Build failed! Check internet.",
                        "#D32F2F")
                    set_result(
                        "BUILD FAILED\n\n"
                        "Error: " + str(ex) + "\n\n"
                        "Causes:\n"
                        "1. No internet connection\n"
                        "2. NSE server not responding\n\n"
                        "Turn on internet and try again.")
            set_status("Starting build...", "#E65100")
            set_result(
                "PREPARING BUILD...\n\n"
                "Connecting to internet.\n"
                "Please wait a moment...")
            threading.Thread(target=worker, daemon=True).start()

        # ── BUTTONS ────────────────────────────────────────────────────────────
        btn_search = ft.ElevatedButton(
            text="🔍  SEARCH AND CALCULATE",
            bgcolor="#2E7D32",
            color="#FFFFFF",
            on_click=on_search,
            height=54,
            style=ft.ButtonStyle(
                text_style=ft.TextStyle(
                    size=17, weight="bold"),
            ),
        )

        btn_build = ft.ElevatedButton(
            text="🔄  BUILD DATABASE  (first time)",
            bgcolor="#E65100",
            color="#FFFFFF",
            on_click=on_build,
            height=54,
            style=ft.ButtonStyle(
                text_style=ft.TextStyle(
                    size=16, weight="bold"),
            ),
        )

        # ── ADD TO PAGE ────────────────────────────────────────────────────────
        page.add(status_box)
        page.add(prg_bar)
        page.add(prg_text)
        page.add(ft.Divider(height=6))
        page.add(ft.Text(
            "Enter Stock Symbol:",
            size=17, color="#E3F2FD", weight="bold"))
        page.add(fld_search)
        page.add(btn_search)
        page.add(ft.Divider(height=10))
        page.add(ft.Container(
            content=ft.Text(
                "FIRST TIME SETUP — Build Database",
                size=16, color="#FFFFFF", weight="bold"),
            bgcolor="#B71C1C",
            padding=8, border_radius=6))
        page.add(ft.Text(
            "Tap below to download all NSE stocks (needs internet):",
            size=15, color="#B3E5FC"))
        page.add(btn_build)
        page.add(ft.Divider(height=10))
        page.add(result_box)
        page.update()

        # ── STARTUP ────────────────────────────────────────────────────────────
        n = db_count()
        if n < 5:
            set_status(
                "⚠️  No database. Tap BUILD DATABASE.",
                "#C62828")
            set_result(
                "✅ APP IS WORKING!\n\n"
                "Requests: "
                + ("OK" if REQUESTS_OK else "MISSING") + "\n\n"
                "FIRST TIME SETUP:\n"
                "1. Turn on mobile internet\n"
                "2. Tap orange BUILD DATABASE\n"
                "3. Wait 5 to 15 minutes\n"
                "4. Search any NSE symbol\n\n"
                "The database downloads ~2500\n"
                "NSE stocks with Hindi names.")
        else:
            set_status(
                "✅ Ready — " + str(n) + " stocks loaded!",
                "#2E7D32")
            set_result(
                "✅ WELCOME BACK!\n\n"
                + str(n) + " stocks in database.\n\n"
                "Search examples:\n"
                "  RELIANCE\n  TCS\n  SBIN\n"
                "  INFY\n  WIPRO\n  ITC\n  LT\n\n"
                "Type symbol and tap SEARCH.")

    except Exception as err:
        try:
            page.controls.clear()
            page.add(ft.Container(
                content=ft.Text(
                    "STARTUP ERROR:\n" + str(err),
                    size=15, color="#FFFFFF",
                    selectable=True),
                bgcolor="#D32F2F",
                padding=16, border_radius=8))
            page.update()
        except: pass


ft.app(target=main)
