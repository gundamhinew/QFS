from __future__ import annotations

import math

import pandas as pd


def _is_positive_number(value: float | int | None) -> bool:
    """
    判断输入是否为有效正数。
    """

    if value is None:
        return False

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return False

    return not math.isnan(numeric_value) and numeric_value > 0


def round_buy_shares(
    raw_shares: float,
    lot_size: int = 100
) -> int:
    """
    按 A 股一手规则向下取整买入股数。
    """

    if lot_size <= 0 or not _is_positive_number(raw_shares):
        return 0

    rounded = int(float(raw_shares) // lot_size * lot_size)

    if rounded < lot_size:
        return 0

    return int(rounded)


def round_sell_shares(
    raw_shares_to_sell: float,
    current_shares: int,
    lot_size: int = 100,
    allow_full_exit: bool = True
) -> int:
    """
    按 A 股一手规则向下取整卖出股数，清仓时允许卖出零股。
    """

    if (
        lot_size <= 0
        or not _is_positive_number(raw_shares_to_sell)
        or not _is_positive_number(current_shares)
    ):
        return 0

    current_shares_int = int(current_shares)
    raw_sell = min(float(raw_shares_to_sell), current_shares_int)

    if allow_full_exit and raw_sell >= current_shares_int:
        return int(current_shares_int)

    rounded = int(raw_sell // lot_size * lot_size)

    if rounded < lot_size:
        return 0

    return int(rounded)


def is_valid_buy_shares(
    shares: int,
    lot_size: int = 100
) -> bool:
    """
    判断买入股数是否满足一手及整数手要求。
    """

    if lot_size <= 0:
        return False

    try:
        shares_int = int(shares)
    except (TypeError, ValueError):
        return False

    if pd.isna(shares):
        return False

    return shares_int >= lot_size and shares_int % lot_size == 0
