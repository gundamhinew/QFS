from __future__ import annotations

import time
import tushare as ts


class TushareClient:
    def __init__(self, token: str, sleep_seconds: float = 0.3):
        ts.set_token(token)
        self.pro = ts.pro_api()
        self.sleep_seconds = sleep_seconds

    def _sleep(self):
        time.sleep(self.sleep_seconds)

    def stock_basic(self, fields: str):
        df = self.pro.stock_basic(exchange="", list_status="L,D,P", fields=fields)
        self._sleep()
        return df

    def trade_cal(self, exchange: str, start_date: str, end_date: str, fields: str):
        df = self.pro.trade_cal(exchange=exchange, start_date=start_date, end_date=end_date, fields=fields)
        self._sleep()
        return df

    def daily(self, trade_date: str, fields: str):
        df = self.pro.daily(trade_date=trade_date, fields=fields)
        self._sleep()
        return df

    def adj_factor(self, trade_date: str, fields: str):
        df = self.pro.adj_factor(trade_date=trade_date, fields=fields)
        self._sleep()
        return df

    def daily_basic(self, trade_date: str, fields: str):
        df = self.pro.daily_basic(trade_date=trade_date, fields=fields)
        self._sleep()
        return df

    def fina_indicator(
        self,
        ts_code: str,
        fields: str,
        start_date: str | None = None,
        end_date: str | None = None
    ):
        params = {"ts_code": ts_code, "fields": fields}
        if start_date is not None:
            params["start_date"] = start_date
        if end_date is not None:
            params["end_date"] = end_date
        df = self.pro.fina_indicator(**params)
        self._sleep()
        return df
