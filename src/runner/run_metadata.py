from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import subprocess
from typing import Any

import pandas as pd


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")


def calculate_full_config_hash(config: dict[str, Any]) -> str:
    payload = json.dumps(
        config,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def get_git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None

    commit = result.stdout.strip()
    return commit or None


def row_count(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, pd.DataFrame):
        return int(len(value))
    try:
        return int(len(value))
    except Exception:
        return None


def row_counts(**frames: Any) -> dict[str, int]:
    counts = {}
    for name, value in frames.items():
        count = row_count(value)
        if count is not None:
            counts[name] = count
    return counts


def config_period(config: dict[str, Any]) -> tuple[Any, Any]:
    period = config.get("period", {})
    if isinstance(period, dict):
        return period.get("start"), period.get("end")

    backtest = config.get("backtest", {})
    if isinstance(backtest, dict):
        return backtest.get("start"), backtest.get("end")

    return None, None


def base_run_manifest(
    *,
    run_id: str,
    run_type: str,
    started_at: str,
    finished_at: str,
    config_path: str,
    config: dict[str, Any],
    status: str,
    error_message: str | None,
    rows: dict[str, int] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    start, end = config_period(config)
    manifest = {
        "run_id": run_id,
        "run_type": run_type,
        "started_at": started_at,
        "finished_at": finished_at,
        "config_path": config_path,
        "config_hash": calculate_full_config_hash(config),
        "git_commit": get_git_commit(),
        "start": start,
        "end": end,
        "row_counts": rows or {},
        "status": status,
        "error_message": error_message,
    }
    if extra:
        manifest.update(extra)
    return manifest
