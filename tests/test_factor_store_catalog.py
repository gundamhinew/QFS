from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.factors.catalog import FactorCatalog
from src.core.artifact_store import write_json
from src.factors.store import FactorStore, calculate_config_hash


def _config(status: str = "draft") -> dict:
    return {
        "schema_version": 2,
        "factor_id": "unit_factor",
        "implementation": "momentum",
        "version": 1,
        "status": status,
        "metadata": {"name": "Unit Factor"},
        "data": {"raw_root": "data/raw"},
        "period": {"start": "2020-01-01", "end": "2020-01-03"},
        "universe": {},
        "params": {"lookback": 1},
        "preprocess": {"direction": "positive"},
        "evaluation": {},
        "storage": {},
    }


def _raw_factor() -> pd.DataFrame:
    return pd.DataFrame({
        "trade_date": pd.to_datetime(["2020-01-01", "2020-01-02"]),
        "ts_code": ["000001.SZ", "000001.SZ"],
        "factor_id": ["unit_factor", "unit_factor"],
        "factor_value": [0.1, 0.2],
    })


def _processed_factor() -> pd.DataFrame:
    return pd.DataFrame({
        "trade_date": pd.to_datetime(["2020-01-01", "2020-01-02"]),
        "ts_code": ["000001.SZ", "000001.SZ"],
        "factor_id": ["unit_factor", "unit_factor"],
        "raw_value": [0.1, 0.2],
        "factor_score": [0.0, 1.0],
    })


def test_factor_store_hash_changes_with_params():
    config_a = _config()
    config_b = _config()
    config_b["params"] = {"lookback": 5}

    assert calculate_config_hash(config_a) != calculate_config_hash(config_b)


def test_factor_store_save_and_cache_hit(tmp_path):
    store = FactorStore(root=tmp_path)
    config = _config()

    assert not store.has_cache(config)
    saved = store.save(config, _raw_factor(), _processed_factor())

    assert store.has_cache(config)
    loaded = store.load(config)
    assert loaded["config_hash"] == saved["config_hash"]
    assert loaded["raw_factor"].shape[0] == 2
    assert loaded["manifest"]["row_count"] == 2


def test_factor_store_refresh_rebuild_can_overwrite_exact_cache(tmp_path):
    store = FactorStore(root=tmp_path)
    config = _config()
    store.save(config, _raw_factor(), _processed_factor())
    raw = _raw_factor()
    raw.loc[0, "factor_value"] = 9.9

    store.save(config, raw, _processed_factor())
    loaded = store.load(config)

    assert loaded["raw_factor"].loc[0, "factor_value"] == pytest.approx(9.9)


def _write_factor_config(path: Path, config: dict) -> None:
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def test_factor_catalog_list_show_and_missing(tmp_path):
    config_root = tmp_path / "configs"
    artifacts_root = tmp_path / "artifacts"
    _write_factor_config(config_root / "unit_factor.yaml", _config())
    catalog = FactorCatalog(config_root=config_root, artifacts_root=artifacts_root)

    entries = catalog.list_entries()
    assert len(entries) == 1
    assert catalog.get_entry("unit_factor").status == "draft"

    with pytest.raises(KeyError):
        catalog.get_entry("missing")


def test_factor_catalog_rejects_approve_without_report(tmp_path):
    config_root = tmp_path / "configs"
    artifacts_root = tmp_path / "artifacts"
    _write_factor_config(config_root / "unit_factor.yaml", _config())
    catalog = FactorCatalog(config_root=config_root, artifacts_root=artifacts_root)

    with pytest.raises(ValueError, match="cannot be approved"):
        catalog.set_status("unit_factor", "approved")


def test_factor_catalog_state_transitions_with_report_and_force(tmp_path):
    config_root = tmp_path / "configs"
    artifacts_root = tmp_path / "artifacts"
    _write_factor_config(config_root / "unit_factor.yaml", _config())
    report_dir = artifacts_root / "unit_factor" / "run_1"
    write_json(report_dir / "run_manifest.json", {"status": "success"})

    catalog = FactorCatalog(config_root=config_root, artifacts_root=artifacts_root)
    tested = catalog.mark_tested_if_draft("unit_factor")
    assert tested.status == "tested"

    approved = catalog.set_status("unit_factor", "approved")
    assert approved.status == "approved"

    deprecated = catalog.set_status("unit_factor", "deprecated", force=True)
    assert deprecated.status == "deprecated"
