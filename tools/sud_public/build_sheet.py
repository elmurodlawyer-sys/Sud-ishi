"""data/latest/<TUR>/ dagi topilgan ishlar va ularning tahlillaridan (<ish>.tahlil.md)
Google Sheet'ga yuklash uchun CSV yasaydi: data/latest/natijalar.csv

    python tools/sud_public/build_sheet.py [pdf_havolalar.json]

pdf_havolalar.json (ixtiyoriy): {"<ish raqami>": "<Google Drive havolasi>"}.
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data" / "latest"
API = "https://adolatapi1.sud.uz"
TYPES = {"CIVIL": "Fuqarolik", "ADMINISTRATIVE": "Ma'muriy", "ECONOMIC": "Iqtisodiy"}
RESULTS = {"FULFILLED": "Qanoatlantirilgan", "PARTIALLY_FULFILLED": "Qisman qanoatlantirilgan",
           "REFUSED": "Rad etilgan", "CASE_ENDED": "Ish yuritish tugatilgan",
           "LEFT_WITHOUT_CONSIDERATION": "Ko'rmasdan qoldirilgan"}
INSTANCES = {"FIRST": "Birinchi", "APPEAL": "Apellyatsiya", "CASSATION": "Kassatsiya", "REVISION": "Taftish", "INSPECTION": "Taftish"}
SECTIONS = {
    "Tashkilot roli": r"Taraflar va tashkilotning roli",
    "Talab": r"Talab mazmuni",
    "Nima uchun shunday qaror chiqdi": r"Sud motivlari",
    "Qo'llangan normalar": r"Qo.llangan qonun normalari",
    "Huquqiy baho": r"Huquqiy baho",
    "Tashkilot uchun xulosa": r"Tashkilot faoliyati uchun xulosa",
    "Qisqa xulosa": r"Qisqa xulosa",
}


def section(md: str, title_rx: str) -> str:
    """"## N. Sarlavha" bilan boshlanadigan bo'limning matnini qaytaradi."""
    parts = re.split(r"^#{1,3}\s+", md, flags=re.M)
    for part in parts:
        head, _, body = part.partition("\n")
        if re.search(title_rx, head):
            text = re.sub(r"\n{2,}", "\n", body).strip()
            return text[:49000]  # Google Sheets katagi chegarasi 50 000 belgi
    return ""


def main():
    links = json.loads(Path(sys.argv[1]).read_text()) if len(sys.argv) > 1 else {}
    rows = []
    for t, label in TYPES.items():
        for j in sorted((BASE / t).glob("*.json"), key=lambda p: json.loads(p.read_text()).get("hearing_date") or "",
                        reverse=True):
            d = json.loads(j.read_text())
            md_path = j.parent / f"{j.stem}.tahlil.md"
            md = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
            row = {
                "Sud turi": label,
                "Ish raqami": d["case_number"],
                "Sud": (d.get("court_names") or {}).get("uz_cyr", ""),
                "Instansiya": INSTANCES.get(d.get("instance"), d.get("instance")),
                "Sana": d.get("hearing_date") or "",
                "Ish toifasi": "; ".join(c.get("uz_cyr", "") for c in d.get("categories") or []),
                "Sudya": d.get("responsible_judge_name") or d.get("speaker_judge_name") or "",
                "Natija": RESULTS.get(d.get("result"), d.get("result") or ""),
                "Topilgan tashkilot": ", ".join({"inson_markazi": "Inson markazi",
                                                 "ijtimoiy_himoya_agentligi": "Ijtimoiy himoya agentligi"}
                                                .get(m, m) for m in d.get("matched", [])),
            }
            row.update({k: section(md, rx) for k, rx in SECTIONS.items()})
            row["PDF (Drive)"] = links.get(d["case_number"], "")
            row["PDF (sud.uz)"] = f"{API}/public/onStream/{d['pdf']['id']}"
            rows.append(row)
    out = BASE / "natijalar.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["Ish raqami"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} ta ish -> {out}")


if __name__ == "__main__":
    main()
