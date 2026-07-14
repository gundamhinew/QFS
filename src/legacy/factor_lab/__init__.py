"""Legacy factor-lab public API; use :mod:`src.factors`."""

from src.factors.catalog import FactorCatalog
from src.factors.checker import FactorChecker
from src.factors.evaluator import FactorEvaluator
from src.factors.scaffold import create_factor_template
from src.factors.store import FactorStore


__all__ = [
    "FactorCatalog",
    "FactorChecker",
    "FactorEvaluator",
    "FactorStore",
    "create_factor_template",
]
