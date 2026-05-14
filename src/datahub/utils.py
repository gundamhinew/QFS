from __future__ import annotations

from pathlib import Path
from datetime import datetime
import yaml


def load_settings(path: str = "config/settings.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def yyyymmdd_to_datetime(series):
    return series.astype(str).pipe(lambda s: __import__("pandas").to_datetime(s, format="%Y%m%d", errors="coerce"))