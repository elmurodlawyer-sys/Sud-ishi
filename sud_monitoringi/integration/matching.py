"""Sud ishi ishtirokchilari orasidan Agentlik tizimidagi tashkilotlarni aniqlash."""
from dataclasses import dataclass, field

from core.models import Classifier, ClassifierKind, Organization
from core.normalize import contains_phrase, extract_stirs, normalize_name

ROLE_FIELDS = [("plaintiffs", "davogar"), ("defendants", "javobgar"), ("third_parties", "uchinchi")]
MIN_KEY_LENGTH = 6


@dataclass
class Match:
    organization: Organization
    role: str
    key_length: int
    depth: int


@dataclass
class MatchResult:
    primary: Match
    others: list = field(default_factory=list)


class OrganizationMatcher:
    """Tashkilotning to'liq, qisqa, oldingi va muqobil nomlari hamda STIR bo'yicha moslaydi.

    Bir nechta tashkilotga tegishli umumiy kalitlar (masalan, faqat "Inson ijtimoiy
    xizmatlar markazi") noaniq hisoblanadi va e'tiborga olinmaydi.
    """

    def __init__(self, organizations=None):
        orgs = list(organizations if organizations is not None else Organization.objects.filter(is_active=True))
        self.by_pk = {o.pk: o for o in orgs}
        key_owners = {}
        for org in orgs:
            for key in (org.match_keys or "").splitlines():
                if len(key) >= MIN_KEY_LENGTH:
                    key_owners.setdefault(key, set()).add(org.pk)
        self.keys = sorted(
            ((key, next(iter(owners))) for key, owners in key_owners.items() if len(owners) == 1),
            key=lambda item: -len(item[0]),
        )
        self.by_stir = {o.stir: o.pk for o in orgs if o.stir}
        self._depth = {}

    def depth(self, org):
        if org.pk not in self._depth:
            d, node = 0, org
            while node.parent_id and d < 20:
                d += 1
                node = self.by_pk.get(node.parent_id) or node.parent
            self._depth[org.pk] = d
        return self._depth[org.pk]

    def find_in_text(self, text):
        """Matndagi tashkilotlar: {org_pk: eng uzun mos kalit uzunligi}."""
        found = {}
        norm = normalize_name(text)
        if not norm:
            return found
        for key, org_pk in self.keys:
            if org_pk not in found and contains_phrase(norm, key):
                found[org_pk] = len(key)
        for stir in extract_stirs(text):
            if stir in self.by_stir:
                found.setdefault(self.by_stir[stir], 100)
        return found

    def match(self, record):
        matches = {}
        for field_name, role in ROLE_FIELDS:
            for org_pk, key_len in self.find_in_text(record.get(field_name, "")).items():
                if org_pk not in matches:
                    org = self.by_pk[org_pk]
                    matches[org_pk] = Match(org, role, key_len, self.depth(org))
        if not matches:
            return None
        # Asosiy tashkilot: avval bevosita taraf (da'vogar/javobgar), so'ng ierarxiyada eng quyi
        # (eng aniq) tashkilot, so'ng eng uzun mos kelgan nom
        ordered = sorted(
            matches.values(), key=lambda m: (m.role == "uchinchi", -m.depth, -m.key_length)
        )
        return MatchResult(primary=ordered[0], others=ordered[1:])


# --- Matnni klassifikatorga moslash --------------------------------------------

def _classifier_by_keywords(kind, text, rules, default=None):
    norm = normalize_name(text)
    for keyword, code in rules:
        if keyword in norm:
            return Classifier.get(kind, code)
    if norm:
        for c in Classifier.objects.filter(kind=kind, is_active=True):
            if normalize_name(c.name) == norm:
                return c
    return Classifier.get(kind, default) if default else None


def instance_from_text(text):
    rules = [("apell", "apellyatsiya"), ("kassats", "kassatsiya"), ("taftis", "taftish"), ("nazorat", "taftish"),
             ("yangi ochilgan", "boshqa"), ("birinchi", "birinchi"), ("1 instan", "birinchi")]
    return _classifier_by_keywords(ClassifierKind.INSTANCE, text, rules, default="birinchi")


def court_type_from_text(text):
    rules = [("iqtisod", "iqtisodiy"), ("xojalik", "iqtisodiy"), ("mamuriy", "mamuriy"), ("jinoyat", "jinoyat"),
             ("fuqarolik", "fuqarolik"), ("oliy sud", "oliy"), ("ekonomich", "iqtisodiy"), ("administrativ", "mamuriy"),
             ("grazhdansk", "fuqarolik"), ("ugolovn", "jinoyat")]
    return _classifier_by_keywords(ClassifierKind.COURT_TYPE, text, rules)


def region_from_text(text):
    norm = normalize_name(text)
    if not norm:
        return None
    if "toshkent shaxar" in norm or "toshkent sh" in norm or "tashkent city" in norm:
        return Classifier.get(ClassifierKind.REGION, "toshkent-sh")
    if "toshkent viloyat" in norm:
        return Classifier.get(ClassifierKind.REGION, "toshkent-v")
    for region in Classifier.objects.filter(kind=ClassifierKind.REGION, is_active=True):
        first = normalize_name(region.name).split(" ")[0]
        if len(first) >= 5 and first != "toshkent" and first in norm:
            return region
    if "toshkent" in norm:
        return Classifier.get(ClassifierKind.REGION, "toshkent-sh")
    return None


def category_from_text(text):
    norm = normalize_name(text)
    if not norm:
        return None
    best, best_score = None, 0
    for c in Classifier.objects.filter(kind=ClassifierKind.CASE_CATEGORY, is_active=True):
        cname = normalize_name(c.name)
        if cname == norm:
            return c
        words = [w for w in cname.split() if len(w) >= 5]
        score = sum(1 for w in words if w[:5] in norm)
        if score > best_score:
            best, best_score = c, score
    return best
