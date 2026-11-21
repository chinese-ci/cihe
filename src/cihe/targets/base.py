"""目标适配器接口：encode → emit → verify。

适配器只消费纯词库物料、taxonomy 与可选字表，不读取来源语料或来源元数据。
具体 target 的产物细节由各自契约规定。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence

from cihe.encoding import ConverterStats, EncodedEntry, EncodingResult
from cihe.report import BuildReport

MaterialTree = dict[str, dict[str, list[str]]]
Encoder = Callable[[Sequence[str]], EncodingResult]


@dataclass(frozen=True)
class EncodedTarget:
    """编码阶段的结果：按类目分组的编码条目、编码统计与构建报告。"""

    category_entries: dict[str, tuple[EncodedEntry, ...]]
    converter: ConverterStats
    report: BuildReport


@dataclass(frozen=True)
class EmittedTarget:
    """落盘阶段的结果：产物目录、文件集合与报告路径。"""

    artifact_dir: Path
    files: tuple[Path, ...]
    report_json: Path
    report_md: Path


class TargetAdapter(Protocol):
    name: str
    version: str

    def encode(
        self,
        materials: MaterialTree,
        char_entries: Sequence[tuple[str, str]],
        *,
        image: str,
        encoder: Encoder | None,
        overall_skip_limit: float,
        category_skip_limit: float,
    ) -> EncodedTarget: ...

    def emit(
        self, encoded: EncodedTarget, output_dir: Path
    ) -> EmittedTarget: ...

    def verify(
        self, artifact_dir: Path, report_path: Path
    ) -> dict[str, Any]: ...
