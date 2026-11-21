from __future__ import annotations

import json
from pathlib import Path

from cihe.dicts import read_char_table
from cihe.encoding import ConverterStats, EncodedEntry, EncodingResult
from cihe.tracer import run_consumer


class FakeEncoder:
    def __init__(self, codes: dict[str, str]) -> None:
        self.codes = codes

    def __call__(self, words):
        entries = tuple(
            EncodedEntry(text=word, code=self.codes[word])
            for word in words
            if word in self.codes
        )
        skipped = tuple(word for word in words if word not in self.codes)
        return EncodingResult(
            entries=entries,
            stats=ConverterStats(
                imported=len(words),
                exported=len(entries),
                filtered=len(skipped),
            ),
            skipped=skipped,
        )


def write_char_table(path: Path, characters: str) -> None:
    lines = [
        "# test char table",
        "---",
        "name: wubi86.zi",
        'version: "test"',
        "sort: original",
        "columns:",
        "  - text",
        "  - code",
        "...",
    ]
    lines.extend(f"{character}\ta" for character in characters)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_category(
    root: Path, category: str, words: list[str]
) -> None:
    from cihe.categories import spec_for

    spec = spec_for(category)
    for name in spec.files:
        target = root.joinpath(*category.split("/"), f"{name}.txt")
        target.parent.mkdir(parents=True, exist_ok=True)
        text = "\n".join(words) + "\n" if name == "其它" and words else ""
        target.write_text(text, encoding="utf-8", newline="\n")


def build(
    tmp_path: Path,
    categories: dict[str, list[str]],
    chars: str,
    codes: dict[str, str],
    *,
    overall_skip_limit: float = 0.005,
    category_skip_limit: float = 0.02,
):
    material = tmp_path / "material"
    for category, words in categories.items():
        write_category(material, category, words)
    char_table = tmp_path / "char_table.yaml"
    write_char_table(char_table, "".join(dict.fromkeys(chars)))
    return run_consumer(
        material,
        tmp_path / "out",
        char_table,
        encoder=FakeEncoder(codes),
        overall_skip_limit=overall_skip_limit,
        category_skip_limit=category_skip_limit,
    )


def test_dispositions_counts_and_package_exclude_unwritten_words(
    tmp_path: Path,
) -> None:
    result = build(
        tmp_path,
        {
            "下里巴人/日常口语": [
                "你好",
                "卵石",
                "AA制",
                "一二三四五",
                "龘",
                "朋友",
            ]
        },
        "你好卵石一二三四五朋友",
        {"你好": "wqvb", "卵石": "lhng"},
    )

    category = result.report.categories[0]
    assert category.total == 6
    assert category.encoded == 1
    assert category.runtime_only == 2
    assert category.dropped == 3
    assert category.skip_rate == 5 / 6
    assert [(skip.word, skip.disposition, skip.reason) for skip in category.skips] == [
        ("卵石", "runtime", "known_bad_char"),
        ("AA制", "dropped", "mixed_latin"),
        ("一二三四五", "dropped", "too_long_for_runtime"),
        ("龘", "dropped", "out_of_charset"),
        ("朋友", "runtime", "encoder_error"),
    ]

    assert [entry.text for entry in result.category_entries["daily_spoken"]] == [
        "你好"
    ]
    table = read_char_table(
        result.ci_dir / "wubi86.ci.daily_spoken.dict.yaml"
    )
    assert [text for text, _code in table] == ["你好"]

    assert result.threshold_exceeded
    report = json.loads(result.report_json.read_text(encoding="utf-8"))
    assert report["overall"]["total"] == 6
    assert report["overall"]["encoded"] == 1
    assert report["overall"]["runtime_only"] == 2
    assert report["overall"]["dropped"] == 3
    assert report["threshold_exceeded"]
    assert "总体" in report["violations"]
    for forbidden in ("weight", "frequency", "fixture"):
        assert forbidden not in result.report_json.read_text(encoding="utf-8").lower()
        assert forbidden not in result.report_md.read_text(encoding="utf-8").lower()


def test_no_threshold_failure_when_skip_rate_is_low(tmp_path: Path) -> None:
    words = [f"阿{chr(0x4E00 + index)}" for index in range(999)]
    words.append("朋友")
    codes = {word: "a" for word in words if word != "朋友"}

    result = build(
        tmp_path,
        {"下里巴人/日常口语": words},
        "".join(words),
        codes,
    )

    assert result.report.overall.total == 1000
    assert result.report.overall.skip_count == 1
    assert result.report.overall.skip_rate == 0.001
    assert not result.threshold_exceeded
    assert result.report.violations == ()
    assert result.report.categories[0].runtime_only == 1


def test_category_threshold_fails_even_when_overall_is_below(tmp_path: Path) -> None:
    many = [f"阿{chr(0x4E00 + index)}" for index in range(1000)]
    few = [
        "你好",
        "朋友",
        *[f"阿{chr(0x4E00 + 1000 + index)}" for index in range(8)],
    ]
    codes = {word: "a" for word in [*many, *few] if word != "朋友"}

    result = build(
        tmp_path,
        {
            "下里巴人/日常口语": few,
            "下里巴人/生活服务": many,
        },
        "".join(dict.fromkeys([*many, *few])),
        codes,
    )

    assert result.report.overall.skip_rate == 1 / 1010
    assert result.report.overall.skip_rate < 0.005
    assert result.threshold_exceeded
    assert result.report.violations == ("下里巴人/日常口语",)


def test_thresholds_are_configurable(tmp_path: Path) -> None:
    words = [f"阿{chr(0x4E00 + index)}" for index in range(999)]
    words.append("朋友")
    codes = {word: "a" for word in words if word != "朋友"}

    result = build(
        tmp_path,
        {"下里巴人/日常口语": words},
        "".join(words),
        codes,
        overall_skip_limit=0.0005,
    )

    assert result.threshold_exceeded
    assert "总体" in result.report.violations


def test_examples_are_capped_at_twenty(tmp_path: Path) -> None:
    words = [f"朋{chr(0x4E00 + index)}" for index in range(25)]

    result = build(
        tmp_path,
        {"下里巴人/日常口语": words},
        "".join(words),
        {},
    )

    category = result.report.categories[0]
    assert len(category.skips) == 25
    payload = json.loads(result.report_json.read_text(encoding="utf-8"))
    assert len(payload["categories"][0]["examples"]) == 20
    assert len(payload["categories"][0]["skips"]) == 25


def test_category_table_sorts_by_length_then_codepoint(tmp_path: Path) -> None:
    words = ["一二三四五", "谢谢", "早上好", "一二三四", "你好"]
    codes = {word: "a" for word in words}

    result = build(
        tmp_path,
        {"下里巴人/日常口语": words},
        "".join(words),
        codes,
    )

    table = read_char_table(
        result.ci_dir / "wubi86.ci.daily_spoken.dict.yaml"
    )
    assert [text for text, _code in table] == [
        "你好",
        "谢谢",
        "早上好",
        "一二三四",
        "一二三四五",
    ]
