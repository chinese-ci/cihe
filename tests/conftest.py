from __future__ import annotations

from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).resolve().parent


@pytest.fixture
def golden_root() -> Path:
    return TESTS_ROOT / "golden"


@pytest.fixture
def material_root() -> Path:
    return TESTS_ROOT / "fixtures" / "material"


@pytest.fixture
def skip_material_root() -> Path:
    return TESTS_ROOT / "fixtures" / "material_skips"


@pytest.fixture
def char_table_path() -> Path:
    return TESTS_ROOT / "fixtures" / "char_table" / "wubi86.zi.dict.yaml"
