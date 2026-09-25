"""Tashkilot va sud nomlarini solishtirish uchun normallashtirish.

Sud ishlari manbalarida bir tashkilot nomi turlicha yozilishi mumkin:
kirill/lotin yozuvi, turli tutuq belgilari (‘ ’ ' ʻ `), qo'shtirnoqlar,
"h"/"x" almashinuvi, ortiqcha bo'shliqlar va h.k. Shu sababli ikki tomon
ham bir xil qoidada normallashtirilib, keyin solishtiriladi (3.1-band).
"""
import re
import unicodedata

CYR_TO_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "", "ы": "i", "ь": "", "э": "e", "ю": "yu",
    "я": "ya", "ў": "o", "қ": "q", "ғ": "g", "ҳ": "h",
}

APOSTROPHES = "'`´ʻʼ‘’′ʹ"
QUOTES = "\"«»“”„‟"

_non_alnum = re.compile(r"[^0-9a-z]+")
_spaces = re.compile(r"\s+")


def transliterate(text):
    return "".join(CYR_TO_LAT.get(ch, ch) for ch in text)


def normalize_name(text):
    """Nomni solishtirish kaliti ko'rinishiga keltiradi."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", str(text)).lower()
    text = transliterate(text)
    for ch in APOSTROPHES + QUOTES:
        text = text.replace(ch, "")
    # "h" va "x" ko'pincha almashtirib yoziladi (xizmat/hizmat, hokimiyat/xokimiyat)
    text = text.replace("sh", "\x01").replace("ch", "\x02").replace("h", "x")
    text = text.replace("\x01", "sh").replace("\x02", "ch")
    text = _non_alnum.sub(" ", text)
    return _spaces.sub(" ", text).strip()


def normalize_case_number(text):
    """Sud ishi raqamini solishtirish uchun normallashtiradi (masalan, "2-1001-2601/123")."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", str(text)).lower()
    text = transliterate(text)
    text = text.replace("—", "-").replace("–", "-").replace("№", "")
    text = re.sub(r"\s+", "", text)
    return text.strip()


def contains_phrase(haystack_norm, needle_norm):
    """Normallashtirilgan matnda ibora butun so'zlar sifatida mavjudligini tekshiradi."""
    if not haystack_norm or not needle_norm:
        return False
    return f" {needle_norm} " in f" {haystack_norm} "


STIR_RE = re.compile(r"(?<!\d)(\d{9})(?!\d)")


def extract_stirs(text):
    return set(STIR_RE.findall(text or ""))
