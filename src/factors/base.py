from __future__ import annotations

from abc import ABC, abstractmethod
import pandas as pd

from src.datahub.data_manager import DataManager


class BaseFactor(ABC):

    factor_name: str = "base_factor"

    def __init__(
        self,
        dm: DataManager,
        params: dict | None = None
    ):
        self.dm = dm
        self.params = params or {}

    @abstractmethod
    def build(
        self,
        start: str,
        end: str,
        universe: list[str] | None = None
    ) -> pd.DataFrame:
        """
        必须返回：

        ts_code
        trade_date
        factor_value
        """
        pass