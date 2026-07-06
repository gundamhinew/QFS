from __future__ import annotations

import pandas as pd

from src.alpha_models.aligner import FactorAligner
from src.alpha_models.base import BaseAlphaModel
from src.alpha_models.registry import register_alpha_model
from src.contracts.model_frames import validate_model_score_frame


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    if not weights:
        raise ValueError("weights must not be empty")

    total = sum(float(value) for value in weights.values())
    if total == 0:
        raise ValueError("weight sum must not be zero")

    return {
        key: float(value) / total
        for key, value in weights.items()
    }


def factor_aliases(config: dict) -> list[str]:
    aliases = []
    for item in config.get("factors", []):
        alias = item.get("alias") or item.get("factor_id")
        if alias in aliases:
            raise ValueError(f"Duplicate factor alias: {alias}")
        aliases.append(alias)
    return aliases


@register_alpha_model("weighted_score")
class WeightedScoreAlphaModel(BaseAlphaModel):
    model_type = "weighted_score"

    def build(
        self,
        processed_factors: dict[str, pd.DataFrame],
        config: dict,
    ) -> pd.DataFrame:
        aliases = factor_aliases(config)
        missing = [alias for alias in aliases if alias not in processed_factors]
        if missing:
            raise ValueError(f"Missing processed factors: {missing}")

        raw_weights = {
            item.get("alias") or item.get("factor_id"): item.get("weight", 1.0)
            for item in config.get("factors", [])
        }
        weights = normalize_weights(raw_weights)
        alignment = config.get("alignment", {})
        missing_policy = alignment.get("missing_policy", "intersection")
        min_factor_count = alignment.get("min_factor_count")

        aligned = FactorAligner().align(
            {alias: processed_factors[alias] for alias in aliases},
            missing_policy=missing_policy,
            min_factor_count=min_factor_count,
        )

        score = pd.Series(0.0, index=aligned.index)
        contribution_cols = []

        for alias in aliases:
            contribution_col = f"contribution_{alias}"
            contribution_cols.append(contribution_col)

            if missing_policy == "renormalize":
                valid_weight_sum = pd.Series(0.0, index=aligned.index)
                for other_alias in aliases:
                    valid_weight_sum += aligned[other_alias].notna().astype(float) * weights[other_alias]
                effective_weight = aligned[alias].notna().astype(float) * weights[alias] / valid_weight_sum
                effective_weight = effective_weight.replace([float("inf"), -float("inf")], 0).fillna(0)
                contribution = aligned[alias].fillna(0.0) * effective_weight
            else:
                contribution = aligned[alias].fillna(0.0) * weights[alias]

            aligned[contribution_col] = contribution
            score += contribution

        result = aligned[["trade_date", "ts_code", "factor_count", "missing_factor_count"]].copy()
        result["model_id"] = config["model_id"]
        result["model_score"] = score
        result["normalized_weight"] = str(weights)

        for col in contribution_cols:
            result[col] = aligned[col]

        return validate_model_score_frame(result)
