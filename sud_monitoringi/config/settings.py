"""
"Sud monitoringi" axborot tizimi sozlamalari.

Barcha muhim parametrlar muhit o'zgaruvchilari (environment variables) orqali
beriladi. Namuna uchun `.env.example` faylini ko'ring.
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file(path):
    """Oddiy .env o'quvchi (tashqi kutubxonasiz)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file(BASE_DIR / ".env")


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "ha", "on")


def env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


DEBUG = env_bool("DEBUG", False)
SECRET_KEY = env("SECRET_KEY") or ("dev-insecure-key-faqat-sinov-uchun" if DEBUG else None)
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY muhit o'zgaruvchisi berilmagan (ishchi rejimda majburiy).")

ALLOWED_HOSTS = [h.strip() for h in env("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [h.strip() for h in env("CSRF_TRUSTED_ORIGINS", "").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "accounts",
    "core",
    "cases",
    "integration",
    "notifications",
    "reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "accounts.middleware.AuditMiddleware",
]

# Statik fayllarni gunicorn orqali berish (nginx sozlanmagan bo'lsa ham ishlaydi)
try:
    import whitenoise  # noqa: F401

    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
except ImportError:  # pragma: no cover
    pass

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "notifications.context_processors.notifications",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Ma'lumotlar bazasi -----------------------------------------------------
# DB_ENGINE=postgres bo'lsa PostgreSQL, aks holda SQLite ishlatiladi.
if env("DB_ENGINE", "sqlite").lower() in ("postgres", "postgresql"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME", "sud_monitoringi"),
            "USER": env("DB_USER", "sud_monitoringi"),
            "PASSWORD": env("DB_PASSWORD", ""),
            "HOST": env("DB_HOST", "localhost"),
            "PORT": env("DB_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    SQLITE_PATH = Path(env("SQLITE_PATH", str(BASE_DIR / "data" / "db.sqlite3")))
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(SQLITE_PATH),
        }
    }

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "reports:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

if "test" in sys.argv:
    # Testlarni tezlashtirish uchun (faqat test rejimida)
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Ketma-ket noto'g'ri kirish urinishlari bo'yicha bloklash
LOGIN_MAX_ATTEMPTS = env_int("LOGIN_MAX_ATTEMPTS", 5)
LOGIN_LOCK_MINUTES = env_int("LOGIN_LOCK_MINUTES", 15)

LANGUAGE_CODE = "uz"
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True
USE_THOUSAND_SEPARATOR = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Yuklangan hujjatlar ommaga ochiq emas: faqat huquq tekshiruvidan keyin
# maxsus view orqali beriladi.
MEDIA_ROOT = Path(env("MEDIA_ROOT", str(BASE_DIR / "data" / "media")))
BACKUP_ROOT = Path(env("BACKUP_ROOT", str(BASE_DIR / "data" / "backups")))
REPORTS_ROOT = Path(env("REPORTS_ROOT", str(BASE_DIR / "data" / "reports")))

DOCUMENT_MAX_SIZE_MB = env_int("DOCUMENT_MAX_SIZE_MB", 25)
DOCUMENT_ALLOWED_EXTENSIONS = [
    "pdf", "doc", "docx", "xls", "xlsx", "odt", "rtf", "txt", "jpg", "jpeg", "png", "tif", "tiff", "zip",
]
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Sessiya va xavfsizlik ---------------------------------------------------
SESSION_COOKIE_AGE = env_int("SESSION_COOKIE_AGE", 8 * 60 * 60)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

if not DEBUG:
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", True)
    CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", True)
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)
    SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 0)
    if env_bool("BEHIND_PROXY", False):
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# --- Elektron pochta (ixtiyoriy) ---------------------------------------------
EMAIL_NOTIFICATIONS = env_bool("EMAIL_NOTIFICATIONS", False)
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "sud-monitoringi@localhost")
SITE_URL = env("SITE_URL", "http://localhost:8000")

# --- Monitoring parametrlari -------------------------------------------------
# Sud majlisi / muddat yaqinlashganda necha kun oldin ogohlantirish
HEARING_REMINDER_DAYS = env_int("HEARING_REMINDER_DAYS", 3)
DEADLINE_REMINDER_DAYS = env_int("DEADLINE_REMINDER_DAYS", 5)
# Necha kun yangilanmagan ish "uzoq muddat yangilanmagan" hisoblanadi
STALE_CASE_DAYS = env_int("STALE_CASE_DAYS", 30)
# Kunlik avtomatik zaxira nusxa soati (run_scheduler uchun)
BACKUP_HOUR = env_int("BACKUP_HOUR", 2)
# Integratsiya tashqi so'rovlari uchun kutish vaqti (soniya)
INTEGRATION_HTTP_TIMEOUT = env_int("INTEGRATION_HTTP_TIMEOUT", 30)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    "loggers": {"django.db.backends": {"level": "WARNING"}},
}
