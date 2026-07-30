import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
_ENV_FILE = ROOT / "backend" / ".env"
load_dotenv(_ENV_FILE, override=True)

DATA_DIR = ROOT / "data" / "fastpheno"
DB_PATH = Path(os.environ.get("FASTPHENO_AUTH_DB", ROOT / "backend" / "auth.db"))

SECRET_KEY = os.environ.get("FASTPHENO_SECRET_KEY", "dev-change-me-in-production")
SESSION_COOKIE = "fastpheno_session"
SESSION_DAYS = int(os.environ.get("FASTPHENO_SESSION_DAYS", "7"))
PIN_MINUTES = int(
    os.environ.get("FASTPHENO_PIN_MINUTES")
    or os.environ.get("FASTPHENO_MAGIC_LINK_MINUTES", "15")
)

BASE_URL = os.environ.get("FASTPHENO_BASE_URL", "http://localhost:8000").rstrip("/")

# Comma-separated allow-list. Empty = allow any email (dev only).
_allowed = os.environ.get("FASTPHENO_ALLOWED_EMAILS", "").strip()
ALLOWED_EMAILS = {e.strip().lower() for e in _allowed.split(",") if e.strip()} if _allowed else set()

# If true, PINs also print to the server console and login page.
_dev_print = os.environ.get("FASTPHENO_DEV_PRINT_PINS") or os.environ.get("FASTPHENO_DEV_PRINT_LINKS", "1")
DEV_PRINT_PINS = _dev_print == "1"

SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER or "fastpheno@localhost").strip()
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "1") == "1"
SMTP_USE_SSL = os.environ.get("SMTP_USE_SSL", "0") == "1"
SMTP_TIMEOUT = int(os.environ.get("SMTP_TIMEOUT", "30"))

# When SMTP fails on localhost, show the PIN on the login page instead of blocking sign-in.
_smtp_fallback = os.environ.get("FASTPHENO_SMTP_FALLBACK_DEV")
if _smtp_fallback is None:
    SMTP_FALLBACK_DEV = "localhost" in BASE_URL or "127.0.0.1" in BASE_URL
else:
    SMTP_FALLBACK_DEV = _smtp_fallback == "1"


def smtp_configured() -> bool:
    return bool(SMTP_HOST and SMTP_FROM)


def email_delivery_mode() -> str:
    if smtp_configured() and not DEV_PRINT_PINS:
        return "smtp"
    if DEV_PRINT_PINS:
        return "dev"
    return "none"
