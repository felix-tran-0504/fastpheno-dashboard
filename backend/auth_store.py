import hashlib
import hmac
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from . import config


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _hash_pin(pin: str) -> str:
    return hmac.new(
        config.SECRET_KEY.encode(),
        pin.encode(),
        hashlib.sha256,
    ).hexdigest()


def init_db() -> None:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS pin_codes (
                email TEXT PRIMARY KEY,
                pin_hash TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
            """
        )


@contextmanager
def _conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def email_allowed(email: str) -> bool:
    email = email.strip().lower()
    if not config.ALLOWED_EMAILS:
        return True
    return email in config.ALLOWED_EMAILS


def create_pin(email: str) -> str:
    pin = f"{secrets.randbelow(1_000_000):06d}"
    expires = _utcnow() + timedelta(minutes=config.PIN_MINUTES)
    normalized = email.strip().lower()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO pin_codes (email, pin_hash, expires_at) VALUES (?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                pin_hash = excluded.pin_hash,
                expires_at = excluded.expires_at
            """,
            (normalized, _hash_pin(pin), _iso(expires)),
        )
    return pin


def verify_pin(email: str, pin: str) -> bool:
    normalized = email.strip().lower()
    pin = pin.strip()
    if len(pin) != 6 or not pin.isdigit():
        return False
    now = _iso(_utcnow())
    with _conn() as conn:
        row = conn.execute(
            "SELECT pin_hash, expires_at FROM pin_codes WHERE email = ?",
            (normalized,),
        ).fetchone()
        if not row or row["expires_at"] < now:
            return False
        if not hmac.compare_digest(row["pin_hash"], _hash_pin(pin)):
            return False
        conn.execute("DELETE FROM pin_codes WHERE email = ?", (normalized,))
        return True


def create_session(email: str) -> str:
    session_id = secrets.token_urlsafe(32)
    expires = _utcnow() + timedelta(days=config.SESSION_DAYS)
    with _conn() as conn:
        conn.execute(
            "INSERT INTO sessions (session_id, email, expires_at) VALUES (?, ?, ?)",
            (session_id, email.strip().lower(), _iso(expires)),
        )
    return session_id


def get_session_email(session_id: str | None) -> str | None:
    if not session_id:
        return None
    now = _iso(_utcnow())
    with _conn() as conn:
        row = conn.execute(
            "SELECT email, expires_at FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if not row or row["expires_at"] < now:
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            return None
        return row["email"]


def delete_session(session_id: str | None) -> None:
    if not session_id:
        return
    with _conn() as conn:
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
