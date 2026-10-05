"""Har bir sud turi bo'yicha "Инсон" markazlari yoki Ijtimoiy himoya milliy agentligi
ishtirok etgan eng so'nggi N ta qarorni topadi, PDF'ini saqlaydi.

    python tools/sud_public/latest.py            # har turdan 5 tadan
    python tools/sud_public/latest.py 5 ECONOMIC # faqat bitta tur

Oxirgi kunlardan boshlab orqaga qarab oynalar bo'yicha ro'yxat olinadi, qarorlar
sanasi bo'yicha kamayish tartibida o'qiladi va N ta mos ish topilganda to'xtaydi.
"""
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).parent))
from collect import API, PATTERNS, PAUSE, ROOT, get_json  # noqa: E402

OUT_DIR = ROOT / "data" / "latest"
COURT_TYPES = ["CIVIL", "ADMINISTRATIVE", "ECONOMIC"]
WINDOW_DAYS = 7
MAX_PDFS = 4000  # bitta sud turi uchun o'qiladigan PDF'lar chegarasi
WORKERS = int(os.environ.get("WORKERS", 1))  # har bir sud turiga; standart: 3 tur x 1 = 3 parallel so'rov


def fetch_pdf(pdf_id: str) -> bytes:
    for i in range(3):
        try:
            with urllib.request.urlopen(f"{API}/public/onStream/{pdf_id}", timeout=180) as r:
                return r.read()
        except Exception:  # noqa: BLE001
            if i == 2:
                raise
            time.sleep(5)


def check(item):
    try:
        data = fetch_pdf(item["pdf"]["id"])
        text = "\n".join(p.get_text() for p in pymupdf.open(stream=data, filetype="pdf")).replace("\x02", "и")
        flat = re.sub(r"\s+", " ", text)
        hits = [n for n, rx in PATTERNS.items() if rx.search(flat)]
        time.sleep(PAUSE)
        return item, hits, data, text
    except Exception as e:  # noqa: BLE001
        print(f"  xato {item.get('case_number')}: {e}", file=sys.stderr)
        return item, [], None, None


def window_items(court_type: str, start: dt.date, end: dt.date):
    items, page = [], 0
    while True:
        d = get_json("/publications/list", {"court_type": court_type, "startDate": start.isoformat(),
                                             "endDate": end.isoformat(), "page": page, "size": 100})
        rows = d.get("content") or []
        items += [r for r in rows if r.get("pdf")]
        if not rows or (page + 1) * 100 >= (d.get("totalElements") or 0):
            return items
        page += 1
        time.sleep(PAUSE)


def run(court_type: str, need: int):
    out = OUT_DIR / court_type
    out.mkdir(parents=True, exist_ok=True)
    found, seen, checked = [p.stem.replace("_", "/") for p in out.glob("*.json")][:need], set(), 0
    today = dt.date.today()
    # Qayta ishga tushirishda oldin o'qilgan haftalarni o'tkazib yuborish uchun: FROM_<TUR>=YYYY-MM-DD
    end = dt.date.fromisoformat(os.environ.get(f"FROM_{court_type}", today.isoformat()))
    while len(found) < need and checked < MAX_PDFS and end.year == 2026:
        start = max(end - dt.timedelta(days=WINDOW_DAYS - 1), dt.date(2026, 1, 1))
        items = [i for i in window_items(court_type, start, end) if i["id"] not in seen]
        seen.update(i["id"] for i in items)
        # Eng so'nggisi birinchi; kelajak sanalari (ma'lumot xatosi) oxiriga.
        items.sort(key=lambda i: (i.get("hearing_date") or "") if (i.get("hearing_date") or "") <= today.isoformat() else "", reverse=True)
        print(f"{court_type}: {start}..{end} — {len(items)} ta qaror", flush=True)
        for k in range(0, len(items), WORKERS * 4):
            batch = items[k:k + WORKERS * 4]
            with ThreadPoolExecutor(WORKERS) as ex:
                for item, hits, data, text in ex.map(check, batch):
                    checked += 1
                    # Bitta ishning bir nechta hujjati bo'lishi mumkin — ish raqami bo'yicha bir marta olinadi.
                    if hits and len(found) < need and item["case_number"] not in found:
                        name = item["case_number"].replace("/", "_")
                        (out / f"{name}.pdf").write_bytes(data)
                        (out / f"{name}.txt").write_text(text, encoding="utf-8")
                        (out / f"{name}.json").write_text(
                            json.dumps({**item, "matched": hits}, ensure_ascii=False, indent=1), encoding="utf-8")
                        found.append(item["case_number"])
                        print(f"  + {item['case_number']} ({item.get('hearing_date')}) {hits}", flush=True)
            if len(found) >= need:
                break
        print(f"  o'qildi: {checked}, topildi: {len(found)}", flush=True)
        end = start - dt.timedelta(days=1)
    print(f"{court_type}: YAKUN — {len(found)} ta topildi, {checked} ta PDF o'qildi", flush=True)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    types = sys.argv[2:] or COURT_TYPES
    with ThreadPoolExecutor(len(types)) as ex:
        list(ex.map(lambda t: run(t, n), types))
