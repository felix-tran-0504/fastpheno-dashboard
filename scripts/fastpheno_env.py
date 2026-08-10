"""Load backend/.env and resolve local / remote FastPheno paths."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "backend" / ".env"
DATA_DIR = ROOT / "data" / "fastpheno"

_DEFAULT_LOCAL_III = Path.home() / "III_db_final_sync"
_FALLBACK_LOCAL_III = Path.home() / "Downloads" / "III_db_final"


def load_env() -> None:
    """Load backend/.env into os.environ (no-op if missing or dotenv unavailable)."""
    if not ENV_FILE.is_file():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(ENV_FILE)
    except ImportError:
        pass


def get_iii_db_root() -> Path:
    """
    Local III_db_final tree used by prep scripts.
    Set FASTPHENO_III_DB_ROOT in backend/.env (sync target from ffgg-fastpheno2).
    """
    load_env()
    raw = os.environ.get("FASTPHENO_III_DB_ROOT") or os.environ.get("FASTPHENO_LOCAL_III_DB_STAGING")
    if raw:
        return Path(raw).expanduser()
    if _FALLBACK_LOCAL_III.is_dir():
        return _FALLBACK_LOCAL_III
    return _DEFAULT_LOCAL_III


def get_remote_config() -> dict[str, str | int]:
    """SSH/SFTP settings for ffgg-fastpheno2 (password or key)."""
    load_env()

    def _env(name: str, fallback: str = "") -> str:
        value = os.environ.get(name)
        if value is not None and value != "":
            return value
        return fallback

    # Legacy aliases from early .env.example
    host = _env("FASTPHENO_REMOTE_HOST") or _env("SFTP_HOST")
    user = _env("FASTPHENO_REMOTE_USER") or _env("SFTP_USER")
    password = _env("FASTPHENO_REMOTE_PASSWORD") or _env("SFTP_PASSWORD")
    remote_path = (
        _env("FASTPHENO_REMOTE_III_DB_PATH")
        or _env("SFTP_REMOTE_III_DB_PATH")
        or "III_db_final"
    )
    port_raw = _env("FASTPHENO_REMOTE_PORT") or _env("SFTP_PORT") or "22"
    key_path = _env("FASTPHENO_REMOTE_SSH_KEY") or _env("SFTP_SSH_KEY")

    return {
        "host": host,
        "port": int(port_raw),
        "user": user,
        "password": password,
        "remote_path": remote_path,
        "ssh_key": key_path,
        "local_root": str(get_iii_db_root()),
    }


def require_remote_config() -> dict[str, str | int]:
    cfg = get_remote_config()
    missing: list[str] = []
    if not cfg["host"]:
        missing.append("FASTPHENO_REMOTE_HOST")
    if not cfg["user"]:
        missing.append("FASTPHENO_REMOTE_USER")
    if not cfg["password"] and not cfg["ssh_key"]:
        missing.append("FASTPHENO_REMOTE_PASSWORD (or FASTPHENO_REMOTE_SSH_KEY)")
    if missing:
        names = ", ".join(missing)
        raise SystemExit(
            f"Missing remote credentials in {ENV_FILE}. Set: {names}\n"
            "See backend/.env.example"
        )
    return cfg
