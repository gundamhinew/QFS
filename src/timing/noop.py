from __future__ import annotations

import pandas as pd


class NoOpTiming:
    timing_type = "noop"

    def apply(
        self,
        weights: pd.DataFrame,
        config: dict | None = None,
    ) -> pd.DataFrame:
        result = weights.copy()
        result["exposure"] = 1.0
        return result
