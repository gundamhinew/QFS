from __future__ import annotations

from src.datahub.schemas import STOCK_BASIC_FIELDS


def fetch_stock_basic(client):
    fields = ",".join(STOCK_BASIC_FIELDS)
    df = client.stock_basic(fields=fields)
    return df