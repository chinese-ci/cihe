"""词合调度：纯词库物料 + 字表 → target 适配器 → 产物与构建报告。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cihe.dicts import read_char_table
from cihe.encoding import DEFAULT_IMAGE, ConverterStats, EncodedEntry
from cihe.material import read_material
from cihe.report import BuildReport
from cihe.targets import DEFAULT_TARGET, get_target
from cihe.targets.base import Encoder

# 工单 10 的默认阈值。
DEFAULT_OVERALL_SKIP_LIMIT = 0.005
DEFAULT_CATEGORY_SKIP_LIMIT = 0.02


@dataclass(frozen=True)
class ConsumerResult:
    ci_dir: Path
    category_entries: dict[str, tuple[EncodedEntry, ...]]
    converter: ConverterStats
    report: BuildReport
    report_json: Path
    report_md: Path
    threshold_exceeded: bool
    target: str
    target_version: str


def run_consumer(
    material_dir: Path,
    output_dir: Path,
    char_table_path: Path,
    *,
    target: str = DEFAULT_TARGET,
    image: str = DEFAULT_IMAGE,
    encoder: Encoder | None = None,
    overall_skip_limit: float = DEFAULT_OVERALL_SKIP_LIMIT,
    category_skip_limit: float = DEFAULT_CATEGORY_SKIP_LIMIT,
) -> ConsumerResult:
    materials = read_material(material_dir)
    char_entries = read_char_table(char_table_path)
    if not char_entries:
        raise ValueError(f"字表为空：{char_table_path}")
    if len(set(char_entries)) != len(char_entries):
        raise ValueError(f"字表有重复条目：{char_table_path}")

    adapter = get_target(target)
    encoded = adapter.encode(
        materials,
        char_entries,
        image=image,
        encoder=encoder,
        overall_skip_limit=overall_skip_limit,
        category_skip_limit=category_skip_limit,
    )
    emitted = adapter.emit(encoded, output_dir)

    return ConsumerResult(
        ci_dir=emitted.artifact_dir,
        category_entries=encoded.category_entries,
        converter=encoded.converter,
        report=encoded.report,
        report_json=emitted.report_json,
        report_md=emitted.report_md,
        threshold_exceeded=encoded.report.threshold_exceeded,
        target=adapter.name,
        target_version=adapter.version,
    )
