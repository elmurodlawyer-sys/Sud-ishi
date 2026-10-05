"""data/roles/final/*.md tahlillaridan bitta HTML sahifa yasaydi: data/roles/sud_tahlil.html"""
import html
import json
import re
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "roles" / "final"
OUT = ROOT / "data" / "roles" / "sud_tahlil.html"
API = "https://adolatapi1.sud.uz/public/onStream/"


def md(text: str) -> str:
    return markdown.markdown(text, extensions=["tables", "sane_lists"])


def pdf_link(case: str) -> str:
    name = case.replace("/", "_")
    for p in (ROOT / "data" / "roles").glob(f"*/*/{name}.json"):
        return API + json.loads(p.read_text())["pdf"]["id"]
    return ""


def case_block(path: Path) -> tuple[str, str, str]:
    text = path.read_text(encoding="utf-8")
    title, _, body = text.partition("\n")
    title = title.lstrip("# ").strip()
    m = re.search(r"\d-\d{4}-\d{4}/\d+", title)
    case = m.group(0) if m else path.stem
    kind = "admin" if case.startswith("5-") else "civil"
    role = ("javobgar" if "javobgar" in title.lower() else
            "vakil" if "vakil" in title.lower() or "manfaat" in title.lower() else "davogar")
    body_html = md(body)
    body_html = re.sub(r"<h2>([^<]*xato[^<]*)</h2>", r'<h2 class="neg">\1</h2>', body_html, flags=re.I)
    body_html = re.sub(r"<h2>([^<]*ustunlik[^<]*)</h2>", r'<h2 class="pos">\1</h2>', body_html, flags=re.I)
    link = pdf_link(case)
    pdf = f'<a class="pdf" href="{link}" target="_blank" rel="noopener">Qaror matni (PDF)</a>' if link else ""
    role_label = {"javobgar": "Javobgar", "davogar": "Da'vogar / arizachi", "vakil": "Vakil"}[role]
    kind_label = "Ma'muriy" if kind == "admin" else "Fuqarolik"
    block = f"""
<details class="case" data-kind="{kind}" id="ish-{case.replace('/', '-')}">
  <summary>
    <span class="tags"><span class="tag">{kind_label}</span><span class="tag role-{role}">{role_label}</span></span>
    <span class="ctitle">{html.escape(title)}</span>
  </summary>
  <div class="cbody">{pdf}{body_html}</div>
</details>"""
    return kind, role, block


def main():
    cases = sorted(p for p in SRC.glob("*.md") if not p.name.startswith(("00_", "99_")))
    order = {"admin": 0, "civil": 1}
    roles = {"javobgar": 0, "davogar": 1, "vakil": 2}
    blocks = sorted((case_block(p) for p in cases), key=lambda b: (order[b[0]], roles[b[1]]))
    summary = md((SRC / "00_umumiy.md").read_text(encoding="utf-8").partition("\n")[2])
    method = md((SRC / "99_metodika.md").read_text(encoding="utf-8").partition("\n")[2])
    n_admin = sum(1 for b in blocks if b[0] == "admin")
    n_civil = len(blocks) - n_admin
    page = TEMPLATE.format(summary=summary, method=method, cases="".join(b[2] for b in blocks),
                           n_admin=n_admin, n_civil=n_civil, n=len(blocks))
    OUT.write_text(page, encoding="utf-8")
    print(f"{len(blocks)} ta ish -> {OUT} ({OUT.stat().st_size // 1024} KB)")


TEMPLATE = """<title>Agentlik sud ishlari tahlili</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=PT+Serif:wght@400;700&family=Golos+Text:wght@400;500;600&family=JetBrains+Mono:wght@500&display=swap">
<style>
/* Layout: bitta ustunli hisobot; yuqorida xulosa, keyin filtrlanadigan ishlar, oxirida metodika. */
:root {{
  --bg: #f3f5f7; --paper: #ffffff; --ink: #1b2430; --muted: #5b6878; --line: #d9dfe6;
  --accent: #1f5a6b; --accent-soft: #e2eef1; --neg: #a13a2e; --neg-soft: #f7e6e3; --pos: #2e6b3f; --pos-soft: #e3f1e6;
  --serif: "PT Serif", Georgia, "Times New Roman", serif;
  --sans: "Golos Text", "Segoe UI", system-ui, sans-serif;
  --mono: "JetBrains Mono", ui-monospace, Consolas, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg: #12171d; --paper: #19212a; --ink: #e3e8ee; --muted: #9aa7b6; --line: #2c3743;
  --accent: #7fb9c9; --accent-soft: #1d3138; --neg: #e8907f; --neg-soft: #3a2320; --pos: #8fcb9c; --pos-soft: #1e3324; color-scheme: dark; }} }}
:root[data-theme="dark"] {{
  --bg: #12171d; --paper: #19212a; --ink: #e3e8ee; --muted: #9aa7b6; --line: #2c3743;
  --accent: #7fb9c9; --accent-soft: #1d3138; --neg: #e8907f; --neg-soft: #3a2320; --pos: #8fcb9c; --pos-soft: #1e3324; color-scheme: dark; }}
body {{ background: var(--bg); color: var(--ink); font: 400 15.5px/1.6 var(--sans); }}
.wrap {{ max-width: 920px; margin: 0 auto; padding-inline: 16px; padding-block: 32px 64px; display: grid; gap: 28px; }}
header {{ display: grid; gap: 10px; }}
.eyebrow {{ font: 500 12px/1 var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--accent); }}
h1 {{ font: 700 clamp(26px, 4.5vw, 38px)/1.15 var(--serif); margin: 0; text-wrap: balance; }}
.lead {{ color: var(--muted); max-width: 65ch; margin: 0; }}
.quota {{ display: flex; flex-wrap: wrap; gap: 8px; }}
.quota span {{ font: 500 13px/1 var(--sans); padding: 7px 10px; border-radius: 6px; background: var(--paper); border: 1px solid var(--line); }}
section {{ background: var(--paper); border: 1px solid var(--line); border-radius: 10px; padding: 20px clamp(16px, 3vw, 28px); min-width: 0; }}
section > h2 {{ font: 700 22px/1.25 var(--serif); margin: 0 0 12px; }}
h3 {{ font: 600 16px/1.3 var(--sans); margin: 20px 0 6px; }}
.prose {{ max-width: 72ch; }}
.prose h2 {{ font: 600 17px/1.3 var(--sans); margin: 22px 0 6px; }}
.table {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
th, td {{ border-bottom: 1px solid var(--line); padding: 8px 10px; text-align: left; vertical-align: top; }}
th {{ font-weight: 600; color: var(--muted); font-size: 12.5px; text-transform: uppercase; letter-spacing: .04em; }}
.filters {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }}
.filters button {{ font: 500 14px/1 var(--sans); padding: 9px 14px; border-radius: 999px; border: 1px solid var(--line); background: var(--bg); color: var(--ink); cursor: pointer; }}
.filters button[aria-pressed="true"] {{ background: var(--accent); border-color: var(--accent); color: var(--paper); }}
.filters button:focus-visible, summary:focus-visible, a:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
.cases {{ display: grid; gap: 10px; }}
.case {{ border: 1px solid var(--line); border-radius: 8px; background: var(--paper); }}
.case summary {{ cursor: pointer; list-style: none; padding: 14px 16px; display: grid; gap: 6px; }}
.case summary::-webkit-details-marker {{ display: none; }}
.case[open] summary {{ border-bottom: 1px solid var(--line); }}
.ctitle {{ font: 700 17px/1.35 var(--serif); }}
.tags {{ display: flex; flex-wrap: wrap; gap: 6px; }}
.tag {{ font: 500 12px/1 var(--mono); padding: 5px 8px; border-radius: 4px; background: var(--accent-soft); color: var(--accent); }}
.role-javobgar {{ background: var(--neg-soft); color: var(--neg); }}
.role-davogar {{ background: var(--pos-soft); color: var(--pos); }}
.cbody {{ padding: 4px 16px 18px; max-width: 76ch; min-width: 0; }}
.cbody h2 {{ font: 600 15px/1.3 var(--sans); margin: 18px 0 6px; color: var(--accent); }}
.cbody h2.neg {{ color: var(--neg); }}
.cbody h2.pos {{ color: var(--pos); }}
.cbody ul {{ padding-left: 20px; margin: 6px 0; }}
.cbody li {{ margin: 4px 0; }}
.pdf {{ display: inline-block; margin-top: 12px; font: 500 13px/1 var(--sans); color: var(--accent); }}
code {{ font: 500 13px var(--mono); background: var(--accent-soft); padding: 1px 5px; border-radius: 3px; }}
blockquote {{ margin: 8px 0; padding: 8px 12px; background: var(--bg); border-radius: 6px; color: var(--muted); }}
footer {{ color: var(--muted); font-size: 13px; }}
</style>
<div class="wrap">
<header>
  <div class="eyebrow">public.sud.uz · 2026 yil qarorlari</div>
  <h1>Ijtimoiy himoya milliy agentligi tizimi ishtirokidagi sud ishlari</h1>
  <p class="lead">{n} ta eng so'nggi ish: Agentlik, uning hududiy boshqarmalari, "Inson" markazlari, TIEK va "Muruvvat" uylari javobgar, da'vogar (arizachi) yoki boshqa shaxs manfaatida vakil bo'lgan qarorlar. Tahlil Agentlik tizimining xatolari va ustunliklariga qaratilgan.</p>
  <div class="quota"><span>Ma'muriy: {n_admin} ta ish</span><span>Fuqarolik: {n_civil} ta ish</span></div>
</header>
<section id="xulosa"><h2>Umumiy xulosa</h2><div class="prose table">{summary}</div></section>
<section id="ishlar"><h2>Ishlar bo'yicha tahlil</h2>
  <div class="filters" role="group" aria-label="Sud turi">
    <button type="button" data-f="all" aria-pressed="true">Barchasi</button>
    <button type="button" data-f="admin" aria-pressed="false">Ma'muriy</button>
    <button type="button" data-f="civil" aria-pressed="false">Fuqarolik</button>
  </div>
  <div class="cases">{cases}</div>
</section>
<section id="metodika"><div class="prose">{method}</div></section>
<footer>Qarorlar public.sud.uz ochiq portalidan olingan. "Tahlilchi izohi" deb belgilangan normalar qaror matnida yo'q va Lex.uz da tekshirilishi kerak.</footer>
</div>
<script>
document.querySelectorAll('.filters button').forEach(b => b.addEventListener('click', () => {{
  document.querySelectorAll('.filters button').forEach(x => x.setAttribute('aria-pressed', x === b));
  document.querySelectorAll('.case').forEach(c => {{ c.hidden = b.dataset.f !== 'all' && c.dataset.kind !== b.dataset.f; }});
}}));
</script>
"""

if __name__ == "__main__":
    main()
