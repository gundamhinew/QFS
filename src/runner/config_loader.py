from __future__ import annotations

from pathlib import Path

import yaml


def load_strategy_config(config_path: str) -> dict:
    """
    读取策略 YAML 配置文件。
    """

    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Strategy config file does not exist: {config_path}"
        )

    with path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not config:
        raise ValueError(
            f"Strategy config file is empty: {config_path}"
        )

    if not isinstance(config, dict):
        raise ValueError(
            f"Strategy config must be a YAML mapping: {config_path}"
        )

    return config
