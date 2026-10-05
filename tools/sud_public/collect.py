"""public.sud.uz ochiq API'sidan sud qarorlarini yig'ish va PDF matnidan
"Инсон" ijtimoiy xizmatlar markazlari / Ijtimoiy himoya milliy agentligi
ishtirok etgan ishlarni ajratib olish.

Ishlatish:
    python tools/sud_public/collect.py list   # ro'yxatni (metama'lumot) yig'ish
    python tools/sud_public/collect.py pdf    # PDF'larni o'qib, kalit so'zlarni qidirish
    python tools/sud_public/collect.py export # topilganlarni CSV'ga chiqarish

Faqat ommaviy e'lon qilingan qarorlar o'qiladi; serverga yuk tushmasligi uchun
so'rovlar cheklangan parallellik va pauza bilan yuboriladi.
"""
import csv
import json
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pymupdf

API = "https://adolatapi1.sud.uz"
START, END = "2026-01-01", "2026-12-31"
ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "sud_public.db"
OUT = ROOT / "data" / "sud_public_topilgan.csv"
WORKERS = 3
PAUSE = 0.3

# (sud turi, toifa id yoki None = barcha toifalar, izoh)
SCOPES = [
    ("ADMINISTRATIVE", None, "Ma'muriy sudlar — barcha ishlar"),
    ("CIVIL", "a176b472-4a66-4ec0-a080-e0551dc1afa0", "Pensiya va ijtimoiy to'lovlarni undirish"),
    ("CIVIL", "fbfda98e-ea00-4e34-bd9c-30a0a6824eff", "Ortiqcha to'langan pensiya/ijtimoiy himoya pulini undirish"),
    ("CIVIL", "9f62e15b-a803-42c8-9c05-84b2def3d0dc", "Fuqaroni muomalaga layoqatsiz deb topish"),
]

PATTERNS = {
    "inson_markazi": re.compile(
        r"[«\"“„]\s*(Инсон|Inson)\s*[»\"”]"
        r"|(Инсон|Inson)\s+(ижтимоий|ijtimoiy)\s+(хизмат|xizmat)"
        r"|(ижтимоий|ijtimoiy)\s+(хизматлар|xizmatlar)\s+(маркази|markazi)", re.I),
    "ijtimoiy_himoya_agentligi": re.compile(
        r"(ижтимоий|ijtimoiy)\s+(ҳимоя|химоя|himoya)\s+(миллий\s+|milliy\s+)?(агентлиг|agentlig)"
        r"|агентство\s+социальной\s+защиты", re.I),
}

RESULTS = {
    "FULFILLED": "Qanoatlantirilgan", "PARTIALLY_FULFILLED": "Qisman qanoatlantirilgan",
    "REFUSED": "Rad etilgan", "CASE_ENDED": "Ish yuritish tugatilgan",
    "LEFT_WITHOUT_CONSIDERATION": "Ko'rmasdan qoldirilgan",
}
INSTANCES = {"FIRST": "Birinchi instansiya", "APPEAL": "Apellyatsiya", "CASSATION": "Kassatsiya",
             "REVISION": "Taftish"}


def db() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS decisions (
      id TEXT PRIMARY KEY, court_type TEXT, scope TEXT, court TEXT, instance TEXT,
      case_number TEXT, category TEXT, judge TEXT, result TEXT, document_type TEXT,
      hearing_date TEXT, pdf_id TEXT, raw TEXT,
      scanned INTEGER DEFAULT 0, matched TEXT, snippet TEXT, text TEXT, error TEXT
    );""")
    return con


def get_json(path: str, params: dict, tries: int = 4):
    url = f"{API}{path}?{urllib.parse.urlencode(params)}"
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            if i == tries - 1:
                raise
            print(f"  qayta urinish ({e})", file=sys.stderr)
            time.sleep(5 * (i + 1))


def collect_list():
    con = db()
    for court_type, cat, label in SCOPES:
        page, size = 0, 100
        while True:
            params = {"court_type": court_type, "startDate": START, "endDate": END, "page": page, "size": size}
            if cat:
                params["category_id"] = cat
            d = get_json("/publications/list", params)
            rows = d.get("content") or []
            for c in rows:
                con.execute(
                    """INSERT OR IGNORE INTO decisions (id, court_type, scope, court, instance, case_number,
                    category, judge, result, document_type, hearing_date, pdf_id, raw)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (c["id"], court_type, label, (c.get("court_names") or {}).get("uz_cyr"),
                     c.get("instance"), c.get("case_number"),
                     "; ".join(x.get("uz_cyr", "") for x in c.get("categories") or []),
                     c.get("responsible_judge_name") or c.get("speaker_judge_name"),
                     c.get("result"), (c.get("document_type_name") or {}).get("uz_cyr"),
                     c.get("hearing_date"), (c.get("pdf") or {}).get("id"), json.dumps(c, ensure_ascii=False)))
            con.commit()
            total = d.get("totalElements") or 0
            print(f"{label}: {min((page + 1) * size, total)}/{total}")
            if not rows or (page + 1) * size >= total:
                break
            page += 1
            time.sleep(PAUSE)


def scan_one(row):
    rid, pdf_id = row
    try:
        with urllib.request.urlopen(f"{API}/public/onStream/{pdf_id}", timeout=180) as r:
            data = r.read()
        doc = pymupdf.open(stream=data, filetype="pdf")
        text = "\n".join(p.get_text() for p in doc)
        flat = re.sub(r"\s+", " ", text)
        hits, snippet = [], ""
        for name, rx in PATTERNS.items():
            m = rx.search(flat)
            if m:
                hits.append(name)
                snippet = snippet or flat[max(0, m.start() - 250): m.end() + 250]
        time.sleep(PAUSE)
        return rid, ",".join(hits), snippet, (text if hits else None), None
    except Exception as e:  # noqa: BLE001
        return rid, None, None, None, str(e)[:300]


def scan_pdfs():
    con = db()
    todo = con.execute("SELECT id, pdf_id FROM decisions WHERE scanned = 0 AND pdf_id IS NOT NULL").fetchall()
    print(f"O'qilishi kerak: {len(todo)} ta PDF")
    done = found = 0
    with ThreadPoolExecutor(WORKERS) as ex:
        for rid, hits, snippet, text, err in ex.map(scan_one, todo):
            con.execute("UPDATE decisions SET scanned = ?, matched = ?, snippet = ?, text = ?, error = ? WHERE id = ?",
                        (0 if err else 1, hits, snippet, text, err, rid))
            done += 1
            found += bool(hits)
            if done % 50 == 0:
                con.commit()
                print(f"  {done}/{len(todo)} o'qildi, topildi: {found}", flush=True)
    con.commit()
    print(f"Tugadi: {done} ta o'qildi, {found} ta mos ish topildi")


def export_csv():
    con = db()
    rows = con.execute("""SELECT court_type, scope, court, instance, case_number, category, judge, result,
        document_type, hearing_date, matched, snippet, pdf_id FROM decisions
        WHERE matched IS NOT NULL AND matched != '' ORDER BY court_type, hearing_date DESC""").fetchall()
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Sud turi", "Qidiruv doirasi", "Sud", "Instansiya", "Ish raqami", "Ish toifasi", "Sudya",
                    "Natija", "Hujjat turi", "Ko'rilgan sana", "Topilgan tashkilot", "Matndan parcha", "PDF havola"])
        for r in rows:
            (ct, scope, court, inst, num, cat, judge, res, dt, date, matched, snip, pdf) = r
            w.writerow([ct, scope, court, INSTANCES.get(inst, inst), num, cat, judge, RESULTS.get(res, res), dt,
                        date, matched.replace("inson_markazi", "Inson markazi")
                        .replace("ijtimoiy_himoya_agentligi", "Ijtimoiy himoya agentligi"),
                        snip, f"{API}/public/onStream/{pdf}"])
    print(f"{len(rows)} ta qator -> {OUT}")


if __name__ == "__main__":
    {"list": collect_list, "pdf": scan_pdfs, "export": export_csv}[sys.argv[1] if len(sys.argv) > 1 else "list"]()
