"""写出 rime-wubi 的 Ci 类目词表。

基础项目结构（schema、字表、主表、README、LICENSE）由 `rime-wubi` 仓库维护；
本模块只生成 `wubi86.ci.<slug>.dict.yaml`。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from cihe.categories import CATEGORY_MAPPING, CategorySpec, validate_taxonomy
from cihe.dicts import sort_category_entries, write_dict_yaml
from cihe.encoding import EncodedEntry


@dataclass(frozen=True)
class CiResult:
    ci_dir: Path
    category_dicts: tuple[Path, ...]
    table_names: tuple[str, ...]


def table_name(slug: str) -> str:
    return f"wubi86.ci.{slug}"


def import_order() -> tuple[str, ...]:
    return tuple(table_name(spec.slug) for spec in CATEGORY_MAPPING)


def build_ci_tables(
    ci_dir: Path,
    categories: Sequence[tuple[CategorySpec, Sequence[EncodedEntry]]],
) -> CiResult:
    validate_taxonomy()
    ci_dir.mkdir(parents=True, exist_ok=True)

    category_dicts: list[Path] = []
    table_names: list[str] = []
    for spec, entries in sorted(categories, key=lambda item: item[0].order):
        table = table_name(spec.slug)
        table_names.append(table)
        path = ci_dir / f"{table}.dict.yaml"
        sorted_entries = sort_category_entries(entries)
        write_dict_yaml(
            path,
            table,
            [(entry.text, entry.code) for entry in sorted_entries],
        )
        category_dicts.append(path)

    return CiResult(
        ci_dir=ci_dir,
        category_dicts=tuple(category_dicts),
        table_names=tuple(table_names),
    )
