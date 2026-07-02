from __future__ import annotations

from src.datahub.utils import (
    load_datahub_config,
    now_str,
    resolve_tushare_token,
    today_yyyymmdd,
    validate_yyyymmdd,
)
from src.datahub.client import TushareClient
from src.datahub.storage import ParquetStore
from src.datahub.meta_db import MetaDB
from src.datahub.downloaders.stock_basic import fetch_stock_basic
from src.datahub.downloaders.trade_calendar import fetch_trade_calendar


def run_bootstrap(
    token_override: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None
):
    settings = load_datahub_config()
    start_date = validate_yyyymmdd(
        start_date or settings["calendar"]["default_start"],
        "start"
    )
    end_date = validate_yyyymmdd(end_date or today_yyyymmdd(), "end")
    if start_date > end_date:
        raise ValueError(f"start must be <= end, got {start_date} > {end_date}")

    client = TushareClient(
        token=resolve_tushare_token(settings, token_override),
        sleep_seconds=settings["tushare"]["sleep_seconds"]
    )
    store = ParquetStore(settings["paths"]["raw_root"])
    meta = MetaDB(settings["paths"]["meta_db"])

    # stock_basic
    stock_df = fetch_stock_basic(client)
    stock_df["is_active"] = stock_df["list_status"].eq("L").astype(int)
    stock_df["updated_at"] = now_str()

    store.write_single_file(
        stock_df,
        relative_path="stock_basic/stock_basic.parquet",
        subset_keys=["ts_code"],
        sort_keys=["ts_code"]
    )

    meta.replace_asset_universe(
        stock_df[[
            "ts_code", "symbol", "name", "exchange", "market",
            "list_status", "list_date", "delist_date", "is_active", "updated_at"
        ]]
    )

    meta.upsert_job_status(
        job_name="bootstrap_stock_basic",
        table_name="stock_basic",
        last_trade_date=None,
        status="success",
        last_run_time=now_str(),
        message=f"rows={len(stock_df)}"
    )

    meta.insert_task_log(
        job_name="bootstrap_stock_basic",
        table_name="stock_basic",
        run_time=now_str(),
        status="success",
        rows_written=len(stock_df)
    )

    # trade_calendar
    cal_df = fetch_trade_calendar(
        client,
        exchange=settings["calendar"]["exchange"],
        start_date=start_date,
        end_date=end_date
    )

    store.write_single_file(
        cal_df,
        relative_path="trade_calendar/trade_calendar.parquet",
        subset_keys=["exchange", "cal_date"],
        sort_keys=["exchange", "cal_date"]
    )

    last_open_date = None
    if not cal_df.empty:
        open_days = cal_df[cal_df["is_open"] == 1]
        if not open_days.empty:
            last_open_date = open_days["cal_date"].max()

    meta.upsert_job_status(
        job_name="bootstrap_trade_calendar",
        table_name="trade_calendar",
        last_trade_date=last_open_date,
        status="success",
        last_run_time=now_str(),
        message=f"rows={len(cal_df)}"
    )

    meta.insert_task_log(
        job_name="bootstrap_trade_calendar",
        table_name="trade_calendar",
        run_time=now_str(),
        status="success",
        rows_written=len(cal_df),
        start_date=start_date,
        end_date=end_date
    )
