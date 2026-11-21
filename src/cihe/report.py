"""词合构建报告：JSON（机器）+ Markdown（人）。

报告只包含物料类目、计数、跳过词条与原因，不含来源名称、权重或外部词表信息。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from cihe.policy import Reason, Status

EXAMPLE_LIMIT = 20


@dataclass(frozen=True)
class SkipRecord:
    word: str
    disposition: Status
    reason: Reason


@dataclass(frozen=True)
class CategoryBuild:
    material_path: str | None
    total: int
    encoded: int
    runtime_only: int
    dropped: int
    skips: tuple[SkipRecord, ...]

    @property
    def label(self) -> str:
        return self.material_path or "总体"

    @property
    def skip_count(self) -> int:
        return self.runtime_only + self.dropped

    @property
    def skip_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.skip_count / self.total


@dataclass(frozen=True)
class BuildReport:
    overall: CategoryBuild
    categories: tuple[CategoryBuild, ...]
    overall_skip_limit: float
    category_skip_limit: float
    violations: tuple[str, ...]

    @property
    def threshold_exceeded(self) -> bool:
        return bool(self.violations)


def build_report(
    categories: list[CategoryBuild],
    *,
    overall_skip_limit: float,
    category_skip_limit: float,
) -> BuildReport:
    overall = CategoryBuild(
        material_path=None,
        total=sum(item.total for item in categories),
        encoded=sum(item.encoded for item in categories),
        runtime_only=sum(item.runtime_only for item in categories),
        dropped=sum(item.dropped for item in categories),
        skips=tuple(
            skip for item in categories for skip in item.skips
        ),
    )
    violations: list[str] = []
    if overall.skip_rate > overall_skip_limit:
        violations.append("总体")
    for item in categories:
        if item.skip_rate > category_skip_limit:
            violations.append(item.label)
    return BuildReport(
        overall=overall,
        categories=tuple(categories),
        overall_skip_limit=overall_skip_limit,
        category_skip_limit=category_skip_limit,
        violations=tuple(violations),
    )


def _category_payload(item: CategoryBuild) -> dict[str, object]:
    # examples 供人快速查看（前 20 条）；skips 是审计用的完整记录。
    return {
        "label": item.label,
        "material_path": item.material_path,
        "total": item.total,
        "encoded": item.encoded,
        "runtime_only": item.runtime_only,
        "dropped": item.dropped,
        "skip_count": item.skip_count,
        "skip_rate": round(item.skip_rate, 6),
        "examples": [
            asdict(skip) for skip in item.skips[:EXAMPLE_LIMIT]
        ],
        "skips": [asdict(skip) for skip in item.skips],
    }


def _markdown(
    report: BuildReport, *, target_name: str, target_version: str
) -> str:
    lines = [
        "# 构建报告",
        "",
        f"- target：{target_name} {target_version}",
        f"- 总体跳过率阈值：>{report.overall_skip_limit:.2%} 失败",
        f"- 单类目跳过率阈值：>{report.category_skip_limit:.2%} 失败",
        (
            "- 结果：超阈值，构建失败"
            if report.threshold_exceeded
            else "- 结果：未超阈值"
        ),
    ]
    if report.violations:
        lines.append(f"- 超阈值项：{'、'.join(report.violations)}")
    lines.extend(
        [
            "",
            "| 类目 | total | encoded | runtime_only | dropped | skip_rate |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for item in (report.overall, *report.categories):
        lines.append(
            f"| {item.label} | {item.total} | {item.encoded} | "
            f"{item.runtime_only} | {item.dropped} | {item.skip_rate:.4%} |"
        )
    for item in report.categories:
        if not item.skips:
            continue
        lines.extend(
            [
                "",
                f"## {item.label} 跳过记录",
                "",
                "| 词条 | 处置 | 原因 |",
                "| --- | --- | --- |",
            ]
        )
        for skip in item.skips:
            lines.append(
                f"| {skip.word} | {skip.disposition} | {skip.reason} |"
            )
    return "\n".join(lines) + "\n"


def write_build_report(
    output_dir: Path,
    report: BuildReport,
    *,
    target_name: str,
    target_version: str,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "build-report.json"
    markdown_path = output_dir / "build-report.md"
    payload = {
        "schema_version": 1,
        "target": {"name": target_name, "version": target_version},
        "thresholds": {
            "overall": report.overall_skip_limit,
            "category": report.category_skip_limit,
        },
        "threshold_exceeded": report.threshold_exceeded,
        "violations": list(report.violations),
        "overall": _category_payload(report.overall),
        "categories": [
            _category_payload(item) for item in report.categories
        ],
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    markdown_path.write_text(
        _markdown(
            report,
            target_name=target_name,
            target_version=target_version,
        ),
        encoding="utf-8",
        newline="\n",
    )
    return json_path, markdown_path
