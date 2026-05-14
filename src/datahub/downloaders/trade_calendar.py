from __future__ import annotations

from src.datahub.schemas import TRADE_CAL_FIELDS


def fetch_trade_calendar(client, exchange: str, start_date: str, end_date: str):
    fields = ",".join(TRADE_CAL_FIELDS)
    df = client.trade_cal(exchange=exchange, start_date=start_date, end_date=end_date, fields=fields)
    return df