from __future__ import annotations

import pytest

from src.factors.base import BaseFactor
from src.factors.momentum import MomentumFactor
from src.factors.registry import (
    DEFAULT_FACTOR_REGISTRY,
    FACTOR_REGISTRY,
    FactorRegistry,
    register_factor,
)


class DummyFactor(BaseFactor):
    factor_name = "dummy"

    def build(self, start, end, universe=None):
        raise NotImplementedError


class AnotherDummyFactor(BaseFactor):
    factor_name = "another_dummy"

    def build(self, start, end, universe=None):
        raise NotImplementedError


def test_factor_registry_register_get_list_contains():
    registry = FactorRegistry()

    registry.register("dummy", DummyFactor)

    assert registry.get("dummy") is DummyFactor
    assert registry.contains("dummy")
    assert registry.list() == ["dummy"]


def test_register_factor_decorator_registers_factor():
    registry = FactorRegistry()

    @register_factor("decorated_dummy", registry=registry)
    class DecoratedDummyFactor(DummyFactor):
        pass

    assert registry.get("decorated_dummy") is DecoratedDummyFactor


def test_duplicate_factor_registration_raises():
    registry = FactorRegistry()
    registry.register("dummy", DummyFactor)

    with pytest.raises(ValueError, match="already registered"):
        registry.register("dummy", AnotherDummyFactor)


def test_factor_auto_discovery_registers_momentum():
    assert DEFAULT_FACTOR_REGISTRY.contains("momentum")
    assert DEFAULT_FACTOR_REGISTRY.get("momentum") is MomentumFactor


def test_legacy_factor_registry_mapping_still_works():
    assert FACTOR_REGISTRY["momentum"] is MomentumFactor
    assert "momentum" in FACTOR_REGISTRY
    assert "momentum" in list(FACTOR_REGISTRY.keys())
