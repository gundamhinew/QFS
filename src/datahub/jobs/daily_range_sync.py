from __future__ import annotations

from src.datahub.jobs.backfill_daily import run_daily_range_job


def run_daily_range_sync(
    start_date: str,
    end_date: str,
    token_override: str | None = None
) -> None:
    # 用于手动同步任意日期区间的日线行情，不表达“只补历史”的语义。
    run_daily_range_job(
        start_date=start_date,
        end_date=end_date,
        token_override=token_override,
        job_name="sync_daily_range"
    )
