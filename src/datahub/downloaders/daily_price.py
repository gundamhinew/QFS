from __future__ import annotations

from src.datahub.schemas import DAILY_PRICE_FIELDS


def fetch_daily_price_by_trade_date(client, trade_date: str):
    fields = ",".join(DAILY_PRICE_FIELDS)
    df = client.daily(trade_date=trade_date, fields=fields)
    return df