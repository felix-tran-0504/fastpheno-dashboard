"""Scan III_db_final Pigments campaign folders and build date-filtered zip exports."""

from __future__ import annotations

import calendar
import os
import re
import tempfile
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .. import config

SITE_FOLDER_TO_CODE = {
    "Pickering": "PIK",
    "Pintendre": "PIN",
}
SITE_CODE_TO_FOLDER = {code: folder for folder, code in SITE_FOLDER_TO_CODE.items()}

_DATE_PART = re.compile(r"^(\d{4})-(\d{2})-(\d{2}|xx)$")


def _parse_date_part(part: str) -> tuple[date, date]:
    part = part.strip()
    match = _DATE_PART.match(part)
    if not match:
        raise ValueError(f"invalid folder date part: {part}")
    year, month = int(match.group(1)), int(match.group(2))
    day_token = match.group(3)
    if day_token == "xx":
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)
    day = int(day_token)
    single = date(year, month, day)
    return single, single


def parse_folder_label(label: str) -> tuple[date, date]:
    """Parse campaign folder names like 2023-12-14 or 2023-06-21_2023-06-22 or 2022-09-xx."""
    parts = label.split("_")
    starts: list[date] = []
    ends: list[date] = []
    for part in parts:
        start, end = _parse_date_part(part)
        starts.append(start)
        ends.append(end)
    return min(starts), max(ends)


def _validate_site(site: str | None) -> str | None:
    if site is None or not str(site).strip():
        return None
    code = str(site).strip().upper()
    if code not in SITE_CODE_TO_FOLDER:
        raise ValueError("site must be PIK, PIN, or omitted for all sites")
    return code


def _parse_bound(value: str | None, *, end_of_day: bool = False) -> date | None:
    if not value or not str(value).strip():
        return None
    raw = str(value).strip()
    if "T" in raw:
        raw = raw.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(raw)
            return dt.date()
        except ValueError as exc:
            raise ValueError("invalid datetime") from exc
    if len(raw) >= 10:
        raw = raw[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("invalid date") from exc


def _ranges_overlap(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    return a_start <= b_end and a_end >= b_start


def _pigments_root() -> Path:
    root = config.PIGMENTS_ROOT
    if not root.is_dir():
        raise FileNotFoundError(f"pigments source not found: {root}")
    return root


def list_campaigns(*, site: str | None = None) -> list[dict[str, Any]]:
    root = _pigments_root()
    site = _validate_site(site)
    campaigns: list[dict[str, Any]] = []
    for folder_name, site_code in SITE_FOLDER_TO_CODE.items():
        if site and site_code != site:
            continue
        site_path = root / folder_name
        if not site_path.is_dir():
            continue
        for entry in sorted(site_path.iterdir()):
            if not entry.is_dir():
                continue
            label = entry.name
            try:
                start, end = parse_folder_label(label)
            except ValueError:
                continue
            file_count = sum(1 for path in entry.rglob("*") if path.is_file())
            campaigns.append(
                {
                    "site": site_code,
                    "label": label,
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                    "file_count": file_count,
                    "relative_path": str(entry.relative_to(root)),
                }
            )
    campaigns.sort(key=lambda row: (row["start_date"], row["site"], row["label"]))
    return campaigns


def filter_campaigns(
    campaigns: list[dict[str, Any]],
    *,
    date_from: str | None,
    date_to: str | None,
) -> list[dict[str, Any]]:
    start = _parse_bound(date_from)
    end = _parse_bound(date_to, end_of_day=True)
    if start and end and start > end:
        raise ValueError("from must be on or before to")
    if not start and not end:
        return list(campaigns)
    filtered: list[dict[str, Any]] = []
    for camp in campaigns:
        camp_start = date.fromisoformat(camp["start_date"])
        camp_end = date.fromisoformat(camp["end_date"])
        query_start = start or date.min
        query_end = end or date.max
        if _ranges_overlap(camp_start, camp_end, query_start, query_end):
            filtered.append(camp)
    return filtered


def get_meta(*, site: str | None = None) -> dict[str, Any]:
    campaigns = list_campaigns(site=site)
    if not campaigns:
        return {
            "domain": "pigments",
            "source_root": str(config.PIGMENTS_ROOT),
            "sites": ["PIK", "PIN"],
            "campaigns": [],
            "bounds": None,
        }
    starts = [c["start_date"] for c in campaigns]
    ends = [c["end_date"] for c in campaigns]
    return {
        "domain": "pigments",
        "source_root": str(config.PIGMENTS_ROOT),
        "sites": ["PIK", "PIN"],
        "campaigns": campaigns,
        "bounds": {"min_date": min(starts), "max_date": max(ends)},
    }


def build_zip(
    *,
    site: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> tuple[Path, str]:
    root = _pigments_root()
    site = _validate_site(site)
    campaigns = filter_campaigns(list_campaigns(site=site), date_from=date_from, date_to=date_to)
    if not campaigns:
        raise ValueError("no pigment campaigns match the selected site and date range")

    site_part = site or "all"
    from_part = (_parse_bound(date_from) or date.min).isoformat()
    to_part = (_parse_bound(date_to, end_of_day=True) or date.max).isoformat()
    filename = f"pigments_{site_part}_{from_part}_to_{to_part}.zip"

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp_path = Path(tmp.name)
    tmp.close()

    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for camp in campaigns:
                folder = root / camp["relative_path"]
                if not folder.is_dir():
                    continue
                prefix = f"{camp['site']}/{camp['label']}"
                for file_path in folder.rglob("*"):
                    if not file_path.is_file():
                        continue
                    arcname = f"{prefix}/{file_path.relative_to(folder).as_posix()}"
                    archive.write(file_path, arcname)
        if tmp_path.stat().st_size == 0:
            raise ValueError("zip archive is empty")
    except Exception:
        if tmp_path.exists():
            os.unlink(tmp_path)
        raise

    return tmp_path, filename
