from __future__ import annotations

from datetime import datetime
from pathlib import Path
import yaml


def load_settings(path: str = "configs/datahub/settings.yaml") -> dict:
    settings_path = Path(path)
    legacy_path = Path("config/settings.yaml")

    if not settings_path.exists() and path == "configs/datahub/settings.yaml" and legacy_path.exists():
        settings_path = legacy_path

    with settings_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_tushare_token(settings: dict, token_override: str | None = None) -> str:
    token = token_override or settings.get("tushare", {}).get("token", "")
    token = str(token).strip()

    if not token or (token.startswith("{") and token.endswith("}")):
        raise ValueError(
            "Tushare token is required. Pass --token YOUR_TOKEN, "
            "or set tushare.token in configs/datahub/settings.yaml."
        )

    return token


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def yyyymmdd_to_datetime(series):
    return series.astype(str).pipe(lambda s: __import__("pandas").to_datetime(s, format="%Y%m%d", errors="coerce"))
