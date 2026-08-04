from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "fastpheno"
PARQUET_DIR = DATA_DIR / "parquet"

# Max rows per paginated API response
MAX_PAGE_SIZE = 500
DEFAULT_PAGE_SIZE = 50
# Full filtered table loads (UAV / campaign sensors)
UAV_MAX_TABLE_ROWS = 100_000
CAMPAIGN_MAX_TABLE_ROWS = 50_000
