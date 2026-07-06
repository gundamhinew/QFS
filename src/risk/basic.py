from __future__ import annotations

import numpy as np
import pandas as pd


class BasicWeightConstraint:
    risk_type = "basic_weight_constraint"

    def apply(
        self,
        weights: pd.DataFrame,
        config: dict | None = None,
    ) -> pd.DataFrame:
        config = config or {}
        max_single_weight = config.get("max_single_weight")
        normalize = bool(config.get("normalize_weights", True))

        result = weights.copy()
        if "raw_target_weight" not in result.columns:
            raise ValueError("weights must contain raw_target_weight")

        result["target_weight"] = pd.to_numeric(
            result["raw_target_weight"],
            errors="raise",
        )

        values = result["target_weight"].to_numpy(dtype=float)
        if np.isnan(values).any() or np.isinf(values).any():
            raise ValueError("target weights must not contain NaN or inf")

        if (result["target_weight"] < 0).any():
            raise ValueError("target weights must be non-negative")

        if "exposure" not in result.columns:
            result["exposure"] = 1.0

        if max_single_weight is not None:
            max_weight = float(max_single_weight)
            if max_weight <= 0:
                raise ValueError("max_single_weight must be positive")
            result["target_weight"] = result["target_weight"].clip(upper=max_weight)

        adjusted_parts = []
        for (trade_date, strategy_id), group in result.groupby(["trade_date", "strategy_id"], dropna=False):
            group = group.copy()
            exposure = float(group["exposure"].iloc[0])
            if exposure < 0:
                raise ValueError("exposure must be non-negative")

            total = float(group["target_weight"].sum())
            if total > exposure and total > 0:
                group["target_weight"] = group["target_weight"] * exposure / total
            elif normalize and total > 0 and total < exposure:
                scale = exposure / total
                candidate = group["target_weight"] * scale
                if max_single_weight is None or (candidate <= float(max_single_weight) + 1e-12).all():
                    group["target_weight"] = candidate

            if group["target_weight"].sum() > exposure + 1e-9:
                raise ValueError("total target weight exceeds exposure")

            adjusted_parts.append(group)

        return pd.concat(adjusted_parts, ignore_index=True)
