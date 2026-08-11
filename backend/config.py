from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "fastpheno"
PARQUET_DIR = DATA_DIR / "parquet"


def _resolve_pigments_root() -> Path:
    env_root = os.environ.get("FASTPHENO_PIGMENTS_ROOT")
    candidates: list[Path] = []
    if env_root:
        candidates.append(Path(env_root).expanduser())
    candidates.extend(
        [
            Path.home() / "III_db_final_local" / "keep" / "Pigments",
            Path(r"C:\Users\riedelvi\III_db_final_local\keep\Pigments"),
            Path.home() / "Downloads" / "III_db_final" / "Pigments",
            Path(r"C:\Users\riedelvi\Downloads\III_db_final\Pigments"),
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    if env_root:
        return Path(env_root).expanduser()
    return Path.home() / "III_db_final_local" / "keep" / "Pigments"


PIGMENTS_ROOT = _resolve_pigments_root()

# Max rows per paginated API response
MAX_PAGE_SIZE = 500
DEFAULT_PAGE_SIZE = 50
# Full filtered table loads (UAV / campaign sensors)
UAV_MAX_TABLE_ROWS = 250_000
CAMPAIGN_MAX_TABLE_ROWS = 50_000
SOIL_MOISTURE_MAX_TABLE_ROWS = 350_000
# CSV export: client-side JSON below this row count; server stream above (per domain defaults)
CLIENT_EXPORT_MAX_ROWS = 50_000
EXPORT_MAX_ROWS = 500_000
# Domains that always use server-side Parquet → CSV streaming
SERVER_EXPORT_DOMAINS = frozenset({"soil_moisture", "lidar", "gnss"})
