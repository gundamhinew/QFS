from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class BaseAlphaModel(ABC):
    model_type: str = "base"

    @abstractmethod
    def build(
        self,
        processed_factors: dict[str, pd.DataFrame],
        config: dict,
    ) -> pd.DataFrame:
        """
        Build a ModelScoreFrame.
        """
        raise NotImplementedError
