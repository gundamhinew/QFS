from __future__ import annotations

from pathlib import Path
import pandas as pd


class ParquetStore:
    def __init__(self, raw_root: str):
        self.raw_root = Path(raw_root)

    def _read_existing(self, path: Path) -> pd.DataFrame:
        if path.exists():
            return pd.read_parquet(path)
        return pd.DataFrame()

    def write_single_file(
        self,
        df: pd.DataFrame,
        relative_path: str,
        subset_keys: list[str],
        sort_keys: list[str]
    ) -> None:
        path = self.raw_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)

        old = self._read_existing(path)
        merged = pd.concat([old, df], ignore_index=True)

        if not merged.empty:
            merged = merged.drop_duplicates(subset=subset_keys, keep="last")
            merged = merged.sort_values(sort_keys).reset_index(drop=True)

        merged.to_parquet(path, index=False)

    def write_month_partition(
        self,
        df: pd.DataFrame,
        table_name: str,
        date_col: str,
        subset_keys: list[str],
        sort_keys: list[str]
    ) -> None:
        if df.empty:
            return

        work = df.copy()
        work[date_col] = pd.to_datetime(work[date_col])

        work["year"] = work[date_col].dt.year
        work["month"] = work[date_col].dt.month

        for (year, month), part in work.groupby(["year", "month"]):
            path = self.raw_root / table_name / f"year={year}" / f"month={month:02d}.parquet"
            path.parent.mkdir(parents=True, exist_ok=True)

            old = self._read_existing(path)
            merged = pd.concat([old, part.drop(columns=["year", "month"])], ignore_index=True)

            merged = merged.drop_duplicates(subset=subset_keys, keep="last")
            merged = merged.sort_values(sort_keys).reset_index(drop=True)
            merged.to_parquet(path, index=False)

    def write_ts_code_partition(
        self,
        df: pd.DataFrame,
        table_name: str,
        code_col: str,
        subset_keys: list[str],
        sort_keys: list[str]
    ) -> None:
        if df.empty:
            return

        for ts_code, part in df.groupby(code_col):
            path = self.raw_root / table_name / f"ts_code={ts_code}.parquet"
            path.parent.mkdir(parents=True, exist_ok=True)

            old = self._read_existing(path)
            merged = pd.concat([old, part], ignore_index=True)
            merged = merged.drop_duplicates(subset=subset_keys, keep="last")
            merged = merged.sort_values(sort_keys).reset_index(drop=True)
            merged.to_parquet(path, index=False)