from __future__ import annotations

import pandas as pd


class FactorAligner:
    """
    Align ProcessedFactorFrame objects on trade_date + ts_code.
    """

    SUPPORTED_POLICIES = {"intersection", "fill_zero", "renormalize"}

    def align(
        self,
        processed_factors: dict[str, pd.DataFrame],
        missing_policy: str = "intersection",
        min_factor_count: int | None = None,
    ) -> pd.DataFrame:
        if missing_policy not in self.SUPPORTED_POLICIES:
            raise ValueError(
                f"missing_policy must be one of {sorted(self.SUPPORTED_POLICIES)}"
            )

        if not processed_factors:
            raise ValueError("processed_factors must not be empty")

        frames = []
        aliases = list(processed_factors)

        for alias, df in processed_factors.items():
            required = {"trade_date", "ts_code", "factor_score"}
            missing = required - set(df.columns)
            if missing:
                raise ValueError(
                    f"Factor '{alias}' is missing required columns: {sorted(missing)}"
                )

            frame = df[["trade_date", "ts_code", "factor_score"]].copy()
            frame["trade_date"] = pd.to_datetime(frame["trade_date"])
            frame = frame.rename(columns={"factor_score": alias})
            frames.append(frame)

        aligned = frames[0]
        for frame in frames[1:]:
            aligned = aligned.merge(
                frame,
                on=["trade_date", "ts_code"],
                how="outer",
            )

        score_cols = aliases
        aligned["factor_count"] = aligned[score_cols].notna().sum(axis=1)
        aligned["missing_factor_count"] = len(score_cols) - aligned["factor_count"]

        threshold = min_factor_count
        if threshold is None:
            threshold = len(score_cols) if missing_policy == "intersection" else 1

        before = len(aligned)
        aligned = aligned[aligned["factor_count"] >= threshold].copy()

        if aligned.empty and before > 0:
            raise ValueError(
                "Factor alignment removed all rows; lower min_factor_count or "
                "inspect factor coverage"
            )

        dropped_ratio = 1.0 - len(aligned) / before if before else 0.0
        if dropped_ratio > 0.95:
            raise ValueError(
                f"Factor alignment dropped {dropped_ratio:.2%} of rows; "
                "refusing to silently lose samples"
            )

        if missing_policy == "intersection":
            aligned = aligned.dropna(subset=score_cols).copy()
            aligned["factor_count"] = len(score_cols)
            aligned["missing_factor_count"] = 0
        elif missing_policy == "fill_zero":
            aligned[score_cols] = aligned[score_cols].fillna(0.0)
        elif missing_policy == "renormalize":
            # Keep NaN values for downstream per-row weight renormalization.
            pass

        return aligned.sort_values(["trade_date", "ts_code"]).reset_index(drop=True)
