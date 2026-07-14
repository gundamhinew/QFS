from __future__ import annotations

import pytest

from src.factors.scaffold import create_factor_template


def test_create_factor_template_creates_expected_files(tmp_path):
    created = create_factor_template(
        factor_id="example_factor",
        implementation="example",
        class_name="ExampleFactor",
        project_root=tmp_path,
    )

    assert created.factor_file.exists()
    assert created.config_file.exists()
    assert created.test_file.exists()
    assert "@register_factor(\"example\")" in created.factor_file.read_text(
        encoding="utf-8"
    )
    assert "class ExampleFactor(BaseFactor)" in created.factor_file.read_text(
        encoding="utf-8"
    )
    assert "TODO: implement the factor calculation" in created.factor_file.read_text(
        encoding="utf-8"
    )
    assert "factor_id: example_factor" in created.config_file.read_text(
        encoding="utf-8"
    )


def test_create_factor_template_conflict_raises(tmp_path):
    create_factor_template(
        factor_id="example_factor",
        implementation="example",
        class_name="ExampleFactor",
        project_root=tmp_path,
    )

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        create_factor_template(
            factor_id="example_factor",
            implementation="example",
            class_name="ExampleFactor",
            project_root=tmp_path,
        )


def test_create_factor_template_force_overwrites(tmp_path):
    created = create_factor_template(
        factor_id="example_factor",
        implementation="example",
        class_name="ExampleFactor",
        project_root=tmp_path,
    )
    created.factor_file.write_text("old content", encoding="utf-8")

    create_factor_template(
        factor_id="example_factor",
        implementation="example",
        class_name="ExampleFactor",
        force=True,
        project_root=tmp_path,
    )

    assert "old content" not in created.factor_file.read_text(encoding="utf-8")
    assert "class ExampleFactor(BaseFactor)" in created.factor_file.read_text(
        encoding="utf-8"
    )
