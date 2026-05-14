from __future__ import annotations

import argparse

from src.datahub.jobs.bootstrap import run_bootstrap
from src.datahub.jobs.daily_update import run_daily_updates
from src.datahub.jobs.financial_update import run_financial_update


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("job", choices=["bootstrap", "daily_update", "financial_update"])
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    if args.job == "bootstrap":
        run_bootstrap()
    elif args.job == "daily_update":
        run_daily_updates()
    elif args.job == "financial_update":
        run_financial_update(limit=args.limit)


if __name__ == "__main__":
    main()