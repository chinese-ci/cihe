from __future__ import annotations

from cihe.encoding import encode_words


def test_real_converter_skips_mixed_latin_words_and_matches_formats() -> None:
    result = encode_words(["你好", "AA制", "T恤"])

    assert [entry.text for entry in result.entries] == ["你好"]
    assert result.entries[0].code == "wqvb"
    assert result.skipped == ("AA制", "T恤")
    assert result.stats.imported == 3
    assert result.stats.exported == 1
    assert result.stats.filtered == 2


def test_real_converter_keeps_input_order_for_encoded_words() -> None:
    result = encode_words(["上班", "你好", "谢谢"])

    assert [entry.text for entry in result.entries] == ["上班", "你好", "谢谢"]
    assert result.skipped == ()
    assert result.stats.filtered == 0


def test_real_converter_skips_the_five_mixed_words() -> None:
    words = ["AA制", "卡拉OK", "T型台", "T恤", "U盘"]

    result = encode_words(words)

    assert result.entries == ()
    assert set(result.skipped) == set(words)
    assert result.stats.imported == 5
    assert result.stats.exported == 0
    assert result.stats.filtered == 5
