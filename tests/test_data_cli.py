from unittest.mock import Mock

import pytest

import src.cli.data as data_cli


@pytest.mark.parametrize(
    ("job", "handler_name", "extra_args", "expected_kwargs"),
    [
        (
            "bootstrap",
            "run_bootstrap",
            [],
            {"token_override": "token", "start_date": "20260101", "end_date": "20260131"},
        ),
        (
            "daily_update",
            "run_daily_updates",
            [],
            {"token_override": "token", "start_date": "20260101", "end_date": "20260131"},
        ),
        (
            "financial_update",
            "run_financial_update",
            ["--limit", "10"],
            {
                "limit": 10,
                "token_override": "token",
                "start_date": "20260101",
                "end_date": "20260131",
            },
        ),
        (
            "backfill_daily",
            "run_backfill_daily",
            [],
            {"start_date": "20260101", "end_date": "20260131", "token_override": "token"},
        ),
        (
            "sync_daily_range",
            "run_daily_range_sync",
            [],
            {"start_date": "20260101", "end_date": "20260131", "token_override": "token"},
        ),
    ],
)
def test_data_cli_dispatches_each_job(
    monkeypatch,
    job,
    handler_name,
    extra_args,
    expected_kwargs,
):
    handler = Mock()
    monkeypatch.setattr(data_cli, handler_name, handler)
    monkeypatch.setattr(
        "sys.argv",
        [
            "data.py",
            job,
            "--start",
            "20260101",
            "--end",
            "20260131",
            "--token",
            "token",
            *extra_args,
        ],
    )

    data_cli.main()

    handler.assert_called_once_with(**expected_kwargs)
