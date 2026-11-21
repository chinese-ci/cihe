"""纯词库物料的读取侧契约，与生产者实现保持独立。

物料目录固定为 `组/一级类目/类目.txt`。
组是 `阳春白雪` 或 `下里巴人`，目录是一级类目，文件名即类目。
读取结果按一级类目分组，组内保留各文件的词条，`其它` 最后。
"""

from __future__ import annotations

from pathlib import Path


class MaterialContractError(ValueError):
    """物料目录不符合公开契约。"""


def _file_order_key(name: str) -> tuple[bool, str]:
    return (name == "其它", name)


def _read_lines(path: Path, relative: str) -> list[str]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise MaterialContractError(f"物料带 BOM：{relative}")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise MaterialContractError(f"物料不是 UTF-8：{relative}") from error
    if "\r" in text:
        raise MaterialContractError(f"物料含 CR：{relative}")
    if "\t" in text:
        raise MaterialContractError(f"物料含制表符：{relative}")
    lines = text.splitlines()
    for line in lines:
        if not line or line.strip() != line:
            raise MaterialContractError(f"物料行不符合契约：{relative}: {line!r}")
    return lines


def read_material(root: Path) -> dict[str, dict[str, list[str]]]:
    if not root.is_dir():
        raise MaterialContractError(f"物料目录不存在：{root}")

    files_by_category: dict[str, dict[str, list[str]]] = {}
    for path in sorted(root.rglob("*.txt")):
        relative = path.relative_to(root)
        if len(relative.parts) != 3:
            raise MaterialContractError(
                f"物料文件必须位于 组/一级类目/类目.txt：{relative.as_posix()}"
            )
        category = f"{relative.parts[0]}/{relative.parts[1]}"
        file_name = path.stem
        files_by_category.setdefault(category, {})[file_name] = _read_lines(
            path, relative.as_posix()
        )

    if not files_by_category:
        raise MaterialContractError(f"物料目录为空：{root}")

    materials: dict[str, dict[str, list[str]]] = {}
    for category, files in sorted(files_by_category.items()):
        materials[category] = {
            name: files[name]
            for name in sorted(files, key=_file_order_key)
        }
    return materials
