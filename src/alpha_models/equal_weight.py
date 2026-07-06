from __future__ import annotations

from src.alpha_models.registry import register_alpha_model
from src.alpha_models.weighted_score import WeightedScoreAlphaModel


@register_alpha_model("equal_weight")
class EqualWeightAlphaModel(WeightedScoreAlphaModel):
    model_type = "equal_weight"

    def build(self, processed_factors, config):
        adjusted = dict(config)
        adjusted["factors"] = [
            {
                **item,
                "weight": 1.0,
            }
            for item in config.get("factors", [])
        ]
        return super().build(processed_factors, adjusted)
