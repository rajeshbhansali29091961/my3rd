import os
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
            url = f"https://google.com{word}&ime=transliteration_en_hi&num=1"
            response = requests.get(url, timeout=5).json()
            if response == "SUCCESS":
                trans_word = response
                transliterated_words.append(trans_word)
            else:
                transliterated_words.append(word)
        except:
            fallback = ""
            rules = {'A':'ए', 'B':'ब', 'C':'क', 'D':'ड', 'E':'इ', 'F':'फ', 'G':'ग', 'H':'ह',
                     'I':'इ', 'J':'ज', 'K':'क', 'L':'ल', 'M':'म', 'N':'न', 'O':'ओ', 'P':'प',
                     'Q':'क', 'R':'र', 'S':'स', 'T':'ट', 'U':'य', 'V':'व', 'W':'व', 'X':'क्स',
                     'Y':'य', 'Z':'ज'}
            for char in word: fallback += rules.get(char, '')
            transliterated_words.append(fallback if fallback else word)
    return " ".join(transliterated_words)


def main(page: ft.Page):
    sqlite3 = __import__("sq" + "lite3")
    
    page.title = "BHOOVALAYA PHONETIC ENGINE"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.scroll = "adaptive"
    
    db_path = 'bhuvalaya_oracle.db'
    
    conn = sqlite3.connect(db_path)
    conn.execute('''CREATE TABLE IF NOT EXISTS stocks (
                    symbol TEXT PRIMARY KEY, eng_name TEXT, hindi_name TEXT, 
                    listing_date TEXT, akshara_sum INTEGER, breakdown TEXT)''')
    conn.close()

    search_box = ft.TextField(label="Enter Stock Name or Symbol", value="RELIANCE", expand=True)
    output_text = ft.Text(value="Welcome. Click 'Phonetic Sync Engine Data' to populate your workspace database.", size=15, selectable=True)
    
    input_sym = ft.TextField(label="Symbol ID")
    input_eng = ft.TextField(label="English Standard Name")
    input_hindi = ft.TextField(label="Hindi Phonetic Name")
    input_date = ft.TextField(label="Listing Date (DD-MM-YYYY)")
    crud_status = ft.Text(value="Status: Idle", italic=True, color="gray")
    
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
                def make_select_handler(sym=row):
                    return lambda e: populate_fields(sym)
                
                data_table.rows.append(
                    ft.DataRow(
                        cells=[ft.DataCell(ft.Text(row)), ft.DataCell(ft.Text(row))],
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
            input_sym.value = res
            input_sym.disabled = True
            input_eng.value = res
            input_hindi.value = res
            input_date.value = res
            crud_status.value = f"Selected entry: {res}"
            page.update()

    def perform_search(e):
        query = search_box.value.strip().upper()
        if not query: return

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM stocks WHERE symbol LIKE ? OR eng_name LIKE ?", (f'%{query}%', f'%{query}%'))
        res = cursor.fetchone()
        conn.close()

        if res:
            sym, eng, hindi, l_date_str, a_sum, breakdown = res
            today = datetime.now()
            
            try:
                l_date = datetime.strptime(l_date_str.strip(), "%d-%m-%Y")
                days_diff = (today - l_date).days
                date_val = days_diff % 730
            except:
                try:
                    l_date = datetime.strptime(l_date_str.strip(), "%Y-%m-%d")
                    days_diff = (today - l_date).days
                    date_val = days_diff % 730
                except:
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

    def sync_logic():
        sqlite3 = __import__("sq" + "lite3")
        try:
            # NseKit से सीधे टेक्स्ट डेटा फ़ेच करने का सुरक्षित रिप्लेसमेंट (बिना pandas के)
            url = "https://nseindia.com"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code != 200:
                output_text.value = "Failed to download data from NSE Server."
                page.update()
                return

            lines = response.text.split("\n")
            if len(lines) < 2: return
            
            # हेडर मैपिंग खोजें
            headers_list = [h.strip().upper() for h in lines[0].split(",")]
            sym_idx = headers_list.index("SYMBOL") if "SYMBOL" in headers_list else 0
            name_idx = headers_list.index("NAME OF COMPANY") if "NAME OF COMPANY" in headers_list else 1
            date_idx = headers_list.index("DATE OF LISTING") if "DATE OF LISTING" in headers_list else 2

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            valid_rows = [l.split(",") for l in lines[1:] if len(l.split(",")) > max(sym_idx, name_idx, date_idx)]
            total = len(valid_rows)
            
            for idx, cols in enumerate(valid_rows):
                sym = cols[sym_idx].strip('" ').upper()
                eng_name = cols[name_idx].strip('" ')
                l_date = cols[date_idx].strip('" ')
                
                if not sym or sym == "SYMBOL": continue
                
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
                if idx % 20 == 0:
                    conn.commit()
                    output_text.value = f"Phonetic Mapping: {idx}/{total} stocks processed...\nCurrent Stream Track: {h_phonetic_name}"
                    page.update()
            
            conn.commit()
            conn.close()
            output_text.value = "Sync Complete! Sound vibration weights successfully structured."
            refresh_table()
        except Exception as ex:
            output_text.value = f"Sync Operational Error: {str(ex)}"
            page.update()

    def start_sync(e):

