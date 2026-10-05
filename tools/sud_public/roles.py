"""Ijtimoiy himoya tizimi tashkilotlarining sud ishlaridagi rolini aniqlash va
kvota bo'yicha eng so'nggi ishlarni yig'ish.

    python tools/sud_public/roles.py classify   # yig'ilgan matnlarni rol bo'yicha tasniflash
    python tools/sud_public/roles.py search     # kvotalar to'lguncha qidirish

Natija: data/roles/<TUR>/<rol>/<ish>.{pdf,txt,json}
"""
import datetime as dt
import glob
import json
import os
import re
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from collect import PAUSE, ROOT, get_json  # noqa: E402
from latest import fetch_pdf  # noqa: E402

import pymupdf  # noqa: E402

OUT = ROOT / "data" / "roles"
WORKERS = int(os.environ.get("WORKERS", 3))

# Agentlik tizimi: Agentlik va hududiy boshqarmalari, "Инсон" markazlari, TIEK, "Мурувват"/"Саховат" uylari.
ORG = re.compile(
    r"(Инсон|Inson)\s*[»\"”']?\s*(ижтимоий|ijtimoiy)\s+(хизмат|xizmat|марказ|markaz)"
    r"|(ижтимоий|ijtimoiy)\s+(ҳимоя|химоя|himoya)\s+(миллий\s+|milliy\s+)?(агентлиг|agentlig)"
    r"|тиббий-ижтимоий\s+эксперт\s+комисси"
    r"|[«\"“„]\s*(Мурувват|Саховат)\s*[»\"”]", re.I)

ROLE_WORDS = [
    ("javobgar", r"жавобгар|javobgar"),
    ("davogar", r"даъвогар|da'vogar|аризачи|arizachi"),
    ("uchinchi", r"учинчи\s+шахс"),
]

# Kvotalar: (sud turi, rol) -> nechta kerak.
QUOTA = {
    ("ADMINISTRATIVE", "javobgar"): 2, ("ADMINISTRATIVE", "davogar"): 2,
    ("CIVIL", "javobgar"): 2, ("CIVIL", "davogar"): 2, ("CIVIL", "vakil"): 1,
}

# Fuqarolik ishlarida faqat tizim tashkilotlari ko'p uchraydigan toifalar o'qiladi.
CIVIL_CATEGORIES = [
    "f6de1988-ecaf-47d2-8c85-633da71b5752",  # Ishga tiklash
    "1d6f38e4-7369-4f36-ad9a-693a9486dbb1",  # Ish haqini undirish
    "f33c2acf-aeac-48ec-b783-480f5e069b90",  # Hisoblangan, lekin to'lanmagan ish haqi
    "69fce272-0170-4476-a16e-1b4b9a7a5bda",  # Mehnat munosabatlariga doir nizolar
    "9a056d61-93bd-4906-90af-3522af529c13",  # Mehnat munosabatlariga doir boshqa ishlar
    "a176b472-4a66-4ec0-a080-e0551dc1afa0",  # Pensiya va ijtimoiy to'lovlarni undirish
    "fbfda98e-ea00-4e34-bd9c-30a0a6824eff",  # Ortiqcha to'langan pensiyani undirish
    "9a6fd5ba-e5d0-452d-a4bb-c438cd2bdb5f",  # Davlatga yetkazilgan zarar
    "64a32444-2931-4e7c-820b-55762401ff1c",  # Xodimdan zararni undirish (regress)
]
# Muomalaga layoqatsiz deb topish va aliment ishlarida tashkilot odatda boshqa shaxs uchun
# arizachi bo'ladi; bunday ishlar yetarli yig'ilgan, shuning uchun qidiruvga kiritilmaydi.


def intro(text: str) -> str:
    flat = re.sub(r"\s+", " ", text)
    m = re.search(r"А\s?Н\s?И\s?Қ\s?Л\s?А\s?Д\s?И|аниқлади", flat)
    return flat[: m.start()] if m and m.start() > 300 else flat[:4000]


def role_of(text: str) -> str | None:
    """Tizim tashkilotining roli: javobgar, davogar, vakil, uchinchi, xulosa yoki boshqa."""
    head = intro(text)
    for m in ORG.finditer(head):
        before = head[max(0, m.start() - 160): m.start()]
        after = head[m.end(): m.end() + 260]
        last = None
        for role, rx in ROLE_WORDS:
            for r in re.finditer(rx, before, re.I):
                if not last or r.start() > last[1]:
                    last = (role, r.start())
        if last and last[0] == "davogar" and re.search(r"манфаат", after[:200], re.I):
            return "vakil"
        if last:
            return last[0]
        if re.search(r"хулоса", after[:150], re.I):
            return "xulosa"
    return "boshqa" if ORG.search(text.replace("\n", " ")) else None


def save(court_type: str, role: str, item: dict, data: bytes | None, text: str):
    d = OUT / court_type / role
    d.mkdir(parents=True, exist_ok=True)
    name = item["case_number"].replace("/", "_")
    if data:
        (d / f"{name}.pdf").write_bytes(data)
    (d / f"{name}.txt").write_text(text, encoding="utf-8")
    (d / f"{name}.json").write_text(json.dumps(item, ensure_ascii=False, indent=1), encoding="utf-8")


def have(court_type: str, role: str) -> set[str]:
    return {p.stem for p in (OUT / court_type / role).glob("*.json")}


def classify():
    """Avval yig'ilgan matnlarni tasniflash (yangi PDF yuklamasdan)."""
    for court_type in ("CIVIL", "ADMINISTRATIVE"):
        for t in sorted(glob.glob(str(ROOT / "data" / "latest" / court_type / "*.txt"))):
            text = open(t, encoding="utf-8").read()
            item = json.load(open(t[:-4] + ".json"))
            role = role_of(text)
            print(court_type, item["case_number"], role)
            if role:
                save(court_type, role, item, None, text)
    con = sqlite3.connect(ROOT / "data" / "sud_public.db")
    for raw, text in con.execute("SELECT raw, text FROM decisions WHERE text IS NOT NULL"):
        item = json.loads(raw)
        role = role_of(text)
        print("CIVIL(db)", item["case_number"], item.get("hearing_date"), role)
        if role:
            save("CIVIL", role, item, None, text)


def check(item):
    try:
        data = fetch_pdf(item["pdf"]["id"])
        text = "\n".join(p.get_text() for p in pymupdf.open(stream=data, filetype="pdf")).replace("\x02", "и")
        time.sleep(PAUSE)
        return item, data, text
    except Exception as e:  # noqa: BLE001
        print(f"  xato {item.get('case_number')}: {e}", file=sys.stderr)
        return item, None, None


def need(court_type: str) -> dict[str, int]:
    return {r: q - len(have(court_type, r)) for (t, r), q in QUOTA.items()
            if t == court_type and q - len(have(court_type, r)) > 0}


def search(court_type: str, start_from: dt.date, max_pdfs: int = 3000):
    done_file = OUT / f"{court_type}.checked"
    OUT.mkdir(parents=True, exist_ok=True)
    done = set(done_file.read_text().split()) if done_file.exists() else set()
    cats = CIVIL_CATEGORIES if court_type == "CIVIL" else [None]
    end, checked = start_from, 0
    while need(court_type) and checked < max_pdfs and end >= dt.date(2026, 1, 1):
        start = max(end - dt.timedelta(days=13), dt.date(2026, 1, 1))
        items = []
        for cat in cats:
            page = 0
            while True:
                params = {"court_type": court_type, "startDate": start.isoformat(), "endDate": end.isoformat(),
                          "page": page, "size": 100}
                if cat:
                    params["category_id"] = cat
                d = get_json("/publications/list", params)
                rows = d.get("content") or []
                items += [r for r in rows if r.get("pdf") and r["id"] not in done]
                if not rows or (page + 1) * 100 >= (d.get("totalElements") or 0):
                    break
                page += 1
                time.sleep(PAUSE)
        items.sort(key=lambda i: i.get("hearing_date") or "", reverse=True)
        print(f"{court_type} {start}..{end}: {len(items)} ta qaror, kerak: {need(court_type)}", flush=True)
        with ThreadPoolExecutor(WORKERS) as ex:
            for item, data, text in ex.map(check, items):
                checked += 1
                if data is None:
                    continue
                with done_file.open("a") as f:
                    f.write(item["id"] + "\n")
                role = role_of(text)
                name = item["case_number"].replace("/", "_")
                if role in need(court_type) and not any(name in have(court_type, r) for r in ("javobgar", "davogar", "vakil")):
                    save(court_type, role, item, data, text)
                    print(f"  + {role}: {item['case_number']} ({item.get('hearing_date')})", flush=True)
                if not need(court_type):
                    break
                if checked % 100 == 0:
                    print(f"  ... {checked} ta o'qildi", flush=True)
        end = start - dt.timedelta(days=1)
    print(f"{court_type}: YAKUN, o'qildi {checked}, yetishmaydi: {need(court_type)}", flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "classify"
    if cmd == "classify":
        classify()
    else:
        types = sys.argv[2:] or ["CIVIL", "ADMINISTRATIVE"]
        frm = {"CIVIL": os.environ.get("FROM_CIVIL"), "ADMINISTRATIVE": os.environ.get("FROM_ADMINISTRATIVE")}
        with ThreadPoolExecutor(len(types)) as ex:
            list(ex.map(lambda t: search(t, dt.date.fromisoformat(frm.get(t) or dt.date.today().isoformat())), types))
