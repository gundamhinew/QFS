from __future__ import annotations

from pathlib import Path

from src.factor_lab.catalog import FactorCatalog
from src.runner.config_loader import load_factor_config


class ModelChecker:
    REQUIRED_KEYS = [
        "schema_version",
        "model_id",
        "model_type",
        "version",
        "status",
        "factors",
        "alignment",
        "evaluation",
        "output",
    ]

    def __init__(
        self,
        catalog: FactorCatalog | None = None,
    ):
        self.catalog = catalog or FactorCatalog()

    def check(self, config: dict) -> None:
        missing = [
            key
            for key in self.REQUIRED_KEYS
            if key not in config
        ]
        if missing:
            raise ValueError(f"Model config missing required keys: {missing}")

        if config.get("schema_version") != 2:
            raise ValueError("Model config must use schema_version: 2")

        factors = config.get("factors")
        if not isinstance(factors, list) or not factors:
            raise ValueError("Model config factors must be a non-empty list")

        factor_ids = []
        aliases = []

        for item in factors:
            if not isinstance(item, dict):
                raise ValueError("Each factor entry must be a mapping")

            factor_id = item.get("factor_id")
            alias = item.get("alias") or factor_id

            if not factor_id:
                raise ValueError("Each factor entry requires factor_id")
            if not alias:
                raise ValueError("Each factor entry requires alias or factor_id")

            factor_ids.append(factor_id)
            aliases.append(alias)

        duplicates = {
            factor_id
            for factor_id in factor_ids
            if factor_ids.count(factor_id) > 1
        }
        if duplicates:
            raise ValueError(f"Duplicate factor_id in model config: {sorted(duplicates)}")

        duplicate_aliases = {
            alias
            for alias in aliases
            if aliases.count(alias) > 1
        }
        if duplicate_aliases:
            raise ValueError(f"Duplicate factor alias in model config: {sorted(duplicate_aliases)}")

        allow_unapproved = bool(
            config.get("evaluation", {}).get("allow_unapproved", False)
        )

        for item in factors:
            factor_id = item["factor_id"]
            config_path = item.get("config")

            try:
                entry = self.catalog.get_entry(factor_id)
                status = entry.status
            except KeyError:
                factor_config = load_factor_config(config_path) if config_path else None
                if not factor_config:
                    raise
                if factor_config.get("factor_id") != factor_id:
                    raise
                status = factor_config.get("status", "draft")
            else:
                factor_config = load_factor_config(config_path) if config_path else None
                if factor_config and factor_config.get("factor_id") != factor_id:
                    raise ValueError(
                        f"Factor config {config_path} does not match factor_id {factor_id}"
                    )

            if status == "deprecated":
                raise ValueError(f"Factor '{factor_id}' is deprecated")

            if status != "approved" and not allow_unapproved:
                raise ValueError(
                    f"Factor '{factor_id}' has status '{status}'. "
                    "Only approved factors are allowed unless allow_unapproved=true."
                )
