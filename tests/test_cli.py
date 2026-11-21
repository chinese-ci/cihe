from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from cihe import cli
from cihe.encoding import ConverterError
from cihe.material import MaterialContractError
from cihe.report import BuildReport, CategoryBuild


def _report(exceeded: bool) -> BuildReport:
    category = CategoryBuild(
        material_path="下里巴人/日常口语",
        total=10,
        encoded=9,
        runtime_only=1,
        dropped=0,
        skips=(),
    )
    overall = CategoryBuild(
        material_path=None,
        total=10,
        encoded=9,
        runtime_only=1,
        dropped=0,
        skips=(),
    )
    return BuildReport(
        overall=overall,
        categories=(category,),
        overall_skip_limit=0.005,
        category_skip_limit=0.02,
        violations=("总体",) if exceeded else (),
    )


def _result(tmp_path: Path, exceeded: bool):
    return SimpleNamespace(
        ci_dir=tmp_path / "ci",
        report=_report(exceeded),
        report_json=tmp_path / "build-report.json",
        report_md=tmp_path / "build-report.md",
        threshold_exceeded=exceeded,
        target="rime-wubi",
        target_version="1.0.0",
    )


def test_cli_returns_zero_below_threshold(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        cli, "run_consumer", lambda *args, **kwargs: _result(tmp_path, False)
    )

    assert cli.main(["--material", str(tmp_path)]) == 0


def test_cli_returns_two_when_threshold_exceeded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        cli, "run_consumer", lambda *args, **kwargs: _result(tmp_path, True)
    )

    assert cli.main(["--material", str(tmp_path)]) == 2


def test_cli_returns_one_on_missing_arguments() -> None:
    assert cli.main([]) == 1


def test_cli_rejects_unknown_target(tmp_path: Path) -> None:
    assert (
        cli.main(
            ["--material", str(tmp_path), "--target", "not-a-target"]
        )
        == 1
    )


def test_cli_returns_one_on_invalid_threshold() -> None:
    assert (
        cli.main(
            [
                "--material",
                "x",
                "--overall-skip-limit",
                "not-a-number",
            ]
        )
        == 1
    )


def test_cli_returns_one_on_input_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fail(*args, **kwargs):
        raise MaterialContractError("坏物料")

    monkeypatch.setattr(cli, "run_consumer", fail)

    assert cli.main(["--material", str(tmp_path)]) == 1


def test_cli_returns_one_on_converter_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fail(*args, **kwargs):
        raise ConverterError("编码器坏了")

    monkeypatch.setattr(cli, "run_consumer", fail)

    assert cli.main(["--material", str(tmp_path)]) == 1
