from __future__ import annotations

import pandas as pd

from src.alpha_models.base import BaseAlphaModel
from src.alpha_models.registry import register_alpha_model
from src.contracts.model_frames import validate_model_score_frame


@register_alpha_model("single_factor")
class SingleFactorAlphaModel(BaseAlphaModel):
    model_type = "single_factor"

    def build(
        self,
        processed_factors: dict[str, pd.DataFrame],
        config: dict,
    ) -> pd.DataFrame:
        factors = config.get("factors", [])
        if len(factors) != 1:
            raise ValueError("single_factor model requires exactly one factor")

        alias = factors[0].get("alias") or factors[0].get("factor_id")
        if alias not in processed_factors:
            raise ValueError(f"Missing processed factor: {alias}")

        df = processed_factors[alias].copy()
        result = df[["trade_date", "ts_code", "factor_score"]].copy()
        result["model_id"] = config["model_id"]
        result = result.rename(columns={"factor_score": "model_score"})
        result["factor_count"] = result["model_score"].notna().astype(int)
        result["missing_factor_count"] = 1 - result["factor_count"]
        result[f"contribution_{alias}"] = result["model_score"]
        result["normalized_weight"] = str({alias: 1.0})
        result = result.dropna(subset=["model_score"])

        return validate_model_score_frame(result)
