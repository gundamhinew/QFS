from __future__ import annotations

from collections.abc import Iterator, Mapping
import importlib
import pkgutil
from types import MappingProxyType
from typing import Callable, TypeVar

from src.factors.base import BaseFactor


FactorClass = type[BaseFactor]
F = TypeVar("F", bound=FactorClass)


class FactorRegistry:
    """
    Registry for factor implementations.

    The registry stores factor classes by stable factor_id. It is intentionally
    small in this work package: discovery and lookup only, no factor checking,
    evaluation, catalog, or model logic.
    """

    def __init__(self):
        self._factors: dict[str, FactorClass] = {}

    def register(
        self,
        factor_id: str,
        factor_cls: FactorClass,
    ) -> FactorClass:
        normalized_id = self._normalize_factor_id(factor_id)

        if normalized_id in self._factors:
            existing = self._factors[normalized_id]
            raise ValueError(
                f"Factor '{normalized_id}' is already registered with "
                f"{existing.__module__}.{existing.__name__}; cannot register "
                f"{factor_cls.__module__}.{factor_cls.__name__}"
            )

        self._factors[normalized_id] = factor_cls
        return factor_cls

    def get(self, factor_id: str) -> FactorClass:
        normalized_id = self._normalize_factor_id(factor_id)

        if normalized_id not in self._factors:
            available = ", ".join(self.list())
            raise KeyError(
                f"Unknown factor '{normalized_id}'. "
                f"Available factors: {available}"
            )

        return self._factors[normalized_id]

    def list(self) -> list[str]:
        return sorted(self._factors)

    def contains(self, factor_id: str) -> bool:
        return self._normalize_factor_id(factor_id) in self._factors

    def as_mapping(self) -> Mapping[str, FactorClass]:
        return MappingProxyType(self._factors)

    @staticmethod
    def _normalize_factor_id(factor_id: str) -> str:
        if not isinstance(factor_id, str):
            raise TypeError("factor_id must be a string")

        normalized_id = factor_id.strip()

        if not normalized_id:
            raise ValueError("factor_id must not be empty")

        return normalized_id


DEFAULT_FACTOR_REGISTRY = FactorRegistry()


def register_factor(
    factor_id: str,
    registry: FactorRegistry | None = None,
) -> Callable[[F], F]:
    """
    Decorator for registering factor classes.
    """

    target_registry = registry or DEFAULT_FACTOR_REGISTRY

    def _decorator(factor_cls: F) -> F:
        target_registry.register(
            factor_id=factor_id,
            factor_cls=factor_cls,
        )
        return factor_cls

    return _decorator


class _FactorRegistryView(Mapping[str, FactorClass]):
    """
    Read-only compatibility mapping for legacy FACTOR_REGISTRY users.
    """

    def __init__(self, registry: FactorRegistry):
        self._registry = registry

    def __getitem__(self, factor_id: str) -> FactorClass:
        return self._registry.get(factor_id)

    def __iter__(self) -> Iterator[str]:
        return iter(self._registry.list())

    def __len__(self) -> int:
        return len(self._registry.list())

    def __contains__(self, factor_id: object) -> bool:
        if not isinstance(factor_id, str):
            return False
        return self._registry.contains(factor_id)

    def keys(self):
        return self._registry.as_mapping().keys()

    def values(self):
        return self._registry.as_mapping().values()

    def items(self):
        return self._registry.as_mapping().items()


DISCOVERY_SKIP_MODULES = {
    "__init__",
    "_init_",
    "base",
    "registry",
    "discovery",
    # Research-lifecycle modules share the factor domain but do not define
    # registerable factor implementations.
    "catalog",
    "checker",
    "evaluator",
    "factor_runner",
    "forward_returns",
    "processor",
    "quantile_analysis",
    "scaffold",
    "store",
}


def discover_factors(
    package_name: str = "src.factors",
) -> None:
    """
    Import factor modules under src/factors so decorators can register classes.
    """

    package = importlib.import_module(package_name)
    package_paths = getattr(package, "__path__", None)

    if package_paths is None:
        raise ValueError(f"Factor package '{package_name}' has no __path__")

    for module_info in pkgutil.iter_modules(package_paths):
        module_name = module_info.name

        if module_name in DISCOVERY_SKIP_MODULES:
            continue

        full_module_name = f"{package_name}.{module_name}"

        try:
            importlib.import_module(full_module_name)
        except Exception as exc:
            raise ImportError(
                f"Failed to import factor module '{full_module_name}': {exc}"
            ) from exc


FACTOR_REGISTRY = _FactorRegistryView(DEFAULT_FACTOR_REGISTRY)


discover_factors()


__all__ = [
    "DEFAULT_FACTOR_REGISTRY",
    "FACTOR_REGISTRY",
    "FactorRegistry",
    "discover_factors",
    "register_factor",
]
