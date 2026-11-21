"""物料类目骨架，从 vendored taxonomy 契约读取。

正本：CiMo `contracts/taxonomy.md` 与 `contracts/taxonomy/taxonomy.json`。
词合只读取类目顺序、路径、文件与 slug，不硬编码类目表。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

VENDOR_DIR = (
    Path(__file__).resolve().parents[2]
    / "contracts"
    / "vendor"
    / "taxonomy-v1"
)
TAXONOMY_PATH = VENDOR_DIR / "taxonomy.json"


@dataclass(frozen=True)
class CategorySpec:
    group: str
    name: str
    slug: str
    order: int
    files: tuple[str, ...]

    @property
    def material_path(self) -> str:
        return f"{self.group}/{self.name}"


def _load() -> tuple[dict[str, Any], tuple[CategorySpec, ...]]:
    payload = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
    specs: list[CategorySpec] = []
    for group in payload.get("groups", []):
        group_name = str(group["name"])
        for category in group.get("categories", []):
            files = tuple(str(item["name"]) for item in category["files"])
            specs.append(
                CategorySpec(
                    group=group_name,
                    name=str(category["name"]),
                    slug=str(category["slug"]),
                    order=len(specs),
                    files=files,
                )
            )
    return payload, tuple(specs)


PAYLOAD, CATEGORY_MAPPING = _load()


def validate_taxonomy() -> None:
    if len(CATEGORY_MAPPING) != 33:
        raise ValueError(f"taxonomy 类目数不符：{len(CATEGORY_MAPPING)}")
    if sum(len(spec.files) for spec in CATEGORY_MAPPING) != 73:
        raise ValueError("taxonomy 文件数不符：应为 73")
    paths = [spec.material_path for spec in CATEGORY_MAPPING]
    if len(paths) != len(set(paths)):
        raise ValueError("taxonomy 存在重复的物料目录")
    slugs = [spec.slug for spec in CATEGORY_MAPPING]
    if len(slugs) != len(set(slugs)):
        raise ValueError("taxonomy 存在重复的 slug")
    if [spec.order for spec in CATEGORY_MAPPING] != list(
        range(len(CATEGORY_MAPPING))
    ):
        raise ValueError("taxonomy 类目顺序必须从 0 连续递增")
    for spec in CATEGORY_MAPPING:
        if not spec.files or spec.files[-1] != "其它":
            raise ValueError(f"类目文件必须以 其它 结尾：{spec.material_path}")
        if len(set(spec.files)) != len(spec.files):
            raise ValueError(f"类目文件重复：{spec.material_path}")


def spec_for(material_path: str) -> CategorySpec:
    for spec in CATEGORY_MAPPING:
        if spec.material_path == material_path:
            return spec
    raise KeyError(f"物料类目没有映射：{material_path}")


validate_taxonomy()
