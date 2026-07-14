from __future__ import annotations

import pandas as pd


class NoOpRisk:
    risk_type = "noop"

    def apply(
        self,
        weights: pd.DataFrame,
        config: dict | None = None,
    ) -> pd.DataFrame:
        result = weights.copy()
        if "target_weight" not in result.columns:
            result["target_weight"] = result["raw_target_weight"]
        return result
