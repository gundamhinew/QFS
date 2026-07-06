from __future__ import annotations

import pandas as pd

from src.contracts.portfolio_frames import validate_target_positions
from src.portfolio.registry import PORTFOLIO_REGISTRY
from src.risk.basic import BasicWeightConstraint
from src.risk.noop import NoOpRisk
from src.strategies.rebalance_policy import RebalancePolicy
from src.timing.noop import NoOpTiming


class StrategyPipeline:
    """
    ModelScoreFrame -> target_positions pipeline.

    This pipeline does not download data, calculate factors, calculate forward
    returns, simulate trades, handle fees, or submit orders.
    """

    def build_target_positions(
        self,
        model_scores: pd.DataFrame,
        config: dict,
    ) -> pd.DataFrame:
        strategy_id = config["strategy_id"]

        rebalance_config = config.get("rebalance", {})
        policy = RebalancePolicy(
            frequency=rebalance_config.get("frequency", "daily")
        )
        filtered_scores = policy.filter_model_scores(model_scores)

        portfolio_config = config.get("portfolio", {})
        portfolio_type = portfolio_config.get("type", "top_n_equal_weight")
        if portfolio_type not in PORTFOLIO_REGISTRY:
            raise ValueError(
                f"Unknown portfolio builder '{portfolio_type}'. "
                f"Available: {sorted(PORTFOLIO_REGISTRY)}"
            )

        builder = PORTFOLIO_REGISTRY[portfolio_type]()
        base_weights = builder.build(
            model_scores=filtered_scores,
            config=portfolio_config,
        )

        if base_weights.empty:
            return pd.DataFrame(
                columns=[
                    "trade_date",
                    "ts_code",
                    "target_weight",
                    "strategy_id",
                ]
            )

        base_weights["strategy_id"] = strategy_id

        timing_config = config.get("timing", {"type": "noop"})
        timing_type = timing_config.get("type", "noop")
        if timing_type != "noop":
            raise ValueError("Only NoOpTiming is implemented in this work package")
        timed = NoOpTiming().apply(base_weights, timing_config)

        risk_config = config.get("risk", {"type": "noop"})
        risk_type = risk_config.get("type", "noop")
        if risk_type == "noop":
            risked = NoOpRisk().apply(timed, risk_config)
        elif risk_type == "basic_weight_constraint":
            risked = BasicWeightConstraint().apply(timed, risk_config)
        else:
            raise ValueError("Unknown risk overlay: " + str(risk_type))

        target_positions = risked[
            [
                "trade_date",
                "ts_code",
                "target_weight",
                "strategy_id",
                "model_score",
                "raw_target_weight",
                "exposure",
            ]
        ].copy()

        return validate_target_positions(target_positions)
