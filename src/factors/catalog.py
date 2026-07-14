from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.core.config_loader import load_factor_config, resolve_project_path


VALID_FACTOR_STATUSES = {
    "draft",
    "tested",
    "approved",
    "deprecated",
}


@dataclass(frozen=True)
class FactorCatalogEntry:
    factor_id: str
    implementation: str
    version: Any
    status: str
    config_path: Path
    metadata: dict
    has_report: bool


class FactorCatalog:
    def __init__(
        self,
        config_root: str | Path = "configs/factors",
        artifacts_root: str | Path = "artifacts/factor_runs",
    ):
        self.config_root = resolve_project_path(config_root)
        self.artifacts_root = resolve_project_path(artifacts_root)

    def list_entries(self) -> list[FactorCatalogEntry]:
        entries = []

        if not self.config_root.exists():
            return entries

        for path in sorted(self.config_root.glob("*.yaml")):
            config = load_factor_config(str(path))
            factor_id = config["factor_id"]
            entries.append(
                FactorCatalogEntry(
                    factor_id=factor_id,
                    implementation=config.get("implementation", ""),
                    version=config.get("version"),
                    status=config.get("status", "draft"),
                    config_path=path,
                    metadata=config.get("metadata", {}),
                    has_report=self.has_successful_report(factor_id),
                )
            )

        return entries

    def get_entry(
        self,
        factor_id: str,
    ) -> FactorCatalogEntry:
        for entry in self.list_entries():
            if entry.factor_id == factor_id:
                return entry

        raise KeyError(f"Factor '{factor_id}' does not exist in catalog")

    def has_successful_report(
        self,
        factor_id: str,
    ) -> bool:
        factor_root = self.artifacts_root / factor_id

        if not factor_root.exists():
            return False

        for manifest_path in factor_root.glob("*/run_manifest.json"):
            try:
                manifest = yaml.safe_load(
                    manifest_path.read_text(encoding="utf-8")
                )
            except Exception:
                continue

            if isinstance(manifest, dict) and manifest.get("status") == "success":
                return True

        return False

    def set_status(
        self,
        factor_id: str,
        status: str,
        force: bool = False,
    ) -> FactorCatalogEntry:
        if status not in VALID_FACTOR_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(VALID_FACTOR_STATUSES)}"
            )

        entry = self.get_entry(factor_id)

        if status == "approved" and not force and not entry.has_report:
            raise ValueError(
                f"Factor '{factor_id}' cannot be approved without a successful "
                "evaluation report. Use --force to override explicitly."
            )

        config = load_factor_config(str(entry.config_path))
        config["status"] = status
        entry.config_path.write_text(
            yaml.safe_dump(
                config,
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        return self.get_entry(factor_id)

    def mark_tested_if_draft(
        self,
        factor_id: str,
    ) -> FactorCatalogEntry:
        entry = self.get_entry(factor_id)

        if entry.status == "draft":
            return self.set_status(factor_id, "tested", force=True)

        return entry
