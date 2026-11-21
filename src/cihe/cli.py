"""词合命令行：物料 → Ci 词表 + 构建报告。

退出码：0 未超阈值；2 超阈值；1 配置/输入错误。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import NoReturn, Sequence

from cihe.encoding import DEFAULT_IMAGE, ConverterError
from cihe.material import MaterialContractError
from cihe.targets import DEFAULT_TARGET, available_targets
from cihe.tracer import (
    DEFAULT_CATEGORY_SKIP_LIMIT,
    DEFAULT_OVERALL_SKIP_LIMIT,
    run_consumer,
)

ROOT = Path(__file__).resolve().parent.parent.parent


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        # argparse 默认以 2 退出，会和“超阈值”混淆；配置错误统一由 main 返回 1。
        raise ValueError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(description=__doc__)
    parser.add_argument(
        "--material",
        type=Path,
        required=True,
        help="纯词库物料目录",
    )
    parser.add_argument(
        "--char-table",
        type=Path,
        default=ROOT / "var" / "char_table" / "wubi86.zi.dict.yaml",
        help="方案字表（来自 rime-wubi 基础项目，用于跳过分类）",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=ROOT / "var" / "consumer",
        help="运行产物目录（ci/ 与 build-report）",
    )
    parser.add_argument(
        "--target",
        default=DEFAULT_TARGET,
        choices=available_targets(),
        help=f"目标适配器，默认 {DEFAULT_TARGET}",
    )
    parser.add_argument(
        "--image",
        default=DEFAULT_IMAGE,
        help="imewlconverter Docker 镜像",
    )
    parser.add_argument(
        "--overall-skip-limit",
        type=float,
        default=DEFAULT_OVERALL_SKIP_LIMIT,
        help=f"总体跳过率阈值，默认 {DEFAULT_OVERALL_SKIP_LIMIT}",
    )
    parser.add_argument(
        "--category-skip-limit",
        type=float,
        default=DEFAULT_CATEGORY_SKIP_LIMIT,
        help=f"单类目跳过率阈值，默认 {DEFAULT_CATEGORY_SKIP_LIMIT}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        arguments = _parser().parse_args(argv)
        result = run_consumer(
            arguments.material,
            arguments.work_dir,
            arguments.char_table,
            target=arguments.target,
            image=arguments.image,
            overall_skip_limit=arguments.overall_skip_limit,
            category_skip_limit=arguments.category_skip_limit,
        )
    except (
        MaterialContractError,
        ConverterError,
        OSError,
        ValueError,
    ) as error:
        print(f"构建失败：{error}", file=sys.stderr)
        return 1

    overall = result.report.overall
    print(f"target：{result.target} {result.target_version}")
    print(f"Ci 词表：{result.ci_dir}")
    print(f"构建报告：{result.report_json}")
    print(
        f"总体：total={overall.total} encoded={overall.encoded} "
        f"runtime_only={overall.runtime_only} dropped={overall.dropped} "
        f"skip_rate={overall.skip_rate:.4%}"
    )
    if result.threshold_exceeded:
        print(
            f"超阈值：{'、'.join(result.report.violations)}",
            file=sys.stderr,
        )
        return 2
    return 0
