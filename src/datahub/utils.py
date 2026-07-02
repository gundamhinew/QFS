from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import yaml


def load_datahub_config(path: str = "configs/datahub.yaml") -> dict:
    config_path = Path(path)
    fallback_paths = [
        Path("configs/datahub/settings.yaml"),
        Path("config/settings.yaml"),
    ]

    if not config_path.exists() and path == "configs/datahub.yaml":
        for fallback_path in fallback_paths:
            if fallback_path.exists():
                config_path = fallback_path
                break

    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    return _normalize_datahub_config(config)


def _normalize_datahub_config(config: dict) -> dict:
    update = config.get("update", {})
    tushare = config.setdefault("tushare", {})
    calendar = config.setdefault("calendar", {})
    daily = config.setdefault("daily", {})
    financial = config.setdefault("financial", {})

    if "sleep_seconds" not in tushare and "sleep_seconds" in update:
        tushare["sleep_seconds"] = update["sleep_seconds"]
    tushare.setdefault("sleep_seconds", 0.2)

    if "default_start" not in calendar and "start_date" in update:
        calendar["default_start"] = update["start_date"]
    if "exchange" not in calendar and "exchange" in update:
        calendar["exchange"] = update["exchange"]
    calendar.setdefault("default_start", "20180101")
    calendar.setdefault("exchange", "SSE")

    if "default_start" not in daily and "start_date" in update:
        daily["default_start"] = update["start_date"]
    daily.setdefault("default_start", calendar["default_start"])

    financial.setdefault("default_start", None)
    financial.setdefault("default_end", None)

    return config


def load_settings(path: str = "configs/datahub.yaml") -> dict:
    return load_datahub_config(path)


def resolve_tushare_token(settings: dict, token_override: str | None = None) -> str:
    token = (
        token_override
        or os.getenv("TUSHARE_TOKEN")
        or settings.get("tushare", {}).get("token", "")
    )
    token = str(token).strip()

    if not token or (token.startswith("{") and token.endswith("}")):
        raise ValueError(
            "Tushare token is required. Pass --token YOUR_TOKEN, "
            "set TUSHARE_TOKEN, or set tushare.token in configs/datahub.yaml."
        )

    return token


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_yyyymmdd() -> str:
    return datetime.now().strftime("%Y%m%d")


def validate_yyyymmdd(value: str, name: str) -> str:
    try:
        datetime.strptime(value, "%Y%m%d")
    except ValueError as exc:
        raise ValueError(f"{name} must be YYYYMMDD, got {value!r}") from exc
    return value


def yyyymmdd_to_datetime(series):
    return series.astype(str).pipe(lambda s: __import__("pandas").to_datetime(s, format="%Y%m%d", errors="coerce"))
