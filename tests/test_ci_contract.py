from __future__ import annotations

from pathlib import Path

import pytest

from cihe.tracer import run_consumer

TESTS_ROOT = Path(__file__).resolve().parent
CI_FILE = "wubi86.ci.daily_spoken.dict.yaml"


@pytest.fixture(scope="module")
def ci_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    result = run_consumer(
        TESTS_ROOT / "fixtures" / "material",
        tmp_path_factory.mktemp("consumer"),
        TESTS_ROOT / "fixtures" / "char_table" / "wubi86.zi.dict.yaml",
    )
    return result.ci_dir


def test_ci_dir_contains_only_ci_tables(ci_dir: Path) -> None:
    files = {path.name for path in ci_dir.iterdir() if path.is_file()}
    assert files == {CI_FILE}
    assert not list(ci_dir.glob("*.schema.yaml"))
    assert not (ci_dir / "wubi86.dict.yaml").exists()
    assert not (ci_dir / "wubi86.zi.dict.yaml").exists()


def test_ci_matches_golden(
    golden_root: Path, ci_dir: Path
) -> None:
    assert (ci_dir / CI_FILE).read_text(encoding="utf-8") == (
        golden_root / "rime" / CI_FILE
    ).read_text(encoding="utf-8")


def test_ci_header_and_order(ci_dir: Path) -> None:
    text = (ci_dir / CI_FILE).read_text(encoding="utf-8")

    assert "name: wubi86.ci.daily_spoken\n" in text
    assert "sort: original\n" in text
    assert "columns:\n  - text\n  - code\n" in text
    entries = [
        tuple(line.split("\t"))
        for line in text.split("\n...\n", 1)[1].splitlines()
        if line.strip()
    ]
    assert entries == sorted(
        entries,
        key=lambda item: (
            len(item[0]) if len(item[0]) < 5 else 5,
            item[0],
        ),
    )
    assert len({text for text, _code in entries}) == len(entries)
