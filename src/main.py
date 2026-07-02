from __future__ import annotations

import argparse

from src.datahub.jobs.backfill_daily import run_backfill_daily
from src.datahub.jobs.bootstrap import run_bootstrap
from src.datahub.jobs.daily_range_sync import run_daily_range_sync
from src.datahub.jobs.daily_update import run_daily_updates
from src.datahub.jobs.financial_update import run_financial_update


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "job",
        choices=[
            "bootstrap",
            "daily_update",
            "financial_update",
            "backfill_daily",
            "sync_daily_range"
        ]
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start", type=str, default=None)
    parser.add_argument("--end", type=str, default=None)
    parser.add_argument(
        "--token",
        "--tushare-token",
        dest="tushare_token",
        type=str,
        default=None,
        help="Runtime Tushare token override. It is not written to config files."
    )
    args = parser.parse_args()

    if args.job == "bootstrap":
        run_bootstrap(
            token_override=args.tushare_token,
            start_date=args.start,
            end_date=args.end
        )
    elif args.job == "daily_update":
        run_daily_updates(
            token_override=args.tushare_token,
            start_date=args.start,
            end_date=args.end
        )
    elif args.job == "financial_update":
        run_financial_update(
            limit=args.limit,
            token_override=args.tushare_token,
            start_date=args.start,
            end_date=args.end
        )
    elif args.job == "backfill_daily":
        if not args.start or not args.end:
            parser.error("backfill_daily requires --start YYYYMMDD and --end YYYYMMDD")
        run_backfill_daily(
            start_date=args.start,
            end_date=args.end,
            token_override=args.tushare_token
        )
    elif args.job == "sync_daily_range":
        if not args.start or not args.end:
            parser.error("sync_daily_range requires --start YYYYMMDD and --end YYYYMMDD")
        run_daily_range_sync(
            start_date=args.start,
            end_date=args.end,
            token_override=args.tushare_token
        )


if __name__ == "__main__":
    main()
