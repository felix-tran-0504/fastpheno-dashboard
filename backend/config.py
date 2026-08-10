from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "fastpheno"
PARQUET_DIR = DATA_DIR / "parquet"

_DEFAULT_PIGMENTS_ROOT = Path("/Users/felixtran/Downloads/III_db_final/Pigments")
PIGMENTS_ROOT = Path(os.environ.get("FASTPHENO_PIGMENTS_ROOT", _DEFAULT_PIGMENTS_ROOT)).expanduser()

# Max rows per paginated API response
MAX_PAGE_SIZE = 500
DEFAULT_PAGE_SIZE = 50
# Full filtered table loads (UAV / campaign sensors)
UAV_MAX_TABLE_ROWS = 250_000
CAMPAIGN_MAX_TABLE_ROWS = 50_000
SOIL_MOISTURE_MAX_TABLE_ROWS = 350_000
