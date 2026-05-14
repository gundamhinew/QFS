from __future__ import annotations

from src.datahub.schemas import ADJ_FACTOR_FIELDS


def fetch_adj_factor_by_trade_date(client, trade_date: str):
    fields = ",".join(ADJ_FACTOR_FIELDS)
    df = client.adj_factor(trade_date=trade_date, fields=fields)
    return df