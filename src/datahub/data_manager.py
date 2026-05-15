from __future__ import annotations

from pathlib import Path
import pandas as pd


class DataManager:

    def __init__(self, raw_root: str = "./data/raw"):
        self.raw_root = Path(raw_root)

    def _collect_monthly_files(
        self,
        table_name: str,
        start: str,
        end: str
    ) -> list[Path]:

        start_dt = pd.to_datetime(start)
        end_dt = pd.to_datetime(end)

        paths = []

        current = start_dt.replace(day=1)

        while current <= end_dt:
            year = current.year
            month = current.month

            path = (
                self.raw_root
                / table_name
                / f"year={year}"
                / f"month={month:02d}.parquet"
            )

            if path.exists():
                paths.append(path)

            current = current + pd.offsets.MonthBegin(1)

        return paths

    def _read_monthly_table(
        self,
        table_name: str,
        start: str,
        end: str
    ) -> pd.DataFrame:

        files = self._collect_monthly_files(
            table_name,
            start,
            end
        )

        if not files:
            return pd.DataFrame()

        dfs = [
            pd.read_parquet(f)
            for f in files
        ]

        df = pd.concat(dfs, ignore_index=True)

        return df

    def get_daily_price(
        self,
        start: str,
        end: str,
        ts_codes: list[str] | None = None
    ) -> pd.DataFrame:

        df = self._read_monthly_table(
            "daily_price",
            start,
            end
        )

        if df.empty:
            return df

        df["trade_date"] = pd.to_datetime(df["trade_date"])

        mask = (
            (df["trade_date"] >= pd.to_datetime(start))
            &
            (df["trade_date"] <= pd.to_datetime(end))
        )

        df = df.loc[mask]

        if ts_codes is not None:
            df = df[df["ts_code"].isin(ts_codes)]

        df = df.sort_values(
            ["trade_date", "ts_code"]
        ).reset_index(drop=True)

        return df

    def get_adj_factor(
        self,
        start: str,
        end: str,
        ts_codes: list[str] | None = None
    ) -> pd.DataFrame:

        df = self._read_monthly_table(
            "adj_factor",
            start,
            end
        )

        if df.empty:
            return df

        df["trade_date"] = pd.to_datetime(df["trade_date"])

        mask = (
            (df["trade_date"] >= pd.to_datetime(start))
            &
            (df["trade_date"] <= pd.to_datetime(end))
        )

        df = df.loc[mask]

        if ts_codes is not None:
            df = df[df["ts_code"].isin(ts_codes)]

        df = df.sort_values(
            ["trade_date", "ts_code"]
        ).reset_index(drop=True)

        return df

    def get_daily_basic(
        self,
        start: str,
        end: str,
        ts_codes: list[str] | None = None
    ) -> pd.DataFrame:

        df = self._read_monthly_table(
            "daily_basic",
            start,
            end
        )

        if df.empty:
            return df

        df["trade_date"] = pd.to_datetime(df["trade_date"])

        mask = (
            (df["trade_date"] >= pd.to_datetime(start))
            &
            (df["trade_date"] <= pd.to_datetime(end))
        )

        df = df.loc[mask]

        if ts_codes is not None:
            df = df[df["ts_code"].isin(ts_codes)]

        df = df.sort_values(
            ["trade_date", "ts_code"]
        ).reset_index(drop=True)

        return df

    def get_adjusted_price(
            self,
            start: str,
            end: str,
            ts_codes: list[str] | None = None,
            price_cols: list[str] | None = None,
            adjust: str = "total_return"
    ) -> pd.DataFrame:
        """
        获取复权价格。

        adjust:
            total_return:
                使用 price * adj_factor，适合计算收益率、动量、波动率等因子。

            qfq:
                前复权价格，将查询区间最后一天价格锚定为原始价格。
                更适合展示价格曲线。
        """

        if price_cols is None:
            price_cols = ["open", "high", "low", "close"]

        if adjust not in ["total_return", "qfq"]:
            raise ValueError("adjust must be one of: 'total_return', 'qfq'")

        price = self.get_daily_price(
            start=start,
            end=end,
            ts_codes=ts_codes
        )

        adj = self.get_adj_factor(
            start=start,
            end=end,
            ts_codes=ts_codes
        )

        if price.empty or adj.empty:
            return pd.DataFrame()

        df = price.merge(
            adj,
            on=["ts_code", "trade_date"],
            how="left"
        )

        df = df.sort_values(
            ["ts_code", "trade_date"]
        ).reset_index(drop=True)

        df["adj_factor"] = (
            df.groupby("ts_code")["adj_factor"]
            .ffill()
            .bfill()
        )

        if adjust == "total_return":
            for col in price_cols:
                if col in df.columns:
                    df[f"adj_{col}"] = df[col] * df["adj_factor"]

        elif adjust == "qfq":
            latest_factor = (
                df.groupby("ts_code")["adj_factor"]
                .transform("last")
            )

            for col in price_cols:
                if col in df.columns:
                    df[f"adj_{col}"] = (
                            df[col] * df["adj_factor"] / latest_factor
                    )

        df = df.sort_values(
            ["trade_date", "ts_code"]
        ).reset_index(drop=True)

        return df