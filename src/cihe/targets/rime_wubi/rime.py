"""把方案包部署到临时 Rime 目录，依次编译全部 schema，并从编译产物里查码。"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from cihe.dicts import parse_tsv_entries

SCHEMA_IDS = ("wubi86", "wubi_pinyin", "wubi_trad")

SHARED_FILES = (
    "default.yaml",
    "punctuation.yaml",
    "key_bindings.yaml",
    "symbols.yaml",
    "pinyin_simp.dict.yaml",
)


class RimeUnavailable(RuntimeError):
    """本机没有 rime_deployer 或 Rime 共享数据。"""


class RimeDeployError(RuntimeError):
    """Rime 部署失败。"""


@dataclass(frozen=True)
class SchemaDeploy:
    schema_id: str
    dictionary: str
    prism: str
    artifacts: tuple[Path, ...]
    table_path: Path
    entries: tuple[tuple[str, str], ...]

    def words_for(self, code: str) -> list[str]:
        return [text for text, entry_code in self.entries if entry_code == code]


@dataclass(frozen=True)
class DeployResult:
    table_path: Path
    entries: tuple[tuple[str, str], ...]
    schemas: Mapping[str, SchemaDeploy]

    def words_for(self, code: str) -> list[str]:
        return [text for text, entry_code in self.entries if entry_code == code]


@dataclass(frozen=True)
class _SchemaInfo:
    schema_id: str
    package_path: Path
    dictionary: str
    prism: str
    has_reverse_lookup: bool


def _parse_table(path: Path) -> list[tuple[str, str]]:
    try:
        return parse_tsv_entries(
            path.read_text(encoding="utf-8").splitlines(), str(path)
        )
    except ValueError as error:
        raise RimeDeployError(str(error)) from error


def _schema_id(path: Path) -> str:
    suffix = ".schema.yaml"
    if not path.name.endswith(suffix):
        raise RimeDeployError(f"不是 schema 文件：{path}")
    return path.name[: -len(suffix)]


def _schema_info(package_path: Path) -> _SchemaInfo:
    schema_id = _schema_id(package_path)
    schema_text = package_path.read_text(encoding="utf-8")
    dictionary = (
        _section_value(schema_text, "translator", "dictionary") or schema_id
    )
    return _SchemaInfo(
        schema_id=schema_id,
        package_path=package_path,
        dictionary=dictionary,
        prism=_section_value(schema_text, "translator", "prism") or dictionary,
        has_reverse_lookup=_top_level_section(schema_text, "reverse_lookup"),
    )


def _ordered_schemas(package_dir: Path) -> list[_SchemaInfo]:
    paths = list(package_dir.glob("*.schema.yaml"))
    if not paths:
        raise RimeDeployError(f"方案包没有 schema：{package_dir}")
    order = {schema_id: index for index, schema_id in enumerate(SCHEMA_IDS)}
    paths.sort(key=lambda path: (order.get(_schema_id(path), len(order)), _schema_id(path)))
    return [_schema_info(path) for path in paths]


def _section_value(text: str, section: str, key: str) -> str | None:
    in_section = False
    for line in text.splitlines():
        if line and not line.startswith((" ", "\t")):
            in_section = line.strip() == f"{section}:"
            continue
        if in_section and line.startswith(f"  {key}:"):
            return line.split(":", 1)[1].strip().strip('"')
    return None


def _top_level_section(text: str, section: str) -> bool:
    return any(line.strip() == f"{section}:" for line in text.splitlines())


def _expected_artifacts(
    build_dir: Path, schema: _SchemaInfo
) -> tuple[Path, ...]:
    artifacts = [
        build_dir / f"{schema.schema_id}.schema.yaml",
        build_dir / f"{schema.dictionary}.table.bin",
        build_dir / f"{schema.dictionary}.table.txt",
        build_dir / f"{schema.prism}.prism.bin",
    ]
    if schema.has_reverse_lookup:
        artifacts.append(build_dir / f"{schema.dictionary}.reverse.bin")
    return tuple(artifacts)


def _copy_shared_data(shared_data_dir: Path, shared_dir: Path) -> None:
    if not shared_data_dir.is_dir():
        raise RimeUnavailable(f"找不到 Rime 共享数据目录：{shared_data_dir}")
    missing = [
        name
        for name in SHARED_FILES
        if not (shared_data_dir / name).is_file()
    ]
    if missing:
        raise RimeUnavailable(
            f"Rime 共享数据目录缺少文件：{shared_data_dir}："
            f"{'、'.join(missing)}"
        )
    for name in SHARED_FILES:
        shutil.copy2(shared_data_dir / name, shared_dir / name)


def _environment(work_dir: Path) -> dict[str, str]:
    environment = dict(os.environ)
    for name in tuple(environment):
        if name.startswith("RIME_"):
            environment.pop(name)
    for variable in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
        target = work_dir / variable.lower()
        target.mkdir(parents=True, exist_ok=True)
        environment[variable] = str(target)
    environment["TMPDIR"] = str(work_dir / "tmp")
    (work_dir / "tmp").mkdir(parents=True, exist_ok=True)
    return environment


def _default_shared_data_dir() -> Path:
    return Path(
        os.environ.get("CIHE_RIME_SHARED_DATA", "/usr/share/rime-data")
    )


def deploy_package(
    package_dir: Path,
    work_dir: Path,
    *,
    shared_data_dir: Path | None = None,
) -> DeployResult:
    if shutil.which("rime_deployer") is None:
        raise RimeUnavailable("找不到 rime_deployer")

    user_dir = work_dir / "user"
    shared_dir = work_dir / "shared"
    build_dir = work_dir / "build"
    for directory in (user_dir, shared_dir, build_dir):
        directory.mkdir(parents=True, exist_ok=True)

    for path in package_dir.iterdir():
        if path.is_file():
            shutil.copy2(path, user_dir / path.name)

    schemas = _ordered_schemas(package_dir)
    schema_list = "".join(
        f"    - schema: {schema.schema_id}\n" for schema in schemas
    )
    (user_dir / "default.custom.yaml").write_text(
        f"patch:\n  schema_list:\n{schema_list}",
        encoding="utf-8",
        newline="\n",
    )
    _copy_shared_data(shared_data_dir or _default_shared_data_dir(), shared_dir)

    environment = _environment(work_dir)
    deployed: dict[str, SchemaDeploy] = {}
    tables: dict[str, tuple[tuple[str, str], ...]] = {}
    for schema in schemas:
        schema_id = schema.schema_id
        schema_path = user_dir / schema.package_path.name
        result = subprocess.run(
            [
                "rime_deployer",
                "--compile",
                str(schema_path),
                str(user_dir),
                str(shared_dir),
                str(build_dir),
            ],
            cwd=work_dir,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RimeDeployError(
                f"rime_deployer 失败（{schema_id}，退出码 {result.returncode}）：\n"
                f"{result.stderr.strip()}"
            )
        artifacts = _expected_artifacts(build_dir, schema)
        missing = [path for path in artifacts if not path.is_file()]
        if missing:
            raise RimeDeployError(
                f"Rime 没有生成 {schema_id} 的编译产物：\n"
                f"{'\n'.join(str(path) for path in missing)}\n"
                f"{result.stderr.strip()}"
            )
        table_path = build_dir / f"{schema.dictionary}.table.txt"
        if schema.dictionary not in tables:
            tables[schema.dictionary] = tuple(_parse_table(table_path))
        deployed[schema_id] = SchemaDeploy(
            schema_id=schema_id,
            dictionary=schema.dictionary,
            prism=schema.prism,
            artifacts=artifacts,
            table_path=table_path,
            entries=tables[schema.dictionary],
        )

    primary = deployed[schemas[0].schema_id]
    return DeployResult(
        table_path=primary.table_path,
        entries=primary.entries,
        schemas=deployed,
    )
