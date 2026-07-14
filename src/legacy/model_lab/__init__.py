"""Legacy model-lab public API; use :mod:`src.alpha_models`."""

from src.alpha_models.checker import ModelChecker
from src.alpha_models.evaluator import ModelEvaluator


__all__ = [
    "ModelChecker",
    "ModelEvaluator",
]
