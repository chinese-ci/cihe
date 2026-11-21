from __future__ import annotations

import json
from pathlib import Path

import pytest

from cihe.categories import (
    CATEGORY_MAPPING,
    PAYLOAD,
    spec_for,
    validate_taxonomy,
)
from cihe.material import MaterialContractError, read_material
from cihe.targets.rime_wubi.package import import_order
from cihe.tracer import run_consumer

XIA_LI_BA_REN_NAMES = [
    "日常口语",
    "生活服务",
    "成语熟语",
    "新词",
    "方言",
    "游戏电竞",
    "动漫二次元",
    "影视娱乐",
]

YANG_CHUN_BAI_XUE_NAMES = [
    "政治",
    "法律、司法",
    "对外关系、国际关系",
    "军事",
    "社会、劳动",
    "灾难、事故",
    "经济",
    "财政、金融",
    "基本建设、建筑业、房地产",
    "农业、农村",
    "矿业、工业",
    "能源、水务、水利",
    "电子信息产业",
    "交通运输、邮政、物流",
    "商业、外贸、海关",
    "服务业、旅游业",
    "环境、气象",
    "教育",
    "科学技术",
    "文化、休闲娱乐",
    "文学、艺术",
    "传媒",
    "医药、卫生",
    "体育",
]


def write_empty_material(root: Path) -> None:
    for spec in CATEGORY_MAPPING:
        for name in spec.files:
            target = root.joinpath(
                *spec.material_path.split("/"), f"{name}.txt"
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("", encoding="utf-8", newline="\n")


def write_words(root: Path, material_path: str, file_name: str, words: list[str]) -> None:
    target = root.joinpath(*material_path.split("/"), f"{file_name}.txt")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(words) + "\n", encoding="utf-8", newline="\n")


def test_category_mapping_is_complete_and_unique() -> None:
    validate_taxonomy()
    assert PAYLOAD["version"] == "1.0.0"
    standards = {item["standard"] for item in PAYLOAD["basis"]}
    assert "GB/T 20093-2022" in standards

    expected_paths = [
        *(f"下里巴人/{name}" for name in XIA_LI_BA_REN_NAMES),
        *(f"阳春白雪/{name}" for name in YANG_CHUN_BAI_XUE_NAMES),
        "阳春白雪/地名",
    ]
    assert [spec.material_path for spec in CATEGORY_MAPPING] == expected_paths
    assert len({spec.material_path for spec in CATEGORY_MAPPING}) == 33
    assert len({spec.slug for spec in CATEGORY_MAPPING}) == 33
    assert [spec.order for spec in CATEGORY_MAPPING] == list(range(33))
    assert spec_for("阳春白雪/地名").files[-1] == "其它"

    assert import_order() == tuple(
        f"wubi86.ci.{spec.slug}" for spec in CATEGORY_MAPPING
    )
    assert import_order()[0] == "wubi86.ci.daily_spoken"
    assert import_order()[-1] == "wubi86.ci.places"

    with pytest.raises(KeyError):
        spec_for("下里巴人/不存在")


def test_category_mapping_matches_golden(golden_root: Path) -> None:
    expected = json.loads(
        (golden_root / "taxonomy" / "mapping.json").read_text(encoding="utf-8")
    )
    actual = [
        {
            "order": spec.order,
            "material_path": spec.material_path,
            "slug": spec.slug,
            "rime_table": f"wubi86.ci.{spec.slug}",
            "files": list(spec.files),
        }
        for spec in CATEGORY_MAPPING
    ]
    assert actual == expected


def test_material_reader_groups_by_category_and_keeps_other_last(
    tmp_path: Path,
) -> None:
    write_words(tmp_path, "下里巴人/日常口语", "口头语", ["你好", "早上好"])
    write_words(tmp_path, "下里巴人/日常口语", "其它", ["谢谢"])

    materials = read_material(tmp_path)

    assert materials == {
        "下里巴人/日常口语": {
            "口头语": ["你好", "早上好"],
            "其它": ["谢谢"],
        }
    }
    assert list(materials["下里巴人/日常口语"]) == ["口头语", "其它"]


def test_material_reader_rejects_files_outside_group_category_layout(
    tmp_path: Path,
) -> None:
    write_words(tmp_path, "下里巴人/日常口语", "其它", ["你好"])
    extra = tmp_path / "下里巴人" / "日常口语.txt"
    extra.write_text("你好\n", encoding="utf-8", newline="\n")

    with pytest.raises(MaterialContractError):
        read_material(tmp_path)


def test_import_order_matches_golden(golden_root: Path) -> None:
    expected = (
        golden_root / "taxonomy" / "import-tables.txt"
    ).read_text(encoding="utf-8").splitlines()
    assert expected[0] == "wubi86.zi"
    assert expected[1:] == list(import_order())


def test_all_ci_tables_are_generated(
    char_table_path: Path, tmp_path: Path
) -> None:
    material_dir = tmp_path / "material"
    write_empty_material(material_dir)

    result = run_consumer(
        material_dir, tmp_path / "consumer", char_table_path
    )
    category_texts = list(result.ci_dir.glob("wubi86.ci.*.dict.yaml"))
    assert len(category_texts) == len(CATEGORY_MAPPING)
    for path in category_texts:
        text = path.read_text(encoding="utf-8")
        assert "sort: original" in text
        assert "weight" not in text
        assert "stem" not in text
    assert not list(result.ci_dir.glob("*.schema.yaml"))


def test_consumer_rejects_undeclared_category(
    char_table_path: Path, tmp_path: Path
) -> None:
    material_dir = tmp_path / "material"
    write_words(material_dir, "下里巴人/不存在", "其它", ["你好"])

    with pytest.raises(MaterialContractError, match="没有映射"):
        run_consumer(material_dir, tmp_path / "consumer", char_table_path)


def test_consumer_rejects_undeclared_material_file(
    char_table_path: Path, tmp_path: Path
) -> None:
    material_dir = tmp_path / "material"
    write_words(material_dir, "下里巴人/日常口语", "不存在", ["你好"])

    with pytest.raises(MaterialContractError, match="未在 taxonomy 中声明"):
        run_consumer(material_dir, tmp_path / "consumer", char_table_path)


def test_consumer_rejects_missing_declared_category_file(
    char_table_path: Path, tmp_path: Path
) -> None:
    material_dir = tmp_path / "material"
    write_words(material_dir, "下里巴人/日常口语", "其它", ["你好"])

    with pytest.raises(MaterialContractError, match="缺少 taxonomy 声明的类目文件"):
        run_consumer(material_dir, tmp_path / "consumer", char_table_path)
