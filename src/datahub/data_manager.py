from __future__ import annotations

from pathlib import Path
import pandas as pd


class DataManager:

    FINA_INDICATOR_KEY_COLUMNS = ["ts_code", "ann_date", "end_date"]

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

    def get_stock_basic(
        self,
        ts_codes: list[str] | None = None,
        active_only: bool = True
    ) -> pd.DataFrame:
        """
        读取股票基础信息。

        说明
        ----
        stock_basic 不是按月分区表，而是全量快照表。
        这里仍然通过 DataManager 暴露统一读取入口，避免上层模块直接访问原始文件。
        """

        path = self.raw_root / "stock_basic" / "stock_basic.parquet"

        if not path.exists():
            return pd.DataFrame()

        df = pd.read_parquet(path)

        if ts_codes is not None:
            df = df[df["ts_code"].isin(ts_codes)]

        if active_only and "is_active" in df.columns:
            df = df[df["is_active"] == 1]

        df = df.sort_values(
            "ts_code"
        ).reset_index(drop=True)

        return df

    def get_fina_indicator(
        self,
        start: str | pd.Timestamp | None = None,
        end: str | pd.Timestamp | None = None,
        ts_codes: list[str] | None = None,
        fields: list[str] | None = None,
    ) -> pd.DataFrame:
        """Read financial indicators filtered by inclusive announcement dates.

        ``start`` and ``end`` bound ``ann_date`` rather than ``end_date``.
        Both boundaries are inclusive; ``None`` leaves that side unbounded.
        Files are read from ``financial/fina_indicator/ts_code=<code>.parquet``
        below ``raw_root`` and are never modified.
        """

        if fields is not None:
            if (
                not isinstance(fields, list)
                or not fields
                or any(not isinstance(field, str) or not field for field in fields)
            ):
                raise ValueError("fields must be a non-empty list of strings")
            if len(fields) != len(set(fields)):
                raise ValueError("fields must not contain duplicates")

        start_dt = self._parse_optional_date(start, "start")
        end_dt = self._parse_optional_date(end, "end")
        if start_dt is not None and end_dt is not None and start_dt > end_dt:
            raise ValueError("start must be less than or equal to end")

        output_columns = self.FINA_INDICATOR_KEY_COLUMNS.copy()
        if fields is not None:
            output_columns.extend(
                field for field in fields if field not in output_columns
            )

        table_root = self.raw_root / "financial" / "fina_indicator"
        if ts_codes == [] or not table_root.exists():
            return pd.DataFrame(columns=output_columns)

        if ts_codes is None:
            paths = sorted(table_root.glob("ts_code=*.parquet"))
        else:
            paths = [
                table_root / f"ts_code={ts_code}.parquet"
                for ts_code in dict.fromkeys(ts_codes)
            ]
            paths = [path for path in paths if path.exists()]

        if not paths:
            return pd.DataFrame(columns=output_columns)

        result = pd.concat(
            [pd.read_parquet(path) for path in paths],
            ignore_index=True,
            sort=False,
        )
        missing_keys = [
            column
            for column in self.FINA_INDICATOR_KEY_COLUMNS
            if column not in result.columns
        ]
        if missing_keys:
            raise ValueError(
                f"Financial indicator data is missing required columns: {missing_keys}"
            )

        for column in ["ann_date", "end_date"]:
            result[column] = self._parse_date_column(result[column], column)

        duplicate_keys = result.duplicated(
            subset=self.FINA_INDICATOR_KEY_COLUMNS,
            keep=False,
        )
        if duplicate_keys.any():
            raise ValueError(
                "Financial indicator data contains duplicate keys for "
                "['ts_code', 'end_date', 'ann_date']"
            )

        if start_dt is not None:
            result = result[result["ann_date"] >= start_dt]
        if end_dt is not None:
            result = result[result["ann_date"] <= end_dt]

        if fields is not None:
            missing_fields = [field for field in fields if field not in result.columns]
            if missing_fields:
                raise ValueError(
                    f"Financial indicator fields do not exist: {missing_fields}"
                )
            result = result[output_columns]

        return result.sort_values(
            ["ts_code", "end_date", "ann_date"]
        ).reset_index(drop=True)

    @staticmethod
    def _parse_optional_date(
        value: str | pd.Timestamp | None,
        name: str,
    ) -> pd.Timestamp | None:
        if value is None:
            return None
        try:
            parsed = pd.to_datetime(value, errors="raise", format="mixed")
        except Exception as exc:
            raise ValueError(f"{name} cannot be converted to datetime") from exc
        if pd.isna(parsed):
            raise ValueError(f"{name} cannot be converted to datetime")
        return pd.Timestamp(parsed)

    @staticmethod
    def _parse_date_column(series: pd.Series, name: str) -> pd.Series:
        try:
            parsed = pd.to_datetime(series, errors="raise", format="mixed")
        except Exception as exc:
            raise ValueError(f"{name} contains values that cannot be converted to datetime") from exc
        if parsed.isna().any():
            raise ValueError(f"{name} contains values that cannot be converted to datetime")
        return parsed

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
