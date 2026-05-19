from __future__ import annotations

import pandas as pd


def _get_limit_threshold(row: pd.Series) -> float:
    """
    获取个股涨跌停阈值。

    第一版尽量根据已有字段识别 ST、科创板和创业板。
    如果行情行缺少 name、market 等辅助字段，则默认使用普通股票 10% 规则。
    """

    ts_code = str(row.get("ts_code", ""))
    name = str(row.get("name", ""))
    market = str(row.get("market", ""))

    if "ST" in name.upper():
        return 4.8

    if ts_code.startswith("300") or ts_code.startswith("301"):
        return 19.8

    if ts_code.startswith("688") or ts_code.startswith("689"):
        return 19.8

    if "创业板" in market or "科创板" in market:
        return 19.8

    # TODO: 后续可结合上市日期、注册制规则变更日期等信息进一步精细化。
    return 9.8


def is_limit_up(row: pd.Series) -> bool:
    """
    判断是否涨停。

    pct_chg 缺失时不做限制，避免因为数据不完整误伤可交易股票。
    """

    pct_chg = row.get("pct_chg")

    if pd.isna(pct_chg):
        return False

    return float(pct_chg) >= _get_limit_threshold(row)


def is_limit_down(row: pd.Series) -> bool:
    """
    判断是否跌停。

    pct_chg 缺失时不做限制，避免因为数据不完整误伤可交易股票。
    """

    pct_chg = row.get("pct_chg")

    if pd.isna(pct_chg):
        return False

    return float(pct_chg) <= -_get_limit_threshold(row)


def can_buy(row: pd.Series) -> bool:
    """
    判断当日是否允许买入。

    简化规则：涨停买不到。
    """

    return not is_limit_up(row)


def can_sell(row: pd.Series) -> bool:
    """
    判断当日是否允许卖出。

    简化规则：跌停卖不出。
    """

    return not is_limit_down(row)
