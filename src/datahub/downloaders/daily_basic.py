from __future__ import annotations

from src.datahub.schemas import DAILY_BASIC_FIELDS


def fetch_daily_basic_by_trade_date(client, trade_date: str):
    fields = ",".join(DAILY_BASIC_FIELDS)
    df = client.daily_basic(trade_date=trade_date, fields=fields)
    return df