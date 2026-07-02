from __future__ import annotations

import pandas as pd

from src.datahub.utils import (
    load_datahub_config,
    now_str,
    resolve_tushare_token,
    validate_yyyymmdd,
)
from src.datahub.client import TushareClient
from src.datahub.storage import ParquetStore
from src.datahub.meta_db import MetaDB
from src.datahub.downloaders.daily_price import fetch_daily_price_by_trade_date
from src.datahub.downloaders.adj_factor import fetch_adj_factor_by_trade_date
from src.datahub.downloaders.daily_basic import fetch_daily_basic_by_trade_date


def _get_open_trade_dates(
    raw_root: str,
    start_date: str,
    end_date: str | None = None
) -> list[str]:
    cal_path = f"{raw_root}/trade_calendar/trade_calendar.parquet"
    cal = pd.read_parquet(cal_path)
    cal["cal_date"] = cal["cal_date"].astype(str)
    mask = (cal["is_open"] == 1) & (cal["cal_date"] >= start_date)
    if end_date is not None:
        mask = mask & (cal["cal_date"] <= end_date)
    return cal.loc[mask, "cal_date"].sort_values().tolist()


def run_daily_updates(
    token_override: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None
):
    settings = load_datahub_config()
    if start_date is not None:
        start_date = validate_yyyymmdd(start_date, "start")
    if end_date is not None:
        end_date = validate_yyyymmdd(end_date, "end")
    if start_date and end_date and start_date > end_date:
        raise ValueError(f"start must be <= end, got {start_date} > {end_date}")

    client = TushareClient(
        token=resolve_tushare_token(settings, token_override),
        sleep_seconds=settings["tushare"]["sleep_seconds"]
    )
    store = ParquetStore(settings["paths"]["raw_root"])
    meta = MetaDB(settings["paths"]["meta_db"])

    jobs = [
        ("update_daily_price", "daily_price", fetch_daily_price_by_trade_date),
        ("update_adj_factor", "adj_factor", fetch_adj_factor_by_trade_date),
        ("update_daily_basic", "daily_basic", fetch_daily_basic_by_trade_date),
    ]

    for job_name, table_name, fetcher in jobs:
        last_date = meta.get_last_trade_date(job_name)

        if start_date is not None:
            job_start_date = start_date
        elif last_date is None:
            job_start_date = settings["daily"]["default_start"]
        else:
            job_start_date = (
                pd.to_datetime(last_date) + pd.Timedelta(days=1)
            ).strftime("%Y%m%d")

        trade_dates = _get_open_trade_dates(
            settings["paths"]["raw_root"],
            job_start_date,
            end_date
        )

        if not trade_dates:
            continue

        total_rows = 0
        latest_success_date = last_date

        try:
            meta.upsert_job_status(
                job_name=job_name,
                table_name=table_name,
                last_trade_date=last_date,
                status="running",
                last_run_time=now_str(),
                message="job started"
            )

            for trade_date in trade_dates:
                df = fetcher(client, trade_date)

                if df.empty:
                    latest_success_date = trade_date

                    meta.upsert_job_status(
                        job_name=job_name,
                        table_name=table_name,
                        last_trade_date=trade_date,
                        status="running",
                        last_run_time=now_str(),
                        message=f"running, empty date, rows={total_rows}"
                    )
                    continue

                if "trade_date" in df.columns:
                    df["trade_date"] = pd.to_datetime(
                        df["trade_date"],
                        format="%Y%m%d",
                        errors="coerce"
                    )

                store.write_month_partition(
                    df=df,
                    table_name=table_name,
                    date_col="trade_date",
                    subset_keys=["ts_code", "trade_date"],
                    sort_keys=["trade_date", "ts_code"]
                )

                total_rows += len(df)
                latest_success_date = trade_date

                # 关键：每成功处理一个交易日，就实时记录断点
                meta.upsert_job_status(
                    job_name=job_name,
                    table_name=table_name,
                    last_trade_date=trade_date,
                    status="running",
                    last_run_time=now_str(),
                    message=f"running, rows={total_rows}"
                )

            # 整个任务完整跑完后，再标记 success
            meta.upsert_job_status(
                job_name=job_name,
                table_name=table_name,
                last_trade_date=latest_success_date,
                status="success",
                last_run_time=now_str(),
                message=f"rows={total_rows}"
            )

            meta.insert_task_log(
                job_name=job_name,
                table_name=table_name,
                run_time=now_str(),
                status="success",
                rows_written=total_rows,
                start_date=trade_dates[0],
                end_date=trade_dates[-1]
            )

        except Exception as e:
            meta.upsert_job_status(
                job_name=job_name,
                table_name=table_name,
                last_trade_date=latest_success_date,
                status="failed",
                last_run_time=now_str(),
                message=str(e)
            )

            meta.insert_task_log(
                job_name=job_name,
                table_name=table_name,
                run_time=now_str(),
                status="failed",
                rows_written=total_rows,
                start_date=trade_dates[0] if trade_dates else None,
                end_date=latest_success_date,
                error_message=str(e)
            )
