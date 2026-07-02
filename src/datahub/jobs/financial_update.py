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
from src.datahub.downloaders.fina_indicator import fetch_fina_indicator_by_ts_code


def run_financial_update(
    limit: int | None = None,
    token_override: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None
):
    settings = load_datahub_config()
    start_date = start_date or settings["financial"]["default_start"]
    end_date = end_date or settings["financial"]["default_end"]
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

    ts_codes = meta.get_active_ts_codes()
    if limit:
        ts_codes = ts_codes[:limit]

    total_rows = 0
    last_ts_code = None

    try:
        meta.upsert_job_status(
            job_name="update_fina_indicator",
            table_name="financial/fina_indicator",
            last_trade_date=None,
            last_ts_code=None,
            status="running",
            last_run_time=now_str(),
            message=""
        )

        for ts_code in ts_codes:
            df = fetch_fina_indicator_by_ts_code(
                client,
                ts_code,
                start_date=start_date,
                end_date=end_date
            )
            if df.empty:
                last_ts_code = ts_code
                continue

            for col in ["ann_date", "end_date"]:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], format="%Y%m%d", errors="coerce")

            store.write_ts_code_partition(
                df=df,
                table_name="financial/fina_indicator",
                code_col="ts_code",
                subset_keys=["ts_code", "end_date", "ann_date"],
                sort_keys=["ts_code", "end_date", "ann_date"]
            )

            total_rows += len(df)
            last_ts_code = ts_code

        meta.upsert_job_status(
            job_name="update_fina_indicator",
            table_name="financial/fina_indicator",
            last_trade_date=None,
            last_ts_code=last_ts_code,
            status="success",
            last_run_time=now_str(),
            message=f"rows={total_rows}"
        )

        meta.insert_task_log(
            job_name="update_fina_indicator",
            table_name="financial/fina_indicator",
            run_time=now_str(),
            status="success",
            rows_written=total_rows,
            start_date=start_date,
            end_date=end_date
        )

    except Exception as e:
        meta.upsert_job_status(
            job_name="update_fina_indicator",
            table_name="financial/fina_indicator",
            last_trade_date=None,
            last_ts_code=last_ts_code,
            status="failed",
            last_run_time=now_str(),
            message=str(e)
        )
        meta.insert_task_log(
            job_name="update_fina_indicator",
            table_name="financial/fina_indicator",
            run_time=now_str(),
            status="failed",
            rows_written=total_rows,
            start_date=start_date,
            end_date=end_date,
            error_message=str(e)
        )
