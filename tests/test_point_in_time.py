from __future__ import annotations

import pandas as pd
import pytest

from src.datahub.point_in_time import align_fina_indicator_to_universe


def _financial_data():
    return pd.DataFrame([
        {
            "ts_code": "000001.SZ",
            "ann_date": "2024-04-02",
            "end_date": "2023-12-31",
            "roe": 10.0,
        },
        {
            "ts_code": "000001.SZ",
            "ann_date": "2024-04-06",
            "end_date": "2023-12-31",
            "roe": 11.0,
        },
        {
            "ts_code": "000001.SZ",
            "ann_date": "2024-05-01",
            "end_date": "2024-03-31",
            "roe": 20.0,
        },
        {
            "ts_code": "000001.SZ",
            "ann_date": "2024-05-04",
            "end_date": "2023-12-31",
            "roe": 12.0,
        },
        {
            "ts_code": "000001.SZ",
            "ann_date": "2024-05-04",
            "end_date": "2024-03-31",
            "roe": 21.0,
        },
        {
            "ts_code": "000002.SZ",
            "ann_date": "2024-04-01",
            "end_date": "2023-12-31",
            "roe": 30.0,
        },
    ])


def _universe_data():
    dates = [
        "2024-04-01",
        "2024-04-02",
        "2024-04-03",
        "2024-04-08",
        "2024-05-01",
        "2024-05-02",
        "2024-05-04",
        "2024-05-06",
    ]
    return pd.DataFrame([
        {"trade_date": trade_date, "ts_code": ts_code}
        for trade_date in reversed(dates)
        for ts_code in ["000002.SZ", "000001.SZ"]
    ])


def test_point_in_time_alignment_obeys_visibility_and_selection_rules():
    financial = _financial_data()
    universe = _universe_data()

    result = align_fina_indicator_to_universe(financial, universe, ["roe"])
    stock_a = result[result["ts_code"] == "000001.SZ"].set_index("trade_date")
    stock_b = result[result["ts_code"] == "000002.SZ"].set_index("trade_date")

    assert pd.isna(stock_a.loc["2024-04-01", "roe"])
    assert pd.isna(stock_a.loc["2024-04-02", "roe"])
    assert stock_a.loc["2024-04-03", "roe"] == 10.0
    assert stock_a.loc["2024-04-08", "roe"] == 11.0
    assert stock_a.loc["2024-05-01", "roe"] == 11.0
    assert stock_a.loc["2024-05-02", "roe"] == 20.0
    assert stock_a.loc["2024-05-04", "roe"] == 20.0
    assert stock_a.loc["2024-05-06", "roe"] == 21.0
    assert stock_a.loc["2024-05-06", "source_end_date"] == pd.Timestamp("2024-03-31")
    assert stock_a.loc["2024-05-06", "source_ann_date"] == pd.Timestamp("2024-05-04")

    assert pd.isna(stock_b.loc["2024-04-01", "roe"])
    assert stock_b.loc["2024-04-02", "roe"] == 30.0
    assert stock_b.loc["2024-05-06", "roe"] == 30.0

    assert len(result) == len(universe)
    assert not result.duplicated(["trade_date", "ts_code"]).any()
    matched = result["source_ann_date"].notna()
    assert (
        result.loc[matched, "source_ann_date"]
        < result.loc[matched, "trade_date"]
    ).all()


def test_point_in_time_alignment_does_not_modify_inputs():
    financial = _financial_data()
    universe = _universe_data()
    financial_before = financial.copy(deep=True)
    universe_before = universe.copy(deep=True)

    align_fina_indicator_to_universe(financial, universe, ["roe"])

    pd.testing.assert_frame_equal(financial, financial_before)
    pd.testing.assert_frame_equal(universe, universe_before)


def test_point_in_time_output_dates_sorting_and_unique_keys():
    result = align_fina_indicator_to_universe(
        _financial_data(),
        _universe_data(),
        ["roe"],
    )

    assert pd.api.types.is_datetime64_any_dtype(result["trade_date"])
    assert pd.api.types.is_datetime64_any_dtype(result["source_ann_date"])
    assert pd.api.types.is_datetime64_any_dtype(result["source_end_date"])
    assert result.equals(
        result.sort_values(["trade_date", "ts_code"]).reset_index(drop=True)
    )
    assert result[["trade_date", "ts_code"]].value_counts().max() == 1


@pytest.mark.parametrize(
    ("financial", "universe", "match"),
    [
        (
            pd.DataFrame(columns=["ann_date", "end_date", "roe"]),
            pd.DataFrame(columns=["trade_date", "ts_code"]),
            "financial_df.*ts_code",
        ),
        (
            pd.DataFrame(columns=["ts_code", "end_date", "roe"]),
            pd.DataFrame(columns=["trade_date", "ts_code"]),
            "financial_df.*ann_date",
        ),
        (
            pd.DataFrame(columns=["ts_code", "ann_date", "roe"]),
            pd.DataFrame(columns=["trade_date", "ts_code"]),
            "financial_df.*end_date",
        ),
        (
            pd.DataFrame(columns=["ts_code", "ann_date", "end_date", "roe"]),
            pd.DataFrame(columns=["ts_code"]),
            "universe_df.*trade_date",
        ),
    ],
)
def test_point_in_time_rejects_missing_required_columns(
    financial,
    universe,
    match,
):
    with pytest.raises(ValueError, match=match):
        align_fina_indicator_to_universe(financial, universe, ["roe"])


@pytest.mark.parametrize("fields", [None, [], "roe", [""], ["roe", "roe"]])
def test_point_in_time_rejects_invalid_fields(fields):
    with pytest.raises(ValueError, match="fields"):
        align_fina_indicator_to_universe(
            _financial_data(),
            _universe_data(),
            fields,
        )


def test_point_in_time_reports_missing_requested_fields():
    with pytest.raises(ValueError, match="gross_margin"):
        align_fina_indicator_to_universe(
            _financial_data(),
            _universe_data(),
            ["gross_margin"],
        )


def test_point_in_time_rejects_duplicate_financial_keys():
    financial = pd.concat(
        [_financial_data(), _financial_data().iloc[[0]]],
        ignore_index=True,
    )

    with pytest.raises(ValueError, match="financial_df.*duplicate"):
        align_fina_indicator_to_universe(financial, _universe_data(), ["roe"])


def test_point_in_time_rejects_duplicate_universe_keys():
    universe = pd.concat(
        [_universe_data(), _universe_data().iloc[[0]]],
        ignore_index=True,
    )

    with pytest.raises(ValueError, match="universe_df.*duplicate"):
        align_fina_indicator_to_universe(_financial_data(), universe, ["roe"])


@pytest.mark.parametrize(
    ("financial_column", "bad_value", "match"),
    [
        ("ann_date", "not-a-date", "financial_df.ann_date"),
        ("end_date", "not-a-date", "financial_df.end_date"),
    ],
)
def test_point_in_time_rejects_invalid_financial_dates(
    financial_column,
    bad_value,
    match,
):
    financial = _financial_data()
    financial.loc[0, financial_column] = bad_value

    with pytest.raises(ValueError, match=match):
        align_fina_indicator_to_universe(financial, _universe_data(), ["roe"])


def test_point_in_time_rejects_invalid_trade_dates():
    universe = _universe_data()
    universe.loc[0, "trade_date"] = "not-a-date"

    with pytest.raises(ValueError, match="universe_df.trade_date"):
        align_fina_indicator_to_universe(_financial_data(), universe, ["roe"])
