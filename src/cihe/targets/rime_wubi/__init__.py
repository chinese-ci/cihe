"""rime-wubi 目标适配器：纯词库物料 → 五笔编码 → Ci 类目词表。

只生成 `wubi86.ci.<slug>.dict.yaml`；schema、字表、主表与发布结构由
`rime-wubi` 仓库维护。规范见 CiMo `contracts/targets/rime-wubi.md`。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from cihe.categories import CATEGORY_MAPPING, CategorySpec, spec_for
from cihe.dicts import parse_tsv_entries
from cihe.encoding import (
    ConverterError,
    EncodedEntry,
    EncodingResult,
    encode_words,
)
from cihe.material import MaterialContractError
from cihe.policy import classify_word
from cihe.report import (
    CategoryBuild,
    SkipRecord,
    build_report,
    write_build_report,
)
from cihe.targets.base import (
    EmittedTarget,
    EncodedTarget,
    Encoder,
    MaterialTree,
)
from cihe.targets.rime_wubi.package import (
    CiResult,
    build_ci_tables,
    table_name,
)

TARGET_NAME = "rime-wubi"
TARGET_VERSION = "1.0.0"


def _category_words(
    spec: CategorySpec, files: dict[str, list[str]]
) -> list[str]:
    unknown = sorted(set(files) - set(spec.files))
    if unknown:
        raise MaterialContractError(
            f"物料文件未在 taxonomy 中声明：{spec.material_path}："
            f"{'、'.join(unknown)}"
        )
    missing = [
        file_name for file_name in spec.files if file_name not in files
    ]
    if missing:
        raise MaterialContractError(
            f"物料缺少 taxonomy 声明的类目文件：{spec.material_path}："
            f"{'、'.join(missing)}"
        )
    words = [
        word for file_name in spec.files for word in files[file_name]
    ]
    if len(set(words)) != len(words):
        raise MaterialContractError(
            f"物料类目内有重复词条：{spec.material_path}"
        )
    return words


def _validate_encoding(
    words: list[str], encoded: EncodingResult
) -> dict[str, EncodedEntry]:
    entries: dict[str, EncodedEntry] = {}
    word_set = set(words)
    for entry in encoded.entries:
        if entry.text not in word_set:
            raise ConverterError(f"编码器输出了物料之外的词条：{entry.text}")
        if entry.text in entries:
            raise ConverterError(f"编码器输出了重复词条：{entry.text}")
        entries[entry.text] = entry
    expected_skipped = tuple(
        word for word in words if word not in entries
    )
    if expected_skipped != encoded.skipped:
        raise ConverterError("编码器跳过列表与输出不一致")
    if encoded.stats.imported != len(words):
        raise ConverterError(
            f"编码器导入条数不一致：期望 {len(words)}，"
            f"实际 {encoded.stats.imported}"
        )
    if encoded.stats.exported != len(encoded.entries):
        raise ConverterError("编码器导出计数与词条数不一致")
    if encoded.stats.filtered != len(encoded.skipped):
        raise ConverterError("编码器过滤计数与跳过数不一致")
    return entries


class RimeWubiTarget:
    name = TARGET_NAME
    version = TARGET_VERSION

    def encode(
        self,
        materials: MaterialTree,
        char_entries: Sequence[tuple[str, str]],
        *,
        image: str,
        encoder: Encoder | None,
        overall_skip_limit: float,
        category_skip_limit: float,
    ) -> EncodedTarget:
        charset = {text for text, _code in char_entries}
        encode = encoder or (lambda words: encode_words(words, image))

        prepared: list[tuple[CategorySpec, list[str]]] = []
        for material_path, files in materials.items():
            try:
                spec = spec_for(material_path)
            except KeyError as error:
                raise MaterialContractError(str(error)) from error
            prepared.append((spec, _category_words(spec, files)))
        prepared.sort(key=lambda item: item[0].order)

        all_words = [
            word for _spec, words in prepared for word in words
        ]
        if len(set(all_words)) != len(all_words):
            raise MaterialContractError("物料跨类目出现重复词条")
        encoded = encode(all_words)
        entries_by_word = _validate_encoding(all_words, encoded)

        category_entries: dict[str, tuple[EncodedEntry, ...]] = {}
        categories: list[CategoryBuild] = []
        for spec, words in prepared:
            written: list[EncodedEntry] = []
            skips: list[SkipRecord] = []
            runtime_only = 0
            dropped = 0
            for word in words:
                has_code = word in entries_by_word
                disposition = classify_word(
                    word, has_code=has_code, charset=charset
                )
                if disposition.status == "encoded":
                    written.append(entries_by_word[word])
                    continue
                if disposition.reason is None:
                    raise ConverterError(f"跳过词条缺少原因：{word}")
                skips.append(
                    SkipRecord(
                        word=word,
                        disposition=disposition.status,
                        reason=disposition.reason,
                    )
                )
                if disposition.status == "runtime":
                    runtime_only += 1
                else:
                    dropped += 1

            category_entries[spec.slug] = tuple(written)
            categories.append(
                CategoryBuild(
                    material_path=spec.material_path,
                    total=len(words),
                    encoded=len(written),
                    runtime_only=runtime_only,
                    dropped=dropped,
                    skips=tuple(skips),
                )
            )

        report = build_report(
            categories,
            overall_skip_limit=overall_skip_limit,
            category_skip_limit=category_skip_limit,
        )
        return EncodedTarget(
            category_entries=category_entries,
            converter=encoded.stats,
            report=report,
        )

    def emit(
        self, encoded: EncodedTarget, output_dir: Path
    ) -> EmittedTarget:
        categories = [
            (spec, encoded.category_entries[spec.slug])
            for spec in CATEGORY_MAPPING
            if spec.slug in encoded.category_entries
        ]
        ci: CiResult = build_ci_tables(output_dir / "ci", categories)
        report_json, report_md = write_build_report(
            output_dir,
            encoded.report,
            target_name=self.name,
            target_version=self.version,
        )
        files = tuple(sorted(ci.ci_dir.iterdir()))
        return EmittedTarget(
            artifact_dir=ci.ci_dir,
            files=files,
            report_json=report_json,
            report_md=report_md,
        )

    def verify(
        self, artifact_dir: Path, report_path: Path
    ) -> dict[str, Any]:
        errors: list[str] = []
        expected = {
            f"{table_name(spec.slug)}.dict.yaml": spec
            for spec in CATEGORY_MAPPING
        }
        actual = {
            path.name
            for path in artifact_dir.glob("*.dict.yaml")
            if path.is_file()
        }
        missing = sorted(set(expected) - actual)
        extra = sorted(actual - set(expected))
        if missing:
            errors.append(f"Ci 词表缺少文件：{'、'.join(missing)}")
        if extra:
            errors.append(f"Ci 目录存在契约外文件：{'、'.join(extra)}")

        total_entries = 0
        for name, spec in sorted(expected.items()):
            path = artifact_dir / name
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            if f"name: {table_name(spec.slug)}\n" not in text:
                errors.append(f"{name} 的 name 不符")
            if "sort: original\n" not in text:
                errors.append(f"{name} 缺少 sort: original")
            if "columns:\n  - text\n  - code\n" not in text:
                errors.append(f"{name} 的 columns 不符")
            marker = "\n...\n"
            if marker not in text:
                errors.append(f"{name} 缺少文档结束标记")
                continue
            try:
                entries = parse_tsv_entries(
                    text.split(marker, 1)[1].splitlines(), name
                )
            except ValueError as error:
                errors.append(str(error))
                continue
            total_entries += len(entries)
            expected_order = sorted(
                entries,
                key=lambda item: (
                    len(item[0]) if len(item[0]) < 5 else 5,
                    item[0],
                ),
            )
            if entries != expected_order:
                errors.append(f"{name} 未按契约顺序排列")
            texts = [item[0] for item in entries]
            if len(set(texts)) != len(texts):
                errors.append(f"{name} 存在重复词条")

        payload: dict[str, Any] = {
            "schema_version": 1,
            "ok": not errors,
            "artifact": str(artifact_dir),
            "target": {"name": self.name, "version": self.version},
            "files": len(actual),
            "entries": total_entries,
            "errors": errors,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return payload
