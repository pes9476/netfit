import json
import os
from pathlib import Path

try:
    import dj_database_url
except ImportError:
    dj_database_url = None
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / "netfit_gemini.local.env")

def env_bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name):
    return [value.strip() for value in os.getenv(name, "").split(",") if value.strip()]


ON_RENDER = env_bool("RENDER") or bool(os.getenv("RENDER_EXTERNAL_HOSTNAME"))
ON_DEPLOYMENT = ON_RENDER
DEBUG = env_bool("DEBUG", not ON_DEPLOYMENT)
SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Set SECRET_KEY before starting with DEBUG=False.")
    SECRET_KEY = "django-insecure-local-development-only-netfit"
PUBLIC_DOMAIN = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")
if DEBUG:
    ALLOWED_HOSTS += ["127.0.0.1", "localhost", "testserver"]
if PUBLIC_DOMAIN:
    ALLOWED_HOSTS.append(PUBLIC_DOMAIN)
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
if PUBLIC_DOMAIN:
    CSRF_TRUSTED_ORIGINS.append(f"https://{PUBLIC_DOMAIN}")
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", not DEBUG)
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "fitness.apps.FitnessConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "fitness.context_processors.quest_menu",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"
USE_SQLITE = env_bool("USE_SQLITE")
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if ON_DEPLOYMENT and (USE_SQLITE or not (DATABASE_URL or os.getenv("POSTGRES_DB"))):
    raise ImproperlyConfigured(
        "Deployed environments require PostgreSQL: set DATABASE_URL and unset USE_SQLITE."
    )
if DATABASE_URL and not USE_SQLITE:
    DATABASES = {"default": dj_database_url.parse(
        DATABASE_URL, conn_max_age=600,
    )}
elif os.getenv("POSTGRES_DB") and not USE_SQLITE:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["POSTGRES_DB"],
            "USER": os.getenv("POSTGRES_USER", "netfit_user"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
if DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
    # Compatible with Supabase transaction poolers as well as direct PostgreSQL.
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
    DATABASES["default"].setdefault("OPTIONS", {}).update({
        "prepare_threshold": None,
        "connect_timeout": 5,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    })

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "netfit-cache",
    }
}
AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if (ON_DEPLOYMENT and not DEBUG)
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", str(BASE_DIR / "media")))
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "dashboard"

_kakao_file = BASE_DIR / "kakao.local.json"
_kakao_local = json.loads(_kakao_file.read_text(encoding="utf-8")) if _kakao_file.exists() else {}
KAKAO_REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "").strip() or _kakao_local.get("KAKAO_REST_API_KEY", "").strip()
KAKAO_CLIENT_SECRET = os.environ.get("KAKAO_CLIENT_SECRET", "").strip() or _kakao_local.get("KAKAO_CLIENT_SECRET", "").strip()
KAKAO_REDIRECT_URI = (
    os.environ.get("KAKAO_REDIRECT_URI", "").strip()
    or _kakao_local.get("KAKAO_REDIRECT_URI", "").strip()
    or (f"https://{PUBLIC_DOMAIN}/login/kakao/callback/" if PUBLIC_DOMAIN
        else "http://127.0.0.1:8000/login/kakao/callback/")
)

# --------------------------------------------------------------------------
# 🤖 NetFit 핏봇 (Groq & Gemini AI Chatbot) 설정
# --------------------------------------------------------------------------
def _clean_str(val):
    if not val:
        return ""
    val = val.strip()
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        val = val[1:-1].strip()
    return val

_groq_local_file = BASE_DIR / "netfit_groq.local.env"
if _groq_local_file.exists():
    try:
        for _line in _groq_local_file.read_text(encoding="utf-8").splitlines():
            if _line.startswith("GROQ_API_KEY="):
                _k = _clean_str(_line.split("=", 1)[1])
                if _k and not os.getenv("GROQ_API_KEY"):
                    os.environ["GROQ_API_KEY"] = _k
    except Exception:
        pass

GROQ_API_KEY = (
    _clean_str(os.getenv("GROQ_API_KEY"))
    or _clean_str(os.getenv("GROQ_KEY"))
)
GROQ_MODEL = _clean_str(os.getenv("GROQ_MODEL")) or "openai/gpt-oss-20b"
GEMINI_API_KEY = (
    _clean_str(os.getenv("GEMINI_API_KEY"))
    or _clean_str(os.getenv("GEMINI_KEY"))
    or _clean_str(os.getenv("GOOGLE_API_KEY"))
)
GEMINI_MODEL = _clean_str(os.getenv("GEMINI_MODEL")) or "gemini-1.5-flash"
FITBOT_REQUIRE_LOGIN = True
FITBOT_REGIONS = [
    "서울특별시", "경기도", "인천광역시", "부산광역시", "대구광역시",
    "대전광역시", "광주광역시", "울산광역시", "세종특별자치시", "강원특별자치도",
    "충청북도", "충청남도", "전북특별자치도", "전라남도", "경상북도",
    "경상남도", "제주특별자치도",
]
FITBOT_FACILITY_SEARCH = "fitness.services.search_facilities_for_fitbot"


