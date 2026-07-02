from __future__ import annotations

from src.datahub.schemas import FINA_INDICATOR_FIELDS


def fetch_fina_indicator_by_ts_code(
    client,
    ts_code: str,
    start_date: str | None = None,
    end_date: str | None = None
):
    fields = ",".join(FINA_INDICATOR_FIELDS)
    df = client.fina_indicator(
        ts_code=ts_code,
        fields=fields,
        start_date=start_date,
        end_date=end_date
    )
    return df
