"""跳过与不可信词条的处置策略（工单 05 / 10）。

处置顺序：

1. 生成成功且不含 13 个已知差异字 → 写入词表。
2. 生成跳过，或含已知差异字（生成码不可信）：
   - 含拉丁字母 → 丢弃（`mixed_latin`，运行时造词无法处理拉丁）；
   - 有字不在方案字表 → 丢弃（`out_of_charset`）；
   - 词长 > 4 → 丢弃（`too_long_for_runtime`）；
   - 含已知差异字 → 不写词表，交给运行时 encoder（`known_bad_char`）；
   - 其余跳过 → 不写词表，交给运行时 encoder（`encoder_error`）。
3. 不写无码词条；不自研编码器；不回退外部词码。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

KNOWN_BAD_CHARS = frozenset("卵囱墼孳枰栻盥窗缌蔻迎酿靥")

Status = Literal["encoded", "runtime", "dropped"]
Reason = Literal[
    "mixed_latin",
    "out_of_charset",
    "too_long_for_runtime",
    "known_bad_char",
    "encoder_error",
]


@dataclass(frozen=True)
class Disposition:
    word: str
    status: Status
    reason: Reason | None


def _has_ascii_letter(word: str) -> bool:
    # 物料契约只允许 ASCII 字母/数字；全角拉丁在词修阶段已归一。
    return any(
        character.isascii() and character.isalpha()
        for character in word
    )


def _has_known_bad_char(word: str) -> bool:
    return any(character in KNOWN_BAD_CHARS for character in word)


def classify_word(
    word: str,
    *,
    has_code: bool,
    charset: frozenset[str] | set[str],
) -> Disposition:
    untrusted = _has_known_bad_char(word)
    if has_code and not untrusted:
        return Disposition(word=word, status="encoded", reason=None)

    if _has_ascii_letter(word):
        return Disposition(word=word, status="dropped", reason="mixed_latin")
    if any(character not in charset for character in word):
        return Disposition(
            word=word, status="dropped", reason="out_of_charset"
        )
    if len(word) > 4:
        return Disposition(
            word=word, status="dropped", reason="too_long_for_runtime"
        )
    if untrusted:
        return Disposition(
            word=word, status="runtime", reason="known_bad_char"
        )
    return Disposition(word=word, status="runtime", reason="encoder_error")
