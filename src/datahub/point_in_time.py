from __future__ import annotations

from typing import Any

import pandas as pd


FINANCIAL_KEY_COLUMNS = ["ts_code", "ann_date", "end_date"]
UNIVERSE_KEY_COLUMNS = ["trade_date", "ts_code"]


def align_fina_indicator_to_universe(
    financial_df: pd.DataFrame,
    universe_df: pd.DataFrame,
    fields: list[str],
) -> pd.DataFrame:
    """Align reported financial indicators to a daily stock universe.

    ``trade_date`` is the date whose close produces the signal, ``ann_date``
    is the official announcement date, and ``end_date`` is the financial
    reporting-period end. A record is visible if and only if
    ``ann_date < trade_date``; an announcement made on the signal date is not
    usable until the next actual universe trading date.

    For each stock and trade date, selection first takes the greatest visible
    ``end_date`` and then, within that reporting period, the greatest
    ``ann_date``. Consequently, a revision becomes effective only after its
    announcement date, while a delayed revision to an older reporting period
    cannot replace a newer published period. Every universe row is preserved.
    """

    _validate_fields(fields)
    _validate_required_columns(
        financial_df,
        FINANCIAL_KEY_COLUMNS,
        "financial_df",
    )
    _validate_required_columns(
        universe_df,
        UNIVERSE_KEY_COLUMNS,
        "universe_df",
    )

    missing_fields = [field for field in fields if field not in financial_df.columns]
    if missing_fields:
        raise ValueError(f"financial_df is missing requested fields: {missing_fields}")

    financial = financial_df.copy(deep=True)
    universe = universe_df.copy(deep=True)
    financial["ann_date"] = _convert_date_column(
        financial["ann_date"],
        "financial_df.ann_date",
    )
    financial["end_date"] = _convert_date_column(
        financial["end_date"],
        "financial_df.end_date",
    )
    universe["trade_date"] = _convert_date_column(
        universe["trade_date"],
        "universe_df.trade_date",
    )

    _raise_on_duplicate_keys(
        financial,
        ["ts_code", "end_date", "ann_date"],
        "financial_df",
    )
    _raise_on_duplicate_keys(
        universe,
        ["trade_date", "ts_code"],
        "universe_df",
    )

    output_columns = [
        "trade_date",
        "ts_code",
        "source_ann_date",
        "source_end_date",
        *fields,
    ]
    rows: list[dict[str, Any]] = []
    financial_by_code = {
        ts_code: group.sort_values(["ann_date", "end_date"])
        for ts_code, group in financial.groupby("ts_code", sort=False)
    }

    for ts_code, stock_universe in universe.groupby("ts_code", sort=False):
        stock_universe = stock_universe.sort_values("trade_date")
        stock_financial = financial_by_code.get(ts_code)
        financial_records = (
            stock_financial.to_dict("records")
            if stock_financial is not None
            else []
        )
        record_index = 0
        selected: dict[str, Any] | None = None

        for trade_date in stock_universe["trade_date"]:
            while (
                record_index < len(financial_records)
                and financial_records[record_index]["ann_date"] < trade_date
            ):
                candidate = financial_records[record_index]
                if selected is None or (
                    candidate["end_date"],
                    candidate["ann_date"],
                ) > (
                    selected["end_date"],
                    selected["ann_date"],
                ):
                    selected = candidate
                record_index += 1

            row: dict[str, Any] = {
                "trade_date": trade_date,
                "ts_code": ts_code,
                "source_ann_date": pd.NaT,
                "source_end_date": pd.NaT,
            }
            if selected is None:
                row.update({field: pd.NA for field in fields})
            else:
                row["source_ann_date"] = selected["ann_date"]
                row["source_end_date"] = selected["end_date"]
                row.update({field: selected[field] for field in fields})
            rows.append(row)

    result = pd.DataFrame(rows, columns=output_columns)
    if result.empty:
        result["trade_date"] = pd.to_datetime(result["trade_date"])
        result["source_ann_date"] = pd.to_datetime(result["source_ann_date"])
        result["source_end_date"] = pd.to_datetime(result["source_end_date"])

    result = result.sort_values(["trade_date", "ts_code"]).reset_index(drop=True)
    if len(result) != len(universe):
        raise RuntimeError("Point-in-time alignment changed the universe row count")
    if result.duplicated(["trade_date", "ts_code"]).any():
        raise RuntimeError("Point-in-time alignment produced duplicate universe keys")

    matched = result["source_ann_date"].notna()
    if not (
        result.loc[matched, "source_ann_date"]
        < result.loc[matched, "trade_date"]
    ).all():
        raise RuntimeError("Point-in-time alignment used future financial data")

    return result


def _validate_fields(fields: list[str]) -> None:
    if (
        not isinstance(fields, list)
        or not fields
        or any(not isinstance(field, str) or not field for field in fields)
    ):
        raise ValueError("fields must be a non-empty list of strings")
    if len(fields) != len(set(fields)):
        raise ValueError("fields must not contain duplicates")


def _validate_required_columns(
    frame: pd.DataFrame,
    required: list[str],
    frame_name: str,
) -> None:
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"{frame_name} is missing required columns: {missing}")


def _convert_date_column(series: pd.Series, name: str) -> pd.Series:
    try:
        converted = pd.to_datetime(series, errors="raise", format="mixed")
    except Exception as exc:
        raise ValueError(f"{name} contains values that cannot be converted to datetime") from exc
    if converted.isna().any():
        raise ValueError(f"{name} contains values that cannot be converted to datetime")
    return converted


def _raise_on_duplicate_keys(
    frame: pd.DataFrame,
    keys: list[str],
    frame_name: str,
) -> None:
    if frame.duplicated(keys, keep=False).any():
        raise ValueError(f"{frame_name} contains duplicate keys for {keys}")


__all__ = ["align_fina_indicator_to_universe"]
