"""O'zbekiston hududlari xaritasi uchun ma'lumotlar.

Hudud chegaralari: geoBoundaries (UZB ADM1, gbOpen), CC BY 4.0 — https://www.geoboundaries.org
Chegaralar SVG yo'llariga oldindan aylantirilgan (static/geo/uz_regions.json), xarita internetsiz ishlaydi.
"""
import json
from functools import lru_cache

from django.conf import settings
from django.db.models import Count, Q

from cases.models import Deadline
from core.models import Classifier, ClassifierKind

# Yorliqlar bir-birining ustiga tushmasligi uchun ayrim hududlar uchun qo'lda tanlangan joy
LABEL_POSITIONS = {
    "toshkent-v": (842, 292),
    "toshkent-sh": (748, 360),
    "andijon": (948, 400),
    "namangan": (872, 330),
    "fargona": (880, 425),
    "sirdaryo": (738, 405),
    "jizzax": (660, 420),
}


@lru_cache(maxsize=1)
def _shapes():
    path = settings.BASE_DIR / "static" / "geo" / "uz_regions.json"
    return json.loads(path.read_text(encoding="utf-8"))


def region_map(cases, deadlines, cases_url):
    """Hududlar kesimidagi ko'rsatkichlar bilan xarita ma'lumotlari.

    cases — foydalanuvchi ko'ra oladigan (bekor qilinmagan) ishlar;
    deadlines — shu doiradagi bajarilmagan muddatlar.
    """
    shapes = _shapes()
    stats = {
        row["organization__region__code"]: row
        for row in cases.order_by().values("organization__region__code").annotate(
            total=Count("id"),
            open=Count("id", filter=Q(status__is_final=False)),
            closed=Count("id", filter=Q(status__is_final=True)),
        )
    }
    overdue = {
        row["case__organization__region__code"]: row["n"]
        for row in Deadline.objects.filter(pk__in=deadlines.overdue().values("pk"))
        .order_by().values("case__organization__region__code").annotate(n=Count("case", distinct=True))
    }
    regions = {c.code: c for c in Classifier.objects.filter(kind=ClassifierKind.REGION)}
    max_total = max([s["total"] for code, s in stats.items() if code in shapes["regions"]] + [1])

    items = []
    for code, shape in shapes["regions"].items():
        region = regions.get(code)
        s = stats.get(code, {})
        total = s.get("total", 0)
        lx, ly = LABEL_POSITIONS.get(code, (shape["cx"], shape["cy"]))
        items.append({
            "code": code,
            "name": region.name if region else code,
            "d": shape["d"],
            "cx": shape["cx"], "cy": shape["cy"], "lx": lx, "ly": ly,
            "leader": code in LABEL_POSITIONS and abs(lx - shape["cx"]) + abs(ly - shape["cy"]) > 25,
            "total": total,
            "open": s.get("open", 0),
            "closed": s.get("closed", 0),
            "overdue": overdue.get(code, 0),
            "level": round(total / max_total, 3) if total else 0,
            "url": cases_url(region=region.pk) if region else cases_url(),
        })
    # Kichik hududlar (Toshkent shahri) katta hududlar ustida chizilishi uchun oxirida
    items.sort(key=lambda r: r["code"] == "toshkent-sh")

    mapped = sum(r["total"] for r in items)
    central_total = sum(s["total"] for code, s in stats.items() if code not in shapes["regions"])
    central_region = regions.get("respublika")
    ranking = [
        {**r, "pct": round(r["total"] * 100 / max_total)} for r in sorted(items, key=lambda r: (-r["total"], r["name"]))
    ]
    return {
        "viewbox": shapes["viewBox"],
        "ranking": ranking,
        "regions": items,
        "max_total": max_total,
        "mapped_total": mapped,
        "central_total": central_total,
        "central_url": cases_url(region=central_region.pk) if central_region else cases_url(),
    }
