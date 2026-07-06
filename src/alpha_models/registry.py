from __future__ import annotations

from collections.abc import Callable

from src.alpha_models.base import BaseAlphaModel


AlphaModelClass = type[BaseAlphaModel]
ALPHA_MODEL_REGISTRY: dict[str, AlphaModelClass] = {}


def register_alpha_model(model_type: str) -> Callable[[AlphaModelClass], AlphaModelClass]:
    def _decorator(model_cls: AlphaModelClass) -> AlphaModelClass:
        if model_type in ALPHA_MODEL_REGISTRY:
            existing = ALPHA_MODEL_REGISTRY[model_type]
            raise ValueError(
                f"Alpha model '{model_type}' already registered with "
                f"{existing.__module__}.{existing.__name__}"
            )
        ALPHA_MODEL_REGISTRY[model_type] = model_cls
        return model_cls

    return _decorator
