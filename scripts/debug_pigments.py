from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import config
from backend.services import pigments

print('CONFIG_PATH', config.__file__)
print('PIGMENTS_ROOT', config.PIGMENTS_ROOT)
print('EXISTS', config.PIGMENTS_ROOT.exists())
if config.PIGMENTS_ROOT.exists():
    print('TOP_LEVEL', [p.name for p in list(config.PIGMENTS_ROOT.iterdir())[:20]])

try:
    campaigns = pigments.list_campaigns(site='PIN')
    print('CAMPAIGNS', len(campaigns))
    for c in campaigns[:10]:
        print(c)
    print('FILTER_2023_06_21_22', pigments.filter_campaigns(campaigns, date_from='2023-06-21', date_to='2023-06-22')[:5])
except Exception as exc:
    print('ERROR', type(exc).__name__, exc)
    raise
