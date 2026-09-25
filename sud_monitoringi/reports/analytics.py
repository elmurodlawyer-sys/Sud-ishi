"""Avtomatik hisobotlar: kesimlar (dimensions) va ko'rsatkichlar (3.8 va 7-bo'limlar).

Hisobot bazadagi aktual ma'lumotlardan hech qanday qo'lda hisob-kitobsiz shakllanadi.
Bir nechta kesimni bir vaqtda tanlash orqali kombinatsiyalangan hisobot olinadi.
"""
from collections import OrderedDict
from decimal import Decimal

from django.db.models import Case as DbCase
from django.db.models import CharField, Count, Q, Sum, Value, When
from django.db.models.functions import TruncDay, TruncMonth, TruncQuarter, TruncWeek, TruncYear

from cases.models import AgencyResult, Hearing, ProceduralRole

GRANULARITY = OrderedDict([
    ("day", ("Kun", TruncDay)),
    ("week", ("Hafta", TruncWeek)),
    ("month", ("Oy", TruncMonth)),
    ("quarter", ("Chorak", TruncQuarter)),
    ("year", ("Yil", TruncYear)),
])

PERIOD_FIELDS = OrderedDict([
    ("created_at", "Ro‘yxatga olingan sana"),
    ("outcome_date", "Yakuniy sud hujjati sanasi"),
    ("filed_date", "Da’vo berilgan sana"),
])

CLAIM_BUCKETS = [
    ("0", "Summasiz", Q(claim_amount__isnull=True) | Q(claim_amount=0)),
    ("1", "10 mln so‘mgacha", Q(claim_amount__gt=0, claim_amount__lt=10_000_000)),
    ("2", "10–50 mln so‘m", Q(claim_amount__gte=10_000_000, claim_amount__lt=50_000_000)),
    ("3", "50–100 mln so‘m", Q(claim_amount__gte=50_000_000, claim_amount__lt=100_000_000)),
    ("4", "100–500 mln so‘m", Q(claim_amount__gte=100_000_000, claim_amount__lt=500_000_000)),
    ("5", "500 mln – 1 mlrd so‘m", Q(claim_amount__gte=500_000_000, claim_amount__lt=1_000_000_000)),
    ("6", "1 mlrd so‘mdan ortiq", Q(claim_amount__gte=1_000_000_000)),
]

# kod: (nomi, id-lookup, label-lookup, choices-xaritasi yoki None)
DIMENSIONS = OrderedDict([
    ("organization", ("Tashkilot", "organization_id", "organization__full_name", None)),
    ("org_type", ("Tashkilot turi", "organization__org_type_id", "organization__org_type__name", None)),
    ("region", ("Hudud", "organization__region_id", "organization__region__name", None)),
    ("court_type", ("Sud turi", "court__court_type_id", "court__court_type__name", None)),
    ("court", ("Sud", "court_id", "court__name", None)),
    ("instance", ("Sud instansiyasi (bosqichi)", "instance_id", "instance__name", None)),
    ("category", ("Ish turi (turkumi)", "category_id", "category__name", None)),
    ("role", ("Protsessual maqom", "role", "role", dict(ProceduralRole.choices))),
    ("status", ("Ish holati", "status_id", "status__name", None)),
    ("state", ("Jarayon", "status__is_final", "status__is_final", {True: "Yakunlangan / arxiv", False: "Jarayonda"})),
    ("outcome", ("Ish natijasi", "outcome_id", "outcome__name", None)),
    ("agency_result", ("Agentlik uchun natija", "agency_result", "agency_result", dict(AgencyResult.choices))),
    ("responsible", ("Mas’ul xodim", "responsible_id", "responsible__last_name", None)),
    ("claim_bucket", ("Da’vo summasi oralig‘i", "claim_bucket", "claim_bucket", {k: v for k, v, _ in CLAIM_BUCKETS})),
    ("period", ("Davr", "period", "period", None)),
])

METRICS = OrderedDict([
    ("total", "Jami ishlar"),
    ("open", "Jarayonda"),
    ("closed", "Yakunlangan"),
    ("plaintiff", "Da’vogar sifatida"),
    ("defendant", "Javobgar sifatida"),
    ("third", "Uchinchi shaxs sifatida"),
    ("favor", "Agentlik foydasiga"),
    ("against", "Agentlik zarariga"),
    ("claim_sum", "Da’vo summasi (so‘m)"),
    ("awarded_sum", "Qaror bo‘yicha summa (so‘m)"),
    ("hearings", "Sud majlislari soni"),
    ("upcoming_hearings", "Kelgusi majlislar"),
])
DEFAULT_METRICS = ["total", "open", "closed", "plaintiff", "defendant", "third", "claim_sum", "hearings"]


def _aggregates():
    return {
        "total": Count("id", distinct=True),
        "open": Count("id", filter=Q(status__is_final=False), distinct=True),
        "closed": Count("id", filter=Q(status__is_final=True), distinct=True),
        "plaintiff": Count("id", filter=Q(role=ProceduralRole.PLAINTIFF), distinct=True),
        "defendant": Count("id", filter=Q(role=ProceduralRole.DEFENDANT), distinct=True),
        "third": Count("id", filter=Q(role=ProceduralRole.THIRD_PARTY), distinct=True),
        "favor": Count("id", filter=Q(agency_result=AgencyResult.FAVOR), distinct=True),
        "against": Count("id", filter=Q(agency_result=AgencyResult.AGAINST), distinct=True),
        "claim_sum": Sum("claim_amount"),
        "awarded_sum": Sum("awarded_amount"),
    }


def _annotate_dims(qs, dims, granularity, period_field, prefix=""):
    if "claim_bucket" in dims:
        qs = qs.annotate(
            claim_bucket=DbCase(
                *[When(_prefixed(cond, prefix), then=Value(code)) for code, _, cond in CLAIM_BUCKETS],
                default=Value("0"), output_field=CharField(),
            )
        )
    if "period" in dims:
        trunc = GRANULARITY.get(granularity, GRANULARITY["month"])[1]
        qs = qs.annotate(period=trunc(f"{prefix}{period_field}"))
    return qs


def _prefixed(q, prefix):
    """Q obyektidagi maydon nomlariga prefiks qo'shadi (masalan, 'case__')."""
    if not prefix:
        return q
    new = Q()
    new.connector, new.negated = q.connector, q.negated
    for child in q.children:
        if isinstance(child, Q):
            new.children.append(_prefixed(child, prefix))
        else:
            new.children.append((f"{prefix}{child[0]}", child[1]))
    return new


def _format_period(value, granularity):
    if value is None:
        return "—"
    if granularity == "day":
        return value.strftime("%d.%m.%Y")
    if granularity == "week":
        iso = value.isocalendar()
        return f"{iso[0]}-yil {iso[1]}-hafta"
    if granularity == "quarter":
        return f"{value.year}-yil {(value.month - 1) // 3 + 1}-chorak"
    if granularity == "year":
        return f"{value.year}-yil"
    months = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]
    return f"{value.year}-yil {months[value.month - 1]}"


def _label(dim, row, granularity):
    name, id_lookup, label_lookup, choices = DIMENSIONS[dim]
    if dim == "period":
        return _format_period(row.get("period"), granularity)
    if dim == "responsible":
        full = " ".join(x for x in [row.get("responsible__last_name"), row.get("responsible__first_name")] if x)
        return full or "Belgilanmagan"
    value = row.get(label_lookup)
    if choices is not None:
        return choices.get(value, "Ko‘rsatilmagan") if value not in (None, "") else "Ko‘rsatilmagan"
    return value if value not in (None, "") else "Ko‘rsatilmagan"


def build_report(qs, dims, metrics=None, granularity="month", period_field="created_at"):
    """Hisobot jadvalini tuzadi. Qaytaradi: headers, rows, totals, row_keys (drill-down uchun)."""
    dims = [d for d in dims if d in DIMENSIONS][:3] or ["organization"]
    metrics = [m for m in (metrics or DEFAULT_METRICS) if m in METRICS] or DEFAULT_METRICS
    if period_field not in PERIOD_FIELDS:
        period_field = "created_at"

    qs = _annotate_dims(qs, dims, granularity, period_field)
    value_fields = []
    for d in dims:
        _, id_lookup, label_lookup, _ = DIMENSIONS[d]
        value_fields += [id_lookup, label_lookup]
        if d == "responsible":
            value_fields.append("responsible__first_name")
    value_fields = list(dict.fromkeys(value_fields))
    aggregates = {k: v for k, v in _aggregates().items() if k in metrics}
    if not aggregates:
        aggregates = {"total": Count("id", distinct=True)}
    data = list(qs.order_by().values(*value_fields).annotate(**aggregates))

    hearing_counts, upcoming_counts = {}, {}
    if "hearings" in metrics or "upcoming_hearings" in metrics:
        from django.utils import timezone

        hqs = Hearing.objects.filter(case__in=qs.order_by().values("pk"))
        hqs = _annotate_dims(hqs, dims, granularity, period_field, prefix="case__")
        h_fields = [f"case__{f}" if f not in ("claim_bucket", "period") else f for f in value_fields]
        for row in hqs.order_by().values(*h_fields).annotate(
            n=Count("id"), up=Count("id", filter=Q(scheduled_at__gte=timezone.now(), status="rejalashtirilgan"))
        ):
            key = tuple(row[f] for f in h_fields)
            hearing_counts[key] = row["n"]
            upcoming_counts[key] = row["up"]

    rows, keys = [], []
    for row in data:
        key = tuple(row[f] for f in value_fields)
        labels = [_label(d, row, granularity) for d in dims]
        values = []
        for m in metrics:
            if m == "hearings":
                values.append(hearing_counts.get(key, 0))
            elif m == "upcoming_hearings":
                values.append(upcoming_counts.get(key, 0))
            else:
                v = row.get(m)
                values.append(v if v is not None else (Decimal("0") if m.endswith("_sum") else 0))
        rows.append(labels + values)
        keys.append({DIMENSIONS[d][1]: row[DIMENSIONS[d][1]] for d in dims})

    def sort_key(item):
        row, key = item
        parts = []
        for i, d in enumerate(dims):
            if d == "period":
                parts.append(str(key.get("period") or ""))
            elif d == "claim_bucket":
                parts.append(str(key.get("claim_bucket")))
            else:
                parts.append(str(row[i]).lower())
        return parts

    paired = sorted(zip(rows, keys), key=sort_key)
    if len(dims) == 1 and dims[0] not in ("period", "claim_bucket"):
        paired = sorted(paired, key=lambda item: -(item[0][len(dims)] or 0) if isinstance(item[0][len(dims)], (int, Decimal)) else 0)
    rows = [p[0] for p in paired]
    keys = [p[1] for p in paired]

    totals = ["Jami"] + [""] * (len(dims) - 1)
    for i, _ in enumerate(metrics):
        col = [r[len(dims) + i] for r in rows]
        totals.append(sum(col, Decimal("0")) if col and isinstance(col[0], Decimal) else sum(col))
    headers = [DIMENSIONS[d][0] for d in dims] + [METRICS[m] for m in metrics]
    return headers, rows, totals, keys


def drilldown_params(dims, key, granularity="month", period_field="created_at"):
    """Hisobot qatoridan ishlar ro'yxatiga o'tish uchun filtr parametrlari."""
    from datetime import timedelta

    params = {}
    mapping = {
        "organization": "organization", "org_type": "org_type", "region": "region", "court_type": "court_type",
        "court": "court", "instance": "instance", "category": "category", "role": "role", "status": "status",
        "outcome": "outcome", "agency_result": "agency_result", "responsible": "responsible",
    }
    for d in dims:
        lookup = DIMENSIONS[d][1]
        value = key.get(lookup)
        if d in mapping and value not in (None, ""):
            params[mapping[d]] = value
        elif d == "state":
            params["state"] = "closed" if value else "open"
        elif d == "period" and value is not None and period_field == "created_at":
            start = value.date() if hasattr(value, "date") else value
            if granularity == "day":
                end = start
            elif granularity == "week":
                end = start + timedelta(days=6)
            elif granularity == "month":
                end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            elif granularity == "quarter":
                m = start.month + 3
                end = (start.replace(year=start.year + (m - 1) // 12, month=(m - 1) % 12 + 1, day=1)) - timedelta(days=1)
            else:
                end = start.replace(month=12, day=31)
            params["created_from"] = start.isoformat()
            params["created_to"] = end.isoformat()
        elif d == "claim_bucket":
            bounds = {"1": (None, 9_999_999.99), "2": (10_000_000, 49_999_999.99), "3": (50_000_000, 99_999_999.99),
                      "4": (100_000_000, 499_999_999.99), "5": (500_000_000, 999_999_999.99), "6": (1_000_000_000, None)}
            lo, hi = bounds.get(value, (None, None))
            if lo is not None:
                params["claim_min"] = lo
            if hi is not None:
                params["claim_max"] = hi
    return params
