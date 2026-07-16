from __future__ import annotations

import pandas as pd
import pytest

from src.datahub.data_manager import DataManager


def _write_fina_file(raw_root, ts_code, rows):
    path = (
        raw_root
        / "financial"
        / "fina_indicator"
        / f"ts_code={ts_code}.parquet"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)


def test_get_fina_indicator_filters_ann_date_inclusively_and_sorts(tmp_path):
    _write_fina_file(tmp_path, "000002.SZ", [{
        "ts_code": "000002.SZ",
        "ann_date": "2024-04-02",
        "end_date": "2023-12-31",
        "roe": 20.0,
    }])
    _write_fina_file(tmp_path, "000001.SZ", [
        {
            "ts_code": "000001.SZ",
            "ann_date": "2024-04-03",
            "end_date": "2024-03-31",
            "roe": 12.0,
        },
        {
            "ts_code": "000001.SZ",
            "ann_date": "2024-04-01",
            "end_date": "2023-12-31",
            "roe": 10.0,
        },
    ])

    result = DataManager(str(tmp_path)).get_fina_indicator(
        start="2024-04-01",
        end=pd.Timestamp("2024-04-02"),
    )

    assert result[["ts_code", "ann_date"]].to_dict("records") == [
        {"ts_code": "000001.SZ", "ann_date": pd.Timestamp("2024-04-01")},
        {"ts_code": "000002.SZ", "ann_date": pd.Timestamp("2024-04-02")},
    ]
    assert pd.api.types.is_datetime64_any_dtype(result["ann_date"])
    assert pd.api.types.is_datetime64_any_dtype(result["end_date"])


def test_get_fina_indicator_ts_codes_and_field_selection(tmp_path):
    rows = [{
        "ts_code": "000001.SZ",
        "ann_date": "2024-04-01",
        "end_date": "2023-12-31",
        "roe": 10.0,
        "gross_margin": 30.0,
    }]
    _write_fina_file(tmp_path, "000001.SZ", rows)
    _write_fina_file(tmp_path, "000002.SZ", [{**rows[0], "ts_code": "000002.SZ"}])

    result = DataManager(str(tmp_path)).get_fina_indicator(
        ts_codes=["000002.SZ"],
        fields=["roe"],
    )

    assert list(result.columns) == ["ts_code", "ann_date", "end_date", "roe"]
    assert result["ts_code"].tolist() == ["000002.SZ"]


def test_get_fina_indicator_none_fields_returns_all_available_fields(tmp_path):
    _write_fina_file(tmp_path, "000001.SZ", [{
        "ts_code": "000001.SZ",
        "ann_date": "2024-04-01",
        "end_date": "2023-12-31",
        "roe": 10.0,
        "netprofit_yoy": 8.0,
    }])

    result = DataManager(str(tmp_path)).get_fina_indicator(fields=None)

    assert {"ts_code", "ann_date", "end_date", "roe", "netprofit_yoy"} == set(result.columns)


def test_get_fina_indicator_empty_sources_keep_expected_columns(tmp_path):
    manager = DataManager(str(tmp_path))

    assert list(manager.get_fina_indicator().columns) == [
        "ts_code", "ann_date", "end_date"
    ]
    assert list(manager.get_fina_indicator(ts_codes=[], fields=["roe"]).columns) == [
        "ts_code", "ann_date", "end_date", "roe"
    ]


@pytest.mark.parametrize(
    "fields",
    [[], "roe", [""], ["roe", "roe"]],
)
def test_get_fina_indicator_rejects_invalid_fields(tmp_path, fields):
    with pytest.raises(ValueError, match="fields"):
        DataManager(str(tmp_path)).get_fina_indicator(fields=fields)


def test_get_fina_indicator_reports_missing_requested_fields(tmp_path):
    _write_fina_file(tmp_path, "000001.SZ", [{
        "ts_code": "000001.SZ",
        "ann_date": "2024-04-01",
        "end_date": "2023-12-31",
        "roe": 10.0,
    }])

    with pytest.raises(ValueError, match="missing_metric"):
        DataManager(str(tmp_path)).get_fina_indicator(fields=["missing_metric"])


def test_get_fina_indicator_rejects_reversed_or_invalid_boundaries(tmp_path):
    manager = DataManager(str(tmp_path))

    with pytest.raises(ValueError, match="start must"):
        manager.get_fina_indicator(start="2024-04-02", end="2024-04-01")
    with pytest.raises(ValueError, match="start cannot"):
        manager.get_fina_indicator(start="not-a-date")


def test_get_fina_indicator_rejects_invalid_stored_dates(tmp_path):
    _write_fina_file(tmp_path, "000001.SZ", [{
        "ts_code": "000001.SZ",
        "ann_date": "invalid",
        "end_date": "2023-12-31",
        "roe": 10.0,
    }])

    with pytest.raises(ValueError, match="ann_date"):
        DataManager(str(tmp_path)).get_fina_indicator()


def test_get_fina_indicator_rejects_duplicate_financial_keys(tmp_path):
    row = {
        "ts_code": "000001.SZ",
        "ann_date": "2024-04-01",
        "end_date": "2023-12-31",
        "roe": 10.0,
    }
    _write_fina_file(tmp_path, "000001.SZ", [row, row])

    with pytest.raises(ValueError, match="duplicate keys"):
        DataManager(str(tmp_path)).get_fina_indicator()
