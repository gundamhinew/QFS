from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.datahub.client import TushareClient
from src.datahub.downloaders.adj_factor import fetch_adj_factor_by_trade_date
from src.datahub.downloaders.daily_basic import fetch_daily_basic_by_trade_date
from src.datahub.downloaders.daily_price import fetch_daily_price_by_trade_date
from src.datahub.meta_db import MetaDB
from src.datahub.storage import ParquetStore
from src.datahub.utils import load_settings, now_str, resolve_tushare_token


DAILY_TABLE_GROUP = "daily_price,adj_factor,daily_basic"


def _validate_yyyymmdd(value: str, name: str) -> str:
    try:
        pd.to_datetime(value, format="%Y%m%d")
    except ValueError as exc:
        raise ValueError(f"{name} must be YYYYMMDD, got {value!r}") from exc
    return value


def _get_open_trade_dates(raw_root: str, start_date: str, end_date: str) -> list[str]:
    cal_path = Path(raw_root) / "trade_calendar" / "trade_calendar.parquet"
    if not cal_path.exists():
        raise FileNotFoundError(
            f"trade calendar not found: {cal_path}. Please run bootstrap first."
        )

    cal = pd.read_parquet(cal_path)
    cal["cal_date"] = cal["cal_date"].astype(str)

    mask = (
        (cal["is_open"] == 1)
        & (cal["cal_date"] >= start_date)
        & (cal["cal_date"] <= end_date)
    )
    return cal.loc[mask, "cal_date"].sort_values().tolist()


def _normalize_trade_date(df: pd.DataFrame) -> pd.DataFrame:
    if "trade_date" not in df.columns:
        return df

    work = df.copy()
    work["trade_date"] = pd.to_datetime(
        work["trade_date"],
        format="%Y%m%d",
        errors="coerce"
    )
    return work


def run_daily_range_job(
    start_date: str,
    end_date: str,
    token_override: str | None = None,
    job_name: str = "sync_daily_range"
) -> None:
    start_date = _validate_yyyymmdd(start_date, "start")
    end_date = _validate_yyyymmdd(end_date, "end")
    if start_date > end_date:
        raise ValueError(f"start must be <= end, got {start_date} > {end_date}")

    settings = load_settings()
    client = TushareClient(
        token=resolve_tushare_token(settings, token_override),
        sleep_seconds=settings["update"]["sleep_seconds"]
    )
    store = ParquetStore(settings["paths"]["raw_root"])
    meta = MetaDB(settings["paths"]["meta_db"])

    trade_dates = _get_open_trade_dates(
        settings["paths"]["raw_root"],
        start_date,
        end_date
    )

    if not trade_dates:
        meta.insert_task_log(
            job_name=job_name,
            table_name=DAILY_TABLE_GROUP,
            run_time=now_str(),
            status="skipped",
            rows_written=0,
            start_date=start_date,
            end_date=end_date,
            error_message="no open trade dates"
        )
        return

    jobs = [
        ("daily_price", fetch_daily_price_by_trade_date),
        ("adj_factor", fetch_adj_factor_by_trade_date),
        ("daily_basic", fetch_daily_basic_by_trade_date),
    ]

    total_rows = 0
    latest_success_date = None

    try:
        meta.upsert_job_status(
            job_name=job_name,
            table_name=DAILY_TABLE_GROUP,
            last_trade_date=None,
            status="running",
            last_run_time=now_str(),
            message=f"job started, range={trade_dates[0]}-{trade_dates[-1]}"
        )

        for trade_date in trade_dates:
            day_rows = 0

            for table_name, fetcher in jobs:
                df = fetcher(client, trade_date)

                if df.empty:
                    # 回填遇到空数据时跳过写入，但保留日志便于排查缺口。
                    meta.insert_task_log(
                        job_name=job_name,
                        table_name=table_name,
                        run_time=now_str(),
                        status="empty",
                        rows_written=0,
                        start_date=trade_date,
                        end_date=trade_date,
                        error_message="empty dataframe"
                    )
                    continue

                df = _normalize_trade_date(df)
                store.write_month_partition(
                    df=df,
                    table_name=table_name,
                    date_col="trade_date",
                    subset_keys=["ts_code", "trade_date"],
                    sort_keys=["trade_date", "ts_code"]
                )

                rows_written = len(df)
                day_rows += rows_written
                total_rows += rows_written

                meta.insert_task_log(
                    job_name=job_name,
                    table_name=table_name,
                    run_time=now_str(),
                    status="success",
                    rows_written=rows_written,
                    start_date=trade_date,
                    end_date=trade_date
                )

            latest_success_date = trade_date

            meta.upsert_job_status(
                job_name=job_name,
                table_name=DAILY_TABLE_GROUP,
                last_trade_date=trade_date,
                status="running",
                last_run_time=now_str(),
                message=f"running, day_rows={day_rows}, total_rows={total_rows}"
            )

        meta.upsert_job_status(
            job_name=job_name,
            table_name=DAILY_TABLE_GROUP,
            last_trade_date=latest_success_date,
            status="success",
            last_run_time=now_str(),
            message=f"rows={total_rows}"
        )

        meta.insert_task_log(
            job_name=job_name,
            table_name=DAILY_TABLE_GROUP,
            run_time=now_str(),
            status="success",
            rows_written=total_rows,
            start_date=trade_dates[0],
            end_date=trade_dates[-1]
        )

    except Exception as e:
        meta.upsert_job_status(
            job_name=job_name,
            table_name=DAILY_TABLE_GROUP,
            last_trade_date=latest_success_date,
            status="failed",
            last_run_time=now_str(),
            message=str(e)
        )

        meta.insert_task_log(
            job_name=job_name,
            table_name=DAILY_TABLE_GROUP,
            run_time=now_str(),
            status="failed",
            rows_written=total_rows,
            start_date=trade_dates[0] if trade_dates else start_date,
            end_date=latest_success_date,
            error_message=str(e)
        )
        raise


def run_backfill_daily(
    start_date: str,
    end_date: str,
    token_override: str | None = None
) -> None:
    run_daily_range_job(
        start_date=start_date,
        end_date=end_date,
        token_override=token_override,
        job_name="backfill_daily"
    )
