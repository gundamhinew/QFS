STOCK_BASIC_FIELDS = [
    "ts_code", "symbol", "name", "area", "industry", "fullname",
    "enname", "cnspell", "market", "exchange", "curr_type",
    "list_status", "list_date", "delist_date", "is_hs"
]

TRADE_CAL_FIELDS = [
    "exchange", "cal_date", "is_open", "pretrade_date"
]

DAILY_PRICE_FIELDS = [
    "ts_code", "trade_date", "open", "high", "low", "close",
    "pre_close", "change", "pct_chg", "vol", "amount"
]

ADJ_FACTOR_FIELDS = [
    "ts_code", "trade_date", "adj_factor"
]

DAILY_BASIC_FIELDS = [
    "ts_code", "trade_date", "close", "turnover_rate", "turnover_rate_f",
    "volume_ratio", "pe", "pe_ttm", "pb", "ps", "ps_ttm",
    "dv_ratio", "dv_ttm", "total_share", "float_share",
    "free_share", "total_mv", "circ_mv"
]

FINA_INDICATOR_FIELDS = [
    "ts_code", "ann_date", "end_date", "eps", "dt_eps", "grossprofit_margin",
    "current_ratio", "quick_ratio", "cash_ratio", "inv_turn", "ar_turn",
    "assets_turn", "ebit", "ebitda", "fcff", "fcfe", "netdebt",
    "working_capital", "ocfps", "netprofit_margin", "gross_margin",
    "roe", "roe_dt", "roa", "roic", "roe_yearly", "roa_yearly",
    "debt_to_assets", "assets_to_eqt", "ocf_to_debt", "turn_days",
    "q_opincome", "q_dtprofit", "q_eps", "q_roe", "q_dt_roe",
    "basic_eps_yoy", "dt_eps_yoy", "op_yoy", "ebt_yoy", "netprofit_yoy",
    "dt_netprofit_yoy", "ocf_yoy", "roe_yoy", "assets_yoy", "tr_yoy", "or_yoy"
]