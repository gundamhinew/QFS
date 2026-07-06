from __future__ import annotations

import pandas as pd

from src.alpha_models.aligner import FactorAligner
from src.alpha_models.base import BaseAlphaModel
from src.alpha_models.registry import register_alpha_model
from src.alpha_models.weighted_score import factor_aliases, normalize_weights
from src.contracts.model_frames import validate_model_score_frame


@register_alpha_model("category_weighted")
class CategoryWeightedAlphaModel(BaseAlphaModel):
    model_type = "category_weighted"

    def build(self, processed_factors: dict[str, pd.DataFrame], config: dict) -> pd.DataFrame:
        aliases = factor_aliases(config)
        missing = [alias for alias in aliases if alias not in processed_factors]
        if missing:
            raise ValueError(f"Missing processed factors: {missing}")

        alignment = config.get("alignment", {})
        missing_policy = alignment.get("missing_policy", "intersection")
        min_factor_count = alignment.get("min_factor_count")
        aligned = FactorAligner().align(
            {alias: processed_factors[alias] for alias in aliases},
            missing_policy=missing_policy,
            min_factor_count=min_factor_count,
        )

        factors = config.get("factors", [])
        categories = config.get("categories", {})
        category_weights = normalize_weights({
            name: spec.get("weight", 1.0)
            for name, spec in categories.items()
        })

        factor_to_category = {}
        for category, spec in categories.items():
            for alias in spec.get("factors", []):
                factor_to_category[alias] = category

        for item in factors:
            alias = item.get("alias") or item.get("factor_id")
            if alias not in factor_to_category:
                raise ValueError(f"Factor '{alias}' is not assigned to a category")

        score = pd.Series(0.0, index=aligned.index)
        contribution_cols = []

        for category, category_weight in category_weights.items():
            category_aliases = [
                alias for alias, assigned in factor_to_category.items()
                if assigned == category
            ]
            if not category_aliases:
                continue

            if missing_policy == "renormalize":
                category_score = aligned[category_aliases].mean(axis=1, skipna=True).fillna(0.0)
            else:
                category_score = aligned[category_aliases].fillna(0.0).mean(axis=1)

            score += category_score * category_weight

            for alias in category_aliases:
                contribution_col = f"contribution_{alias}"
                contribution_cols.append(contribution_col)
                aligned[contribution_col] = (
                    aligned[alias].fillna(0.0)
                    * category_weight
                    / len(category_aliases)
                )

        result = aligned[["trade_date", "ts_code", "factor_count", "missing_factor_count"]].copy()
        result["model_id"] = config["model_id"]
        result["model_score"] = score
        result["normalized_weight"] = str(category_weights)

        for col in contribution_cols:
            result[col] = aligned[col]

        return validate_model_score_frame(result)
