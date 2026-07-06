from __future__ import annotations

from collections.abc import Callable

from src.portfolio.base import BasePortfolioBuilder


PortfolioBuilderClass = type[BasePortfolioBuilder]
PORTFOLIO_REGISTRY: dict[str, PortfolioBuilderClass] = {}


def register_portfolio_builder(
    portfolio_type: str,
) -> Callable[[PortfolioBuilderClass], PortfolioBuilderClass]:
    def _decorator(builder_cls: PortfolioBuilderClass) -> PortfolioBuilderClass:
        if portfolio_type in PORTFOLIO_REGISTRY:
            existing = PORTFOLIO_REGISTRY[portfolio_type]
            raise ValueError(
                f"Portfolio builder '{portfolio_type}' already registered with "
                f"{existing.__module__}.{existing.__name__}"
            )
        PORTFOLIO_REGISTRY[portfolio_type] = builder_cls
        return builder_cls

    return _decorator
