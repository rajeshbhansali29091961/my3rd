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
    "NTPC":"राष्ट्रीय ताप विद्युत निगम","BPCL":"भारत पेट्रोलियम",
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
    "INFRASTRUCTURE":"इन्फ्रास्ट्रक्चर","AUTO":"ऑटो",
    "AUTOMOBILE":"ऑटोमोबाइल","ELECTRIC":"इलेक्ट्रिक",
    "ELECTRONICS":"इलेक्ट्रॉनिक्स","CONSTRUCTION":"कंस्ट्रक्शन",
}
PR = {
    'A':'ए','B':'ब','C':'क','D':'ड','E':'इ','F':'फ',
    'G':'ग','H':'ह','I':'इ','J':'ज','K':'क','L':'ल',
    'M':'म','N':'न','O':'ओ','P':'प','Q':'क','R':'र',
    'S':'स','T':'ट','U':'य','V':'व','W':'व','X':'क्स',
    'Y':'य','Z':'ज'
}
NSE_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"


# ── HELPER FUNCTIONS ───────────────────────────────────────────────────────────
def parse_dt(s):
    if not s: return None
    for f in ("%d-%m-%Y","%Y-%m-%d","%d/%m/%Y","%d-%b-%Y"):
        try: return datetime.strptime(s.strip(), f)
        except: pass
    return None

def get_hindi(sym, eng):
    if sym in CURATED:
        return CURATED[sym]
    if not REQUESTS_OK:
        return " ".join(
            WD.get(w.strip("&.,()-/"),
            "".join(PR.get(c,"") for c in w.strip("&.,()-/").upper()))
            for w in eng.split())
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
        if cw in WD:
            out.append(WD[cw])
            continue
        try:
            r = requests.get(
                "https://inputtools.google.com/request?text="
                + cw + "&ime=transliteration_en_hi&num=1",
                timeout=4).json()
            out.append(r[1][0][1][0] if r[0] == "SUCCESS"
                       else "".join(PR.get(c,"") for c in cw))
        except:
            out.append("".join(PR.get(c,"") for c in cw))
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
    bars  = {1:"*----",2:"**---",3:"***--",4:"****-",5:"*****"}
    if ldate:
        tc = ((today.timetuple().tm_yday -
               ldate.timetuple().tm_yday) % 27) + 1
        tn = ["जन्म","सम्पत","विपत","क्षेम","प्रत्यरि",
              "साधक","वध","मित्र","परम-मित्र"]
        tara = tn[(tc-1)%9] + (
            " GOOD" if tc % 9 in (2,4,6,8,0) else " CAUTION")
    else:
        tara = "N/A"
    S = "=" * 28
    return "\n".join([
        S,
        "SUTRA   : " + sutra,
        "NAVAANK : " + str(nv),
        "GRAHA   : " + g[0],
        S,
        "MARKET FORECAST:",
        "  Signal  : " + g[1],
        "  Strength: " + bars.get(g[2],"") + "  " + str(g[2]) + "/5",
        "  Sectors : " + g[3],
        "  Hold    : " + g[4],
        "  Caution : " + g[5],
        "  Best Day: " + g[6],
        S,
        "VEDIC TIMING:",
        "  Date     : " + wday + " " + today.strftime("%d-%m-%Y"),
        "  Nakshatra: " + nak,
        "  Tara Bala: " + tara,
        S,
        "Research only. Not SEBI advice.",
    ])


# ── MAIN APP ───────────────────────────────────────────────────────────────────
def main(page: ft.Page):
    try:
        # ── PAGE SETUP ─────────────────────────────────────────────────────────
        page.title   = "Bhoovalaya Oracle"
        page.bgcolor = "#FFFFFF"
        page.padding = 8
        page.scroll  = "auto"

        # Show immediately so user knows app started
        page.add(ft.Text(
            "BHOOVALAYA STOCK ORACLE",
            size=18, color="blue", weight="bold"))
        page.add(ft.Text(
            "Vedic Akshara + Financial Astrology",
            size=11, color="gray"))
        page.add(ft.Divider(height=4))
        page.update()

        # ── DATABASE SETUP ─────────────────────────────────────────────────────
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
            page.add(ft.Text("DB init error: " + str(dbe),
                             color="red", size=12))
            page.update()

        def db_count():
            try:
                return sqlite3.connect(db_path).execute(
                    "SELECT COUNT(*) FROM stocks").fetchone()[0]
            except:
                return 0

        # ── WIDGETS ────────────────────────────────────────────────────────────
        lbl_status = ft.Text(
            "Checking database...",
            size=13, color="blue", weight="bold")

        prg_bar = ft.ProgressBar(
            value=0, visible=False, color="orange")

        lbl_prg = ft.Text(
            "", size=11, color="orange", italic=True)

        fld_search = ft.TextField(
            label="NSE Stock Symbol or Name",
            hint_text="Example: RELIANCE",
            value="RELIANCE",
            text_size=14)

        lbl_result = ft.Text(
            "", size=12, selectable=True,
            font_family="monospace")

        # Add widgets to page one by one
        page.add(lbl_status)
        page.add(prg_bar)
        page.add(lbl_prg)
        page.add(ft.Divider(height=4))
        page.add(ft.Text(
            "Enter Stock Symbol:",
            size=13, weight="bold"))
        page.add(fld_search)
        page.update()

        # ── HELPERS ────────────────────────────────────────────────────────────
        def set_status(msg, color="blue"):
            lbl_status.value = msg
            lbl_status.color = color
            page.update()

        def set_prg(pct, msg=""):
            prg_bar.visible = True
            prg_bar.value   = pct
            lbl_prg.value   = msg
            page.update()

        def hide_prg():
            prg_bar.visible = False
            lbl_prg.value   = ""
            page.update()

        def set_result(txt):
            lbl_result.value = txt
            page.update()

        # ── SEARCH ─────────────────────────────────────────────────────────────
        def on_search(e):
            try:
                q = fld_search.value.strip().upper()
                if not q:
                    set_status("Please enter a stock symbol.", "red")
                    return
                set_status("Searching for: " + q + " ...", "blue")
                if db_count() < 5:
                    set_status(
                        "Database empty! Tap BUILD DATABASE.", "red")
                    set_result(
                        "DATABASE IS EMPTY\n\n"
                        "Tap orange BUILD DATABASE button.\n"
                        "Needs internet. Takes 5-15 mins.\n\n"
                        "After build completes,\n"
                        "search any NSE stock symbol.")
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
                    set_status("Found: " + sym, "green")
                    set_result("\n".join([
                        "=" * 28,
                        "SYMBOL  : " + sym,
                        "COMPANY : " + eng,
                        "HINDI   : " + hi,
                        "LISTED  : " + ldt,
                        "=" * 28,
                        "AKSHARA SUM  = " + str(asum),
                        "TEMPORAL MOD = " + str(tval),
                        "COMBINED VIB = " + str(asum + tval),
                        "NAVAANK      = " + str((asum % 9) or 9),
                        "",
                        rep,
                    ]))
                else:
                    set_status("Not found: " + q, "red")
                    set_result(
                        "'" + q + "' NOT FOUND\n\n"
                        "Try these examples:\n"
                        "  RELIANCE\n  TCS\n  SBIN\n"
                        "  INFY\n  WIPRO\n  ITC\n  LT")
            except Exception as ex:
                set_status("Search error!", "red")
                set_result("ERROR: " + str(ex))

        # ── BUILD DATABASE ──────────────────────────────────────────────────────
        def on_build(e):
            def worker():
                try:
                    if not REQUESTS_OK:
                        set_status("requests module missing!", "red")
                        set_result(
                            "BUILD FAILED\n\n"
                            "requests module not available.\n"
                            "Check pyproject.toml has:\n"
                            "requests==2.32.3 in dependencies.")
                        return

                    set_status(
                        "Step 1/4: Connecting to NSE...", "orange")
                    set_prg(0.02, "Connecting to NSE India server...")
                    set_result(
                        "BUILD STARTED\n\n"
                        "Step 1: Connecting to NSE India\n"
                        "Please keep app open.\n"
                        "Do not press back button.\n\n"
                        "Progress bar shows % done.")

                    hdrs = {"User-Agent": "Mozilla/5.0"}
                    resp = requests.get(
                        NSE_URL, headers=hdrs, timeout=60)
                    resp.raise_for_status()

                    rows = list(csv.DictReader(io.StringIO(
                        resp.content.decode("utf-8", errors="ignore"))))
                    total = len(rows)

                    set_status(
                        "Step 2/4: Downloaded "
                        + str(total) + " stocks.", "orange")
                    set_prg(0.10,
                        "Downloaded " + str(total)
                        + " stocks. Translating...")
                    set_result(
                        "BUILD IN PROGRESS\n\n"
                        "Downloaded: " + str(total) + " stocks\n\n"
                        "Now translating names to Hindi\n"
                        "and calculating Akshara values.\n\n"
                        "This takes 5-15 minutes.\n"
                        "Progress bar updating above.\n"
                        "Please wait...")

                    conn2  = sqlite3.connect(db_path)
                    cur    = conn2.cursor()
                    done   = 0

                    for i, row in enumerate(rows):
                        nm = {
                            k.strip().upper(): (v.strip() if v else "")
                            for k, v in row.items()
                        }
                        sym = nm.get("SYMBOL", "").strip()
                        eng = nm.get("NAME OF COMPANY",
                              nm.get("COMPANY NAME", "")).strip()
                        ldt = nm.get("DATE OF LISTING",
                                     "01-01-2000").strip()
                        if not sym or sym.lower() == "symbol":
                            continue
                        hi       = get_hindi(sym, eng)
                        asum, bk = calc(hi)
                        cur.execute(
                            "INSERT OR REPLACE INTO stocks "
                            "VALUES(?,?,?,?,?,?)",
                            (sym, eng, hi, ldt, asum, bk))
                        done += 1
                        if i % 25 == 0:
                            conn2.commit()
                            pct = 0.10 + (i / max(total, 1)) * 0.90
                            set_status(
                                "Processing "
                                + str(i) + "/" + str(total)
                                + " - " + sym, "orange")
                            set_prg(pct,
                                str(int(pct * 100))
                                + "% done - " + sym)

                    conn2.commit()
                    conn2.close()
                    set_prg(1.0,
                        "Complete! " + str(done) + " stocks done.")
                    set_status(
                        "Ready! " + str(done) + " stocks.", "green")
                    set_result(
                        "BUILD COMPLETE!\n\n"
                        "Total stocks: " + str(done) + "\n\n"
                        "Search examples:\n"
                        "  RELIANCE\n  TCS\n  SBIN\n  INFY\n  WIPRO")

                except Exception as ex:
                    hide_prg()
                    set_status(
                        "Build failed! Check internet.", "red")
                    set_result(
                        "BUILD FAILED\n\n"
                        "Error: " + str(ex) + "\n\n"
                        "Possible causes:\n"
                        "1. No internet connection\n"
                        "2. NSE server not responding\n"
                        "3. App has no internet permission\n\n"
                        "Check internet is ON\n"
                        "then tap BUILD DATABASE again.")

            set_status("Starting build...", "orange")
            set_result(
                "PREPARING BUILD...\n\n"
                "Connecting to internet.\n"
                "Please wait a moment...")
            threading.Thread(target=worker, daemon=True).start()

        # ── BUTTONS ────────────────────────────────────────────────────────────
        btn_search = ft.ElevatedButton(
            text="SEARCH AND CALCULATE",
            bgcolor="green",
            color="white",
            on_click=on_search,
            height=50)

        btn_build = ft.ElevatedButton(
            text="BUILD DATABASE  (first time)",
            bgcolor="orange",
            color="white",
            on_click=on_build,
            height=50)

        # Add remaining widgets
        page.add(btn_search)
        page.add(ft.Divider(height=8))
        page.add(ft.Text(
            "First time only - build database:",
            size=13, weight="bold"))
        page.add(btn_build)
        page.add(ft.Divider(height=8))
        page.add(ft.Text("Result:", size=13, weight="bold"))
        page.add(lbl_result)
        page.update()

        # ── STARTUP MESSAGE ────────────────────────────────────────────────────
        n = db_count()
        if n < 5:
            set_status(
                "No database found. Tap BUILD DATABASE.", "red")
            set_result(
                "WELCOME - APP IS WORKING!\n\n"
                "Requests module: "
                + ("OK" if REQUESTS_OK else "MISSING") + "\n\n"
                "FIRST TIME SETUP:\n"
                "1. Turn on mobile internet\n"
                "2. Tap orange BUILD DATABASE\n"
                "3. Wait 5-15 minutes\n"
                "4. Search any NSE symbol\n\n"
                "If you see this message\n"
                "the APK is working correctly!")
        else:
            set_status(
                "Ready. " + str(n) + " stocks loaded.", "green")
            set_result(
                "WELCOME BACK!\n\n"
                + str(n) + " stocks in database.\n\n"
                "Search examples:\n"
                "  RELIANCE\n  TCS\n  SBIN\n"
                "  INFY\n  WIPRO\n  ITC\n  LT\n\n"
                "Type symbol and tap SEARCH.")

    except Exception as err:
        try:
            page.controls.clear()
            page.add(ft.Text(
                "STARTUP ERROR - PLEASE REPORT:",
                size=16, color="red", weight="bold"))
            page.add(ft.Text(
                str(err),
                size=13, color="red", selectable=True))
            page.update()
        except:
            pass


ft.app(target=main)
