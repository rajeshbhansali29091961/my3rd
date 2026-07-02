import os
import sqlite3
import threading
import requests
import time
from datetime import datetime
import flet as ft

# --- BHOOVALAYA CONSTANTS (1-64 WEIGHT MATRIX) ---
AKSHARA_VALS = {
    'अ': 1, 'आ': 2, 'इ': 3, 'ई': 4, 'उ': 5, 'ऊ': 6, 'ए': 7, 'ऐ': 8, 'ओ': 9, 'औ': 10,
    'क': 11, 'ख': 12, 'ग': 13, 'घ': 14, 'ङ': 15, 'च': 16, 'छ': 17, 'ज': 18, 'झ': 19, 'ञ': 20,
    'ट': 21, 'ठ': 22, 'ड': 23, 'ढ': 24, 'ण': 25, 'त': 26, 'थ': 27, 'द': 28, 'ध': 29, 'न': 30,
    'प': 31, 'फ': 32, 'ब': 33, 'भ': 34, 'म': 35, 'य': 36, 'र': 37, 'ल': 38, 'व': 39, 'श': 40,
    'ष': 41, 'स': 42, 'ह': 43, 'ि': 2, 'ा': 2, 'े': 7, 'ै': 8, 'ो': 9, 'ौ': 10, '्': 0, 'ं': 1
}

SUTRA_MAP = {
    0: "अनंत (Ananta)", 1: "शक्ति (Shakti)", 2: "ज्ञान (Gnana)",
    3: "धर्म (Dharma)", 4: "वैराग्य (Vairagya)", 5: "ऐश्वर्य (Aishwarya)",
    6: "यश (Yashas)", 7: "श्री (Shree)", 8: "वीर्य (Veerya)"
}

EXCHANGE_DICTIONARY = {
    "LTD": "लिमिटेड", "LIMITED": "लिमिटेड", "INDUSTRIES": "इंडस्ट्रीज",
    "BANK": "बैंक", "STEEL": "स्टील", "INFRASTRUCTURE": "इन्फ्रास्ट्रक्चर",
    "FINANCE": "फाइनेंस", "INDIA": "इंडिया", "ENTERPRISES": "एंटरप्राइजेज",
    "POWER": "पावर", "ENERGY": "एनर्जी", "MOTOR": "मोटर", "MOTORS": "मोटर्स"
}


def phonetic_transliterate(text):
    words = text.upper().split()
    transliterated_words = []
    for word in words:
        if word in EXCHANGE_DICTIONARY:
            transliterated_words.append(EXCHANGE_DICTIONARY[word])
            continue
        try:
            url = f"https://inputtools.google.com/request?text={word}&ime=transliteration_en_hi&num=1"
            response = requests.get(url, timeout=5).json()
            if response[0] == "SUCCESS":
                trans_word = response[1][0][1][0]
                transliterated_words.append(trans_word)
            else:
                transliterated_words.append(word)
        except Exception:
            fallback = ""
            rules = {'A': 'ए', 'B': 'ब', 'C': 'क', 'D': 'ड', 'E': 'इ', 'F': 'फ', 'G': 'ग', 'H': 'ह',
                     'I': 'इ', 'J': 'ज', 'K': 'क', 'L': 'ल', 'M': 'म', 'N': 'न', 'O': 'ओ', 'P': 'प',
                     'Q': 'क', 'R': 'र', 'S': 'स', 'T': 'ट', 'U': 'य', 'V': 'व', 'W': 'व', 'X': 'क्स',
                     'Y': 'य', 'Z': 'ज'}
            for char in word:
                fallback += rules.get(char, '')
            transliterated_words.append(fallback if fallback else word)
    return " ".join(transliterated_words)


def parse_date_safely(date_str):
    """Pure-Python date parser (no pandas). Returns datetime or None."""
    if not date_str:
        return None
    date_str = date_str.strip()
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%b-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def main(page: ft.Page):
    page.title = "BHOOVALAYA PHONETIC ENGINE"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.scroll = "adaptive"

    # On mobile, page.client_storage / app storage paths differ from desktop.
    # flet exposes the writable app data dir via os.getenv("FLET_APP_STORAGE_DATA")
    # and the bundled read-only assets dir via os.getenv("FLET_ASSETS_DIR").
    app_storage = os.getenv("FLET_APP_STORAGE_DATA", ".")
    assets_dir = os.getenv("FLET_ASSETS_DIR", "assets")
    db_path = os.path.join(app_storage, "bhuvalaya_oracle.db")
    bundled_db = os.path.join(assets_dir, "bhuvalaya_oracle.db")

    # First launch: copy the pre-built, pre-populated database from the
    # bundled read-only asset into the app's writable storage directory.
    if not os.path.exists(db_path) and os.path.exists(bundled_db):
        import shutil
        shutil.copyfile(bundled_db, db_path)

    # Ensure table exists even if no bundled asset was found (fresh/empty DB fallback)
    conn = sqlite3.connect(db_path)
    conn.execute('''CREATE TABLE IF NOT EXISTS stocks (
                    symbol TEXT PRIMARY KEY, eng_name TEXT, hindi_name TEXT,
                    listing_date TEXT, akshara_sum INTEGER, breakdown TEXT)''')
    conn.close()

    # --- MAIN INTERFACE WIDGET STRUCTS ---
    search_box = ft.TextField(label="Enter Stock Name or Symbol", value="RELIANCE", expand=True)
    output_text = ft.Text(value="Welcome. Click 'Phonetic Sync Engine Data' to populate your workspace database.", size=15, selectable=True)

    # Data Form Inputs for CRUD operations
    input_sym = ft.TextField(label="Symbol ID")
    input_eng = ft.TextField(label="English Standard Name")
    input_hindi = ft.TextField(label="Hindi Phonetic Name")
    input_date = ft.TextField(label="Listing Date (DD-MM-YYYY)")
    crud_status = ft.Text(value="Status: Idle", italic=True, color="gray")

    # Grid Table View for Workspace Browser Rows
    data_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Symbol")),
            ft.DataColumn(ft.Text("Hindi Phonetic Name")),
        ],
        rows=[]
    )

    def refresh_table():
        data_table.rows.clear()
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT symbol, hindi_name FROM stocks ORDER BY symbol ASC LIMIT 50")
            for row in cursor.fetchall():
                def make_select_handler(sym=row[0]):
                    return lambda e: populate_fields(sym)

                data_table.rows.append(
                    ft.DataRow(
                        cells=[ft.DataCell(ft.Text(row[0])), ft.DataCell(ft.Text(row[1]))],
                        on_select_changed=make_select_handler()
                    )
                )
            conn.close()
            page.update()
        except Exception as ex:
            print("Table pipeline refresh warning:", ex)

    def populate_fields(symbol):
        conn = sqlite3.connect(db_path)
        res = conn.cursor().execute("SELECT * FROM stocks WHERE symbol = ?", (symbol,)).fetchone()
        conn.close()
        if res:
            input_sym.value = res[0]
            input_sym.disabled = True
            input_eng.value = res[1]
            input_hindi.value = res[2]
            input_date.value = res[3]
            crud_status.value = f"Selected entry: {res[0]}"
            page.update()

    def perform_search(e):
        query = search_box.value.strip().upper()
        if not query:
            return

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM stocks WHERE symbol LIKE ? OR eng_name LIKE ?", (f'%{query}%', f'%{query}%'))
        res = cursor.fetchone()
        conn.close()

        if res:
            sym, eng, hindi, l_date_str, a_sum, breakdown = res
            today = datetime.now()
            l_date = parse_date_safely(l_date_str)
            if l_date:
                days_diff = (today - l_date).days
                date_val = days_diff % 730
            else:
                days_diff, date_val = 0, 0

            total_vib = a_sum + date_val
            sutra = SUTRA_MAP.get(total_vib % 9)

            output_text.value = (
                f"📊 STOCK EXCHANGE SYMBOL: {sym}\n"
                f"🏢 REGISTRATION NAME: {eng}\n"
                f"🕉️  ENTIRE HINDI PHONETIC NAME: {hindi}\n"
                f"📅 LISTED ON EXCHANGE: {l_date_str}\n"
                f"──────────────────────────────────────────────\n"
                f"🧮 STEP 1: ENTIRE HINDI NAME MATH CALCULATION:\n"
                f"   » {breakdown}\n"
                f"   » Total Akshara Sound Weight Value = {a_sum}\n\n"
                f"⏳ STEP 2: TEMPORAL VALUE MATH (Today: {today.strftime('%Y-%m-%d')}):\n"
                f"   » Days running: {days_diff} days elapsed\n"
                f"   » Temporal Formula Mapping (Mod 730) = {date_val}\n\n"
                f"🌀 STEP 3: COMBINED ENGINE VIBRATION VALUE:\n"
                f"   » {a_sum} (Akshara Value) + {date_val} (Temporal Value) = {total_vib}\n"
                f"──────────────────────────────────────────────\n"
                f"✨ SUTRA ORACLE RESULT: {sutra}"
            )
        else:
            output_text.value = "Stock profile not discovered inside the database workspace. Run 'Phonetic Sync Engine Data' first."
        page.update()

    def fetch_nse_equity_list():
        """
        Fetch the NSE equity list without pandas/NseKit.
        Returns a list of dicts: [{'SYMBOL': ..., 'NAME OF COMPANY': ..., 'DATE OF LISTING': ...}, ...]
        Uses NSE's public CSV endpoint directly via requests + csv module.
        """
        import csv
        import io

        url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        text = resp.content.decode("utf-8", errors="ignore")
        reader = csv.DictReader(io.StringIO(text))
        rows = []
        for row in reader:
            normalized = {k.strip().upper(): (v.strip() if v else "") for k, v in row.items()}
            rows.append(normalized)
        return rows

    def sync_logic():
        try:
            rows = fetch_nse_equity_list()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            total = len(rows)
            for idx, row in enumerate(rows):
                sym = str(row.get('SYMBOL', '')).strip()
                eng_name = str(row.get('NAME OF COMPANY', row.get('COMPANY NAME', ''))).strip()
                l_date = str(row.get('DATE OF LISTING', '01-01-2000')).strip()

                if not sym or sym.lower() == 'symbol':
                    continue

                h_phonetic_name = phonetic_transliterate(eng_name)
                a_sum = 0
                steps = []
                for char in h_phonetic_name:
                    w = AKSHARA_VALS.get(char, 0)
                    a_sum += w
                    if w > 0 or char == '्':
                        steps.append(f"{char}({w})")
                    elif char == " ":
                        steps.append("[Space]")

                cursor.execute("INSERT OR REPLACE INTO stocks VALUES (?, ?, ?, ?, ?, ?)",
                               (sym, eng_name, h_phonetic_name, l_date, a_sum, " + ".join(steps)))
                if idx % 10 == 0:
                    conn.commit()
                    output_text.value = f"Phonetic Mapping: {idx}/{total} stocks processed...\nCurrent Stream Track: {h_phonetic_name}"
                    page.update()

            conn.commit()
            conn.close()
            output_text.value = "Sync Complete! Sound vibration weights successfully structured."
            refresh_table()
        except Exception as ex:
            output_text.value = (
                f"Sync Operational Error: {str(ex)}\n\n"
                "Tip: Live NSE sync may be blocked on mobile networks/data plans. "
                "You can alternatively pre-build the database on desktop and bundle it as an asset."
            )
        page.update()

    def start_sync(e):
        output_text.value = "Initializing Engine Sync Pipeline... Establishing safe remote handshakes..."
        page.update()
        threading.Thread(target=sync_logic, daemon=True).start()

    def db_add(e):
        sym, eng, hindi, l_date = input_sym.value.upper(), input_eng.value, input_hindi.value, input_date.value
        if not (sym and eng and hindi):
            return

        a_sum = 0
        steps = []
        for char in hindi:
            w = AKSHARA_VALS.get(char, 0)
            a_sum += w
            if w > 0 or char == '्':
                steps.append(f"{char}({w})")

        try:
            conn = sqlite3.connect(db_path)
            conn.cursor().execute("INSERT INTO stocks VALUES (?, ?, ?, ?, ?, ?)",
                           (sym, eng, hindi, l_date or "01-01-2000", a_sum, " + ".join(steps)))
            conn.commit()
            conn.close()
            crud_status.value = "New record written down successfully!"
            clear_fields(None)
            refresh_table()
        except Exception as ex:
            crud_status.value = str(ex)
        page.update()

    def db_edit(e):
        sym, eng, hindi, l_date = input_sym.value, input_eng.value, input_hindi.value, input_date.value
        if not sym:
            return

        a_sum = 0
        steps = []
        for char in hindi:
            w = AKSHARA_VALS.get(char, 0)
            a_sum += w
            if w > 0 or char == '्':
                steps.append(f"{char}({w})")

        try:
            conn = sqlite3.connect(db_path)
            conn.cursor().execute("UPDATE stocks SET eng_name=?, hindi_name=?, listing_date=?, akshara_sum=?, breakdown=? WHERE symbol=?",
                           (eng, hindi, l_date, a_sum, " + ".join(steps), sym))
            conn.commit()
            conn.close()
            crud_status.value = "Record changes modified successfully!"
            clear_fields(None)
            refresh_table()
        except Exception as ex:
            crud_status.value = str(ex)
        page.update()

    def clear_fields(e):
        input_sym.disabled = False
        input_sym.value = ""
        input_eng.value = ""
        input_hindi.value = ""
        input_date.value = ""
        crud_status.value = "Status: Form Reset Active"
        page.update()

    # --- INTEGRATED NAVIGATION VIEW PANELS ---
    engine_view = ft.Column([
        ft.Text("🔮 BHOOVALAYA ORACLE ENGINE", size=22, weight="bold"),
        ft.Row([search_box, ft.ElevatedButton("Search & Calculate", on_click=perform_search, bgcolor="green", color="white")]),
        ft.ElevatedButton("Phonetic Sync Engine Data", on_click=start_sync, bgcolor="red", color="white"),
        ft.Container(output_text, border=ft.Border.all(1, "gray"), padding=15, border_radius=10, bgcolor="#F5F5F5", expand=True)
    ], expand=True)

    crud_view = ft.Row([
        ft.Column([ft.Text("Records Browser Matrix (Select Row)"), data_table], scroll="always", expand=True),
        ft.VerticalDivider(width=1),
        ft.Column([
            ft.Text("CRUD Workbench Form", size=18, weight="bold"),
            input_sym, input_eng, input_hindi, input_date,
            ft.Row([
                ft.ElevatedButton("➕ Add Row", on_click=db_add, bgcolor="blue", color="white"),
                ft.ElevatedButton("📝 Update", on_click=db_edit, bgcolor="orange", color="white")
            ]),
            ft.ElevatedButton("🧹 Clear Fields", on_click=clear_fields, bgcolor="gray", color="white"),
            crud_status
        ], width=320, scroll="always")
    ], expand=True)

    # --- NATIVE FLUTTER TABS SPECIFICATION MAPPING ---
    app_tabs = ft.Tabs(
        length=2,
        expand=True,
        content=ft.Column(
            expand=True,
            controls=[
                ft.TabBar(
                    tabs=[
                        ft.Tab(label="Oracle View Engine"),
                        ft.Tab(label="Database CRUD Workbench"),
                    ]
                ),
                ft.TabBarView(
                    expand=True,
                    controls=[
                        engine_view,
                        crud_view,
                    ]
                )
            ]
        )
    )

    page.add(app_tabs)
    refresh_table()


ft.app(target=main)
