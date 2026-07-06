from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class BasePortfolioBuilder(ABC):
    portfolio_type: str = "base"

    @abstractmethod
    def build(
        self,
        model_scores: pd.DataFrame,
        config: dict,
    ) -> pd.DataFrame:
        """
        Convert ModelScoreFrame rows to base target weights.
        """
        raise NotImplementedError
