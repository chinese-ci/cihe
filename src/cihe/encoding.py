"""通过真实 imewlconverter v3.6.0 Docker 生成五笔 86 编码。

同时跑 Rime 与 wb86 两种输出并逐条比对：Rime 是 UTF-8 无 BOM/LF 的
`词<TAB>码<TAB>rank`，wb86 是 UTF-16LE BOM/CRLF 的 `码<空格>词`。rank 丢弃，
两种格式的编码必须一致。被编码器跳过的词由输入与输出的差集确定，交给词合
的处置策略决定 runtime 还是 dropped。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

DEFAULT_IMAGE = os.environ.get(
    "CIHE_IMEWLCONVERTER_IMAGE", "cicai/imewlconverter:3.6.0"
)

@dataclass(frozen=True)
class _OutputFormat:
    format: str
    filename: str
    extra: tuple[str, ...] = ()


_RIME = _OutputFormat("rime", "rime.txt", ("-t", "wubi"))
_WB86 = _OutputFormat("wb86", "wb86.txt")


class ConverterError(RuntimeError):
    """编码器不可用或输出不符合契约。"""


@dataclass(frozen=True)
class ConverterStats:
    imported: int
    exported: int
    filtered: int


@dataclass(frozen=True)
class EncodedEntry:
    text: str
    code: str


@dataclass(frozen=True)
class EncodingResult:
    entries: tuple[EncodedEntry, ...]
    stats: ConverterStats
    skipped: tuple[str, ...]


def _run_docker(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    if shutil.which("docker") is None:
        raise ConverterError("找不到 docker")
    return subprocess.run(
        ["docker", *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


def _ensure_image(image: str) -> None:
    result = _run_docker(["image", "inspect", image])
    if result.returncode != 0:
        raise ConverterError(
            f"编码器镜像不存在：{image}\n"
            "先运行：uv run python tools/build_converter_image.py"
        )


def _converter_payload(
    result: subprocess.CompletedProcess[str], output_format: str
) -> dict[str, object]:
    if result.returncode != 0:
        raise ConverterError(
            f"imewlconverter（{output_format}）失败（退出码 {result.returncode}）：\n"
            f"{result.stderr.strip()}"
        )
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ConverterError(
            f"imewlconverter（{output_format}）的 JSON 输出无法解析："
            f"{result.stdout!r}"
        ) from error
    if not report.get("ok", False):
        raise ConverterError(
            f"imewlconverter（{output_format}）报告失败：{report}"
        )
    payload = report.get("result")
    if not isinstance(payload, dict):
        raise ConverterError(
            f"imewlconverter（{output_format}）缺少 result：{report}"
        )
    errors = payload.get("errors", [])
    if errors:
        raise ConverterError(
            f"imewlconverter（{output_format}）报告错误：{errors}"
        )
    return payload


def _run_conversion(
    work_dir: Path,
    image: str,
    output: _OutputFormat,
) -> dict[str, object]:
    arguments = [
        "run",
        "--rm",
        "-v",
        f"{work_dir}:/work",
        image,
        "-i",
        "word",
        "-o",
        output.format,
        *output.extra,
        "-O",
        f"/work/{output.filename}",
        "--json",
        "/work/words.txt",
    ]
    return _converter_payload(_run_docker(arguments), output.format)


def _parse_rime_output(raw: bytes, exported: int) -> list[EncodedEntry]:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ConverterError("Rime 输出不应带 BOM")
    if b"\r" in raw:
        raise ConverterError("Rime 输出不应包含 CR")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ConverterError("Rime 输出不是 UTF-8") from error
    lines = text.splitlines()
    if len(lines) != exported:
        raise ConverterError(
            f"Rime 导出条数不一致：JSON {exported}，文件 {len(lines)}"
        )
    entries: list[EncodedEntry] = []
    seen: set[str] = set()
    for line in lines:
        columns = line.split("\t")
        if len(columns) != 3:
            raise ConverterError(f"Rime 输出不是词-码-rank：{line!r}")
        word, code, _rank = columns
        if not word or not code:
            raise ConverterError(f"Rime 输出有空字段：{line!r}")
        if word in seen:
            raise ConverterError(f"Rime 输出有重复词条：{word}")
        seen.add(word)
        entries.append(EncodedEntry(text=word, code=code))
    return entries


def _parse_wb86_output(raw: bytes, exported: int) -> dict[str, str]:
    if not raw.startswith(b"\xff\xfe"):
        raise ConverterError("wb86 输出缺少 UTF-16LE BOM")
    try:
        text = raw[2:].decode("utf-16-le")
    except UnicodeDecodeError as error:
        raise ConverterError("wb86 输出不是 UTF-16LE") from error
    remainder = text.replace("\r\n", "")
    if "\r" in remainder or "\n" in remainder:
        raise ConverterError("wb86 输出必须使用 CRLF")
    lines = text.split("\r\n")
    if lines and lines[-1] == "":
        lines.pop()
    if len(lines) != exported:
        raise ConverterError(
            f"wb86 导出条数不一致：JSON {exported}，文件 {len(lines)}"
        )
    mapping: dict[str, str] = {}
    for line in lines:
        columns = line.split(" ")
        if len(columns) != 2 or not all(columns):
            raise ConverterError(f"wb86 输出不是码-空格-词：{line!r}")
        code, word = columns
        if word in mapping:
            raise ConverterError(f"wb86 输出有重复词条：{word}")
        mapping[word] = code
    return mapping


def _payload_counts(payload: dict[str, object]) -> tuple[int, int, int]:
    try:
        return (
            int(str(payload["imported"])),
            int(str(payload["exported"])),
            int(str(payload["filtered"])),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ConverterError(f"imewlconverter 计数字段不完整：{payload}") from error


def encode_words(
    words: Sequence[str], image: str = DEFAULT_IMAGE
) -> EncodingResult:
    word_list = list(words)
    if len(set(word_list)) != len(word_list):
        raise ConverterError("输入词条有重复，词合要求去重后的物料")
    if not word_list:
        return EncodingResult(
            entries=(),
            stats=ConverterStats(imported=0, exported=0, filtered=0),
            skipped=(),
        )

    _ensure_image(image)
    with tempfile.TemporaryDirectory(prefix="cihe-encode-") as temporary:
        work_dir = Path(temporary)
        (work_dir / "words.txt").write_text(
            "\n".join(word_list) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        rime_payload = _run_conversion(work_dir, image, _RIME)
        wb86_payload = _run_conversion(work_dir, image, _WB86)

        imported, exported, filtered = _payload_counts(rime_payload)
        if imported != len(word_list):
            raise ConverterError(
                f"输入条数不一致：期望 {len(word_list)}，实际 {imported}"
            )
        if _payload_counts(wb86_payload) != (imported, exported, filtered):
            raise ConverterError("Rime 与 wb86 的导入/导出/过滤计数不一致")

        rime_path = work_dir / _RIME.filename
        wb86_path = work_dir / _WB86.filename
        if not rime_path.is_file() or not wb86_path.is_file():
            raise ConverterError("imewlconverter 没有生成两种输出文件")

        rime_entries = _parse_rime_output(rime_path.read_bytes(), exported)
        wb86_codes = _parse_wb86_output(wb86_path.read_bytes(), exported)
        rime_codes = {entry.text: entry.code for entry in rime_entries}
        if rime_codes != wb86_codes:
            raise ConverterError("Rime 与 wb86 的编码不一致")

        skipped = tuple(
            word for word in word_list if word not in rime_codes
        )
        if len(skipped) != filtered:
            raise ConverterError(
                f"跳过条数不一致：JSON {filtered}，差集 {len(skipped)}"
            )
        entries = tuple(
            EncodedEntry(text=word, code=rime_codes[word])
            for word in word_list
            if word in rime_codes
        )
        return EncodingResult(
            entries=entries,
            stats=ConverterStats(
                imported=imported, exported=exported, filtered=filtered
            ),
            skipped=skipped,
        )
