from __future__ import annotations

import pandas as pd


def exclude_bj_stocks(df: pd.DataFrame) -> pd.DataFrame:
    """
    剔除北交所股票。

    兼容 ts_code、exchange、market 三类常见字段。
    """

    if df.empty:
        return df

    result = df.copy()
    mask = pd.Series(False, index=result.index)

    if "ts_code" in result.columns:
        mask = mask | result["ts_code"].astype(str).str.endswith(".BJ")

    if "exchange" in result.columns:
        mask = mask | result["exchange"].astype(str).str.upper().eq("BSE")

    if "market" in result.columns:
        mask = mask | result["market"].astype(str).str.contains("北交", na=False)

    return result.loc[~mask].copy()


def exclude_st_stocks(df: pd.DataFrame) -> pd.DataFrame:
    """
    剔除 ST / *ST 股票。

    第一版使用股票名称识别，后续可接入更完整的风险警示历史表。
    """

    if df.empty or "name" not in df.columns:
        return df

    result = df.copy()
    name = result["name"].astype(str).str.upper()
    mask = name.str.contains("ST", na=False)

    return result.loc[~mask].copy()


def exclude_new_stocks(
    df: pd.DataFrame,
    min_list_days: int = 120
) -> pd.DataFrame:
    """
    剔除上市不足指定天数的新股。
    """

    if df.empty or "list_date" not in df.columns:
        return df

    result = df.copy()
    result["list_date"] = pd.to_datetime(
        result["list_date"],
        errors="coerce"
    )

    list_days = (
        result["trade_date"] - result["list_date"]
    ).dt.days

    return result.loc[list_days >= min_list_days].copy()


def exclude_low_price(
    df: pd.DataFrame,
    min_close: float = 2.0
) -> pd.DataFrame:
    """
    剔除极低价股。
    """

    if df.empty or "close" not in df.columns:
        return df

    return df.loc[df["close"] >= min_close].copy()


def exclude_low_amount(
    df: pd.DataFrame,
    min_amount: float = 30_000_000
) -> pd.DataFrame:
    """
    剔除低成交额股票。

    如果上游保留 tushare 原始 amount（单位通常为千元），UniverseBuilder
    会先生成 amount_yuan，再优先用 amount_yuan 做过滤。
    """

    if df.empty:
        return df

    amount_col = "amount_yuan" if "amount_yuan" in df.columns else "amount"

    if amount_col not in df.columns:
        return df

    return df.loc[df[amount_col] >= min_amount].copy()


def exclude_suspended(df: pd.DataFrame) -> pd.DataFrame:
    """
    剔除停牌或疑似停牌股票。

    第一版规则：当天无行情不会出现在行情表；若 vol 或 amount 为 0，也视为不可交易。
    """

    if df.empty:
        return df

    result = df.copy()

    if "vol" in result.columns:
        result = result.loc[result["vol"].fillna(0) > 0].copy()

    if "amount" in result.columns:
        result = result.loc[result["amount"].fillna(0) > 0].copy()

    return result
