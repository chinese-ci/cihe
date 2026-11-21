from __future__ import annotations

from pathlib import Path

from cihe.tracer import run_consumer

CI_FILES = [
    "wubi86.ci.daily_spoken.dict.yaml",
]


def test_consumer_contract_matches_golden(
    golden_root: Path,
    material_root: Path,
    char_table_path: Path,
    tmp_path: Path,
) -> None:
    result = run_consumer(
        material_root, tmp_path / "consumer", char_table_path
    )
    ci_dir = result.ci_dir

    assert (ci_dir / "wubi86.ci.daily_spoken.dict.yaml").read_text(
        encoding="utf-8"
    ) == (golden_root / "rime" / "wubi86.ci.daily_spoken.dict.yaml").read_text(
        encoding="utf-8"
    )

    assert {path.name for path in ci_dir.iterdir()} == set(CI_FILES)
    assert not (ci_dir / "wubi86.zi.dict.yaml").exists()
    assert not (ci_dir / "wubi86.dict.yaml").exists()
    assert not list(ci_dir.glob("*.schema.yaml"))

    assert result.converter.imported == 20
    assert result.converter.exported == 20
    assert result.converter.filtered == 0


def test_build_report_matches_golden(
    golden_root: Path,
    material_root: Path,
    char_table_path: Path,
    tmp_path: Path,
) -> None:
    result = run_consumer(
        material_root, tmp_path / "consumer", char_table_path
    )

    assert result.report_json.read_text(encoding="utf-8") == (
        golden_root / "report" / "build-report.json"
    ).read_text(encoding="utf-8")
    assert result.report_md.read_text(encoding="utf-8") == (
        golden_root / "report" / "build-report.md"
    ).read_text(encoding="utf-8")
    assert not result.threshold_exceeded


def test_skip_fixture_matches_golden(
    golden_root: Path,
    skip_material_root: Path,
    char_table_path: Path,
    tmp_path: Path,
) -> None:
    result = run_consumer(
        skip_material_root, tmp_path / "consumer", char_table_path
    )

    category = result.report.categories[0]
    assert (
        category.total,
        category.encoded,
        category.runtime_only,
        category.dropped,
    ) == (7, 2, 1, 4)
    assert [
        (skip.word, skip.disposition, skip.reason)
        for skip in category.skips
    ] == [
        ("卵石", "runtime", "known_bad_char"),
        ("卵一二三四", "dropped", "too_long_for_runtime"),
        ("卵龘", "dropped", "out_of_charset"),
        ("AA制", "dropped", "mixed_latin"),
        ("T恤", "dropped", "mixed_latin"),
    ]
    assert result.threshold_exceeded
    assert result.report_json.read_text(encoding="utf-8") == (
        golden_root / "report_skips" / "build-report.json"
    ).read_text(encoding="utf-8")
    assert result.report_md.read_text(encoding="utf-8") == (
        golden_root / "report_skips" / "build-report.md"
    ).read_text(encoding="utf-8")
    assert (
        result.ci_dir / "wubi86.ci.daily_spoken.dict.yaml"
    ).read_text(encoding="utf-8") == (
        golden_root / "rime_skips" / "wubi86.ci.daily_spoken.dict.yaml"
    ).read_text(encoding="utf-8")


def test_package_has_no_source_names(
    material_root: Path,
    char_table_path: Path,
    tmp_path: Path,
) -> None:
    result = run_consumer(
        material_root, tmp_path / "consumer", char_table_path
    )

    for path in result.ci_dir.iterdir():
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8").lower()
        assert "fixture" not in text, path.name
