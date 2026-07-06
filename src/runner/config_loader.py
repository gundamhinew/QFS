from __future__ import annotations

from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUPPORTED_SCHEMA_VERSIONS = {1, 2}


class ConfigError(ValueError):
    """
    Raised when a YAML config is syntactically readable but semantically invalid.
    """


def get_schema_version(config: dict) -> int:
    """
    Return config schema_version, treating legacy configs as version 1.
    """

    raw_version = config.get("schema_version", 1)

    if isinstance(raw_version, bool):
        raise ConfigError("schema_version must be an integer, not a boolean")

    try:
        schema_version = int(raw_version)
    except (TypeError, ValueError) as exc:
        raise ConfigError(
            f"schema_version must be an integer. Got: {raw_version!r}"
        ) from exc

    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        supported = sorted(SUPPORTED_SCHEMA_VERSIONS)
        raise ConfigError(
            f"Unsupported schema_version {schema_version}. "
            f"Supported versions: {supported}"
        )

    return schema_version


def resolve_project_path(path_value: str | Path) -> Path:
    """
    Resolve a config path relative to the project root.
    """

    path = Path(path_value)

    if path.is_absolute():
        return path

    return PROJECT_ROOT / path


def load_strategy_config(config_path: str) -> dict:
    """
    读取策略 YAML 配置文件。
    """

    path = resolve_project_path(config_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Strategy config file does not exist: {path}"
        )

    with path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not config:
        raise ValueError(
            f"Strategy config file is empty: {config_path}"
        )

    if not isinstance(config, dict):
        raise ConfigError(
            f"Strategy config must be a YAML mapping: {path}"
        )

    config["schema_version"] = get_schema_version(config)

    return config


def load_factor_config(config_path: str) -> dict:
    """
    Read a factor YAML config file.
    """

    path = resolve_project_path(config_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Factor config file does not exist: {path}"
        )

    with path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not config:
        raise ValueError(
            f"Factor config file is empty: {path}"
        )

    if not isinstance(config, dict):
        raise ConfigError(
            f"Factor config must be a YAML mapping: {path}"
        )

    config["schema_version"] = get_schema_version(config)

    return config


def load_model_config(config_path: str) -> dict:
    """
    Read a model YAML config file.
    """

    path = resolve_project_path(config_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Model config file does not exist: {path}"
        )

    with path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not config:
        raise ValueError(
            f"Model config file is empty: {path}"
        )

    if not isinstance(config, dict):
        raise ConfigError(
            f"Model config must be a YAML mapping: {path}"
        )

    config["schema_version"] = get_schema_version(config)

    return config
