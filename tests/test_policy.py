from __future__ import annotations

import pytest

from cihe.policy import KNOWN_BAD_CHARS, classify_word

CHARSET = frozenset("你好卵石一二三四五朋友龘")


def test_encoded_word_without_known_bad_char_is_written() -> None:
    result = classify_word("你好", has_code=True, charset=CHARSET)

    assert result.status == "encoded"
    assert result.reason is None


def test_skipped_mixed_latin_is_dropped() -> None:
    result = classify_word("AA制", has_code=False, charset=CHARSET)

    assert result.status == "dropped"
    assert result.reason == "mixed_latin"


def test_skipped_out_of_charset_is_dropped() -> None:
    result = classify_word("龘", has_code=False, charset=frozenset("你"))

    assert result.status == "dropped"
    assert result.reason == "out_of_charset"


def test_skipped_too_long_is_dropped() -> None:
    result = classify_word("一二三四五", has_code=False, charset=CHARSET)

    assert result.status == "dropped"
    assert result.reason == "too_long_for_runtime"


def test_untrusted_known_bad_char_goes_runtime() -> None:
    result = classify_word("卵石", has_code=True, charset=CHARSET)

    assert result.status == "runtime"
    assert result.reason == "known_bad_char"


def test_skipped_known_bad_char_goes_runtime() -> None:
    result = classify_word("卵石", has_code=False, charset=CHARSET)

    assert result.status == "runtime"
    assert result.reason == "known_bad_char"


def test_unknown_skip_goes_runtime_as_encoder_error() -> None:
    result = classify_word("朋友", has_code=False, charset=CHARSET)

    assert result.status == "runtime"
    assert result.reason == "encoder_error"


@pytest.mark.parametrize(
    ("word", "has_code", "charset", "reason"),
    [
        ("卵A", False, CHARSET, "mixed_latin"),
        (
            "卵龘",
            False,
            frozenset("你好卵石一二三四五朋友"),
            "out_of_charset",
        ),
        ("卵一二三四", False, CHARSET, "too_long_for_runtime"),
    ],
)
def test_reason_order_follows_spec(
    word: str, has_code: bool, charset: frozenset[str], reason: str
) -> None:
    result = classify_word(word, has_code=has_code, charset=charset)

    assert result.status == "dropped"
    assert result.reason == reason


def test_encoded_word_outside_charset_still_written() -> None:
    result = classify_word("龘", has_code=True, charset=frozenset("你"))

    assert result.status == "encoded"


def test_known_bad_char_set_matches_spec() -> None:
    assert KNOWN_BAD_CHARS == frozenset("卵囱墼孳枰栻盥窗缌蔻迎酿靥")
    assert len(KNOWN_BAD_CHARS) == 13


@pytest.mark.parametrize(
    "word", ["AA制", "卡拉OK", "T型台", "T恤", "U盘"]
)
def test_five_mixed_words_are_dropped_as_mixed_latin(word: str) -> None:
    result = classify_word(word, has_code=False, charset=CHARSET)

    assert result.status == "dropped"
    assert result.reason == "mixed_latin"
