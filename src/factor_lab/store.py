from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.runner.config_loader import PROJECT_ROOT, resolve_project_path


def canonical_config_for_hash(config: dict) -> dict[str, Any]:
    keys = [
        "schema_version",
        "factor_id",
        "implementation",
        "version",
        "params",
        "preprocess",
        "period",
        "universe",
    ]
    return {
        key: config.get(key)
        for key in keys
    }


def calculate_config_hash(config: dict) -> str:
    payload = json.dumps(
        canonical_config_for_hash(config),
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class FactorStore:
    """
    File-backed cache for raw and processed factor data.

    Version one only reuses exact config-hash matches.
    """

    def __init__(
        self,
        root: str | Path = "data/factor",
    ):
        self.root = resolve_project_path(root)

    def cache_dir(
        self,
        config: dict,
        config_hash: str | None = None,
    ) -> Path:
        factor_id = config["factor_id"]
        version = config.get("version", 1)
        hash_value = config_hash or calculate_config_hash(config)

        return (
            self.root
            / factor_id
            / f"version={version}"
            / f"config_hash={hash_value}"
        )

    def has_cache(
        self,
        config: dict,
    ) -> bool:
        path = self.cache_dir(config)
        return (
            (path / "raw_factor.parquet").exists()
            and (path / "processed_factor.parquet").exists()
            and (path / "manifest.json").exists()
        )

    def load(
        self,
        config: dict,
    ) -> dict[str, Any]:
        path = self.cache_dir(config)

        if not self.has_cache(config):
            raise FileNotFoundError(f"Factor cache does not exist: {path}")

        manifest = json.loads(
            (path / "manifest.json").read_text(encoding="utf-8")
        )
        return {
            "raw_factor": pd.read_parquet(path / "raw_factor.parquet"),
            "processed_factor": pd.read_parquet(path / "processed_factor.parquet"),
            "manifest": manifest,
            "cache_dir": path,
            "config_hash": manifest["config_hash"],
        }

    def save(
        self,
        config: dict,
        raw_factor: pd.DataFrame,
        processed_factor: pd.DataFrame,
    ) -> dict[str, Any]:
        config_hash = calculate_config_hash(config)
        path = self.cache_dir(config, config_hash=config_hash)
        path.mkdir(parents=True, exist_ok=True)

        raw_factor.to_parquet(path / "raw_factor.parquet", index=False)
        processed_factor.to_parquet(
            path / "processed_factor.parquet",
            index=False,
        )

        date_min = None
        date_max = None
        if not raw_factor.empty and "trade_date" in raw_factor.columns:
            dates = pd.to_datetime(raw_factor["trade_date"])
            date_min = str(dates.min().date())
            date_max = str(dates.max().date())

        period = config.get("period", {})
        manifest = {
            "factor_id": config.get("factor_id"),
            "implementation": config.get("implementation"),
            "version": config.get("version"),
            "params": config.get("params", {}),
            "preprocess": config.get("preprocess", {}),
            "start": period.get("start"),
            "end": period.get("end"),
            "config_hash": config_hash,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "row_count": int(len(raw_factor)),
            "date_min": date_min,
            "date_max": date_max,
        }

        (path / "manifest.json").write_text(
            json.dumps(
                manifest,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return {
            "manifest": manifest,
            "cache_dir": path,
            "config_hash": config_hash,
        }
