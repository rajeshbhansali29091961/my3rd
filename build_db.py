"""
build_db.py  — STANDALONE, no flet dependency at all
Run this ONCE on your desktop/Windows to pre-populate
assets/bhuvalaya_oracle.db before pushing to GitHub.

Usage:
    python build_db.py

Requirements:
    pip install requests
    (that's all — no flet, no pandas, no NseKit needed here)
"""

import os
import sqlite3
import csv
import io
import requests

# ── copied directly from main.py so we never import flet ──────────────────────

AKSHARA_VALS = {
    'अ': 1, 'आ': 2, 'इ': 3, 'ई': 4, 'उ': 5, 'ऊ': 6, 'ए': 7, 'ऐ': 8, 'ओ': 9, 'औ': 10,
    'क': 11, 'ख': 12, 'ग': 13, 'घ': 14, 'ङ': 15, 'च': 16, 'छ': 17, 'ज': 18, 'झ': 19, 'ञ': 20,
    'ट': 21, 'ठ': 22, 'ड': 23, 'ढ': 24, 'ण': 25, 'त': 26, 'थ': 27, 'द': 28, 'ध': 29, 'न': 30,
    'प': 31, 'फ': 32, 'ब': 33, 'भ': 34, 'म': 35, 'य': 36, 'र': 37, 'ल': 38, 'व': 39, 'श': 40,
    'ष': 41, 'स': 42, 'ह': 43, 'ि': 2, 'ा': 2, 'े': 7, 'ै': 8, 'ो': 9, 'ौ': 10, '्': 0, 'ं': 1
}

EXCHANGE_DICTIONARY = {
    "LTD": "लिमिटेड", "LIMITED": "लिमिटेड", "INDUSTRIES": "इंडस्ट्रीज",
    "BANK": "बैंक", "STEEL": "स्टील", "INFRASTRUCTURE": "इन्फ्रास्ट्रक्चर",
    "FINANCE": "फाइनेंस", "INDIA": "इंडिया", "ENTERPRISES": "एंटरप्राइजेज",
    "POWER": "पावर", "ENERGY": "एनर्जी", "MOTOR": "मोटर", "MOTORS": "मोटर्स"
}

PHONETIC_FALLBACK = {
    'A': 'ए', 'B': 'ब', 'C': 'क', 'D': 'ड', 'E': 'इ', 'F': 'फ', 'G': 'ग', 'H': 'ह',
    'I': 'इ', 'J': 'ज', 'K': 'क', 'L': 'ल', 'M': 'म', 'N': 'न', 'O': 'ओ', 'P': 'प',
    'Q': 'क', 'R': 'र', 'S': 'स', 'T': 'ट', 'U': 'य', 'V': 'व', 'W': 'व', 'X': 'क्स',
    'Y': 'य', 'Z': 'ज'
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
                transliterated_words.append(response[1][0][1][0])
            else:
                transliterated_words.append(
                    "".join(PHONETIC_FALLBACK.get(c, '') for c in word) or word
                )
        except Exception:
            transliterated_words.append(
                "".join(PHONETIC_FALLBACK.get(c, '') for c in word) or word
            )
    return " ".join(transliterated_words)

# ── NSE fetch ─────────────────────────────────────────────────────────────────

NSE_CSV_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
DB_PATH = os.path.join("assets", "bhuvalaya_oracle.db")


def fetch_nse_equity_list():
    print("Downloading NSE equity list...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/124.0 Safari/537.36"
    }
    resp = requests.get(NSE_CSV_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    text = resp.content.decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    rows = [{k.strip().upper(): (v.strip() if v else "") for k, v in row.items()} for row in reader]
    print(f"Downloaded {len(rows)} equity records.")
    return rows


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    os.makedirs("assets", exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS stocks (
                    symbol       TEXT PRIMARY KEY,
                    eng_name     TEXT,
                    hindi_name   TEXT,
                    listing_date TEXT,
                    akshara_sum  INTEGER,
                    breakdown    TEXT)''')

    rows = fetch_nse_equity_list()
    cursor = conn.cursor()
    total = len(rows)
    success = 0

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

        cursor.execute(
            "INSERT OR REPLACE INTO stocks VALUES (?, ?, ?, ?, ?, ?)",
            (sym, eng_name, h_phonetic_name, l_date, a_sum, " + ".join(steps))
        )
        success += 1

        if idx % 50 == 0:
            conn.commit()
            print(f"  [{idx}/{total}] {sym:15s} → {h_phonetic_name}")

    conn.commit()
    conn.close()

    size_kb = os.path.getsize(DB_PATH) // 1024
    print(f"\n✅ Done! {success} stocks written to {DB_PATH} ({size_kb} KB)")
    print("Next step: git add assets\\bhuvalaya_oracle.db && git commit && git push")


if __name__ == "__main__":
    main()
