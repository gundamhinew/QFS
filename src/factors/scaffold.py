from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.core.config_loader import PROJECT_ROOT


@dataclass(frozen=True)
class CreatedFactorFiles:
    factor_file: Path
    config_file: Path
    test_file: Path


def _factor_module_template(
    class_name: str,
    implementation: str,
) -> str:
    return f'''from __future__ import annotations

import pandas as pd

from src.factors.base import BaseFactor
from src.factors.registry import register_factor


@register_factor("{implementation}")
class {class_name}(BaseFactor):
    """
    TODO: describe the economic intuition and raw data requirements.
    """

    factor_id = "{implementation}"
    factor_name = "{implementation}"

    def build(
        self,
        start: str,
        end: str,
        universe: list[str] | None = None,
    ) -> pd.DataFrame:
        """
        Build a RawFactorFrame-like DataFrame.

        Required output columns before FactorRunner adaptation:
            trade_date
            ts_code
            factor_value

        TODO: implement the factor calculation. Do not return invented data.
        """

        raise NotImplementedError(
            "Implement {class_name}.build() before running factor checks."
        )
'''


def _factor_config_template(
    factor_id: str,
    implementation: str,
) -> str:
    return f'''schema_version: 2
factor_id: {factor_id}
implementation: {implementation}
version: 1
status: draft

metadata:
  name: "{factor_id}"
  description: "TODO: describe this factor."
  owner: ""
  category: ""

data:
  raw_root: "data/raw"

period:
  start: "2020-01-01"
  end: "2020-12-31"

universe:
  min_list_days: 120
  min_close: 2.0
  min_amount_yuan: 30000000

params: {{}}

preprocess:
  direction: positive
  winsorize: true
  standardize: true

evaluation:
  enabled: false
  note: "Work package two only checks implementation and data quality."

storage:
  save_raw_factor: false
  output_root: "artifacts/factor_runs"
'''


def _factor_test_template(
    class_name: str,
    implementation: str,
) -> str:
    return f'''from __future__ import annotations

import pytest

from src.factors.{implementation} import {class_name}


def test_{implementation}_build_not_implemented():
    factor = {class_name}(dm=None, params={{}})

    with pytest.raises(NotImplementedError):
        factor.build(
            start="2020-01-01",
            end="2020-01-31",
            universe=[],
        )
'''


def _write_file(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(
            f"Refusing to overwrite existing file without --force: {path}"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def create_factor_template(
    factor_id: str,
    implementation: str,
    class_name: str,
    force: bool = False,
    project_root: Path | None = None,
) -> CreatedFactorFiles:
    """
    Create factor code, config, and a starter test.
    """

    root = project_root or PROJECT_ROOT
    factor_file = root / "src" / "factors" / f"{implementation}.py"
    config_file = root / "configs" / "factors" / f"{factor_id}.yaml"
    test_file = root / "tests" / "factors" / f"test_{implementation}.py"

    targets = [factor_file, config_file, test_file]
    conflicts = [
        path
        for path in targets
        if path.exists()
    ]

    if conflicts and not force:
        conflict_text = ", ".join(str(path) for path in conflicts)
        raise FileExistsError(
            f"Refusing to overwrite existing files without --force: {conflict_text}"
        )

    _write_file(
        factor_file,
        _factor_module_template(
            class_name=class_name,
            implementation=implementation,
        ),
        force=force,
    )
    _write_file(
        config_file,
        _factor_config_template(
            factor_id=factor_id,
            implementation=implementation,
        ),
        force=force,
    )
    _write_file(
        test_file,
        _factor_test_template(
            class_name=class_name,
            implementation=implementation,
        ),
        force=force,
    )

    return CreatedFactorFiles(
        factor_file=factor_file,
        config_file=config_file,
        test_file=test_file,
    )
