"""验证组装后的 rime-wubi 方案包：基础项目 + Ci 词表。

只做部署查码与 OpenCC 校验，不生成或修改任何文件。
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

from cihe.targets.rime_wubi.rime import (
    SCHEMA_IDS,
    RimeDeployError,
    RimeUnavailable,
    deploy_package,
)
from cihe.targets.rime_wubi.rime_query import RimeQueryError, query_package

ROOT = Path(__file__).resolve().parent.parent


def _payload(
    package: Path,
    *,
    ok: bool,
    errors: list[str],
    deployment: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "ok": ok,
        "package": str(package),
        "errors": errors,
        "schemas": (deployment or {}).get("schemas", {}),
        "opencc": (deployment or {}).get("opencc", {"ok": False}),
        "rime_version": (deployment or {}).get("rime_version", ""),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "var" / "package-verify" / "report.json",
    )
    arguments = parser.parse_args()

    report_path = arguments.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    package = arguments.package
    errors: list[str] = []
    deployment: dict[str, object] | None = None

    missing = [
        name
        for name in (
            "wubi86.schema.yaml",
            "wubi_pinyin.schema.yaml",
            "wubi_trad.schema.yaml",
            "wubi86.dict.yaml",
            "wubi86.zi.dict.yaml",
        )
        if not (package / name).is_file()
    ]
    if missing:
        errors.append(f"方案包缺少文件：{'、'.join(missing)}")
    else:
        try:
            with tempfile.TemporaryDirectory(prefix="cihe-verify-") as temporary:
                work_dir = Path(temporary)
                deployed = deploy_package(package, work_dir)
                queried = query_package(deployed, package)
                schemas = {
                    schema_id: {
                        "dictionary": deployed.schemas[schema_id].dictionary,
                        "prism": deployed.schemas[schema_id].prism,
                        "codes": queried.schemas[schema_id].codes,
                    }
                    for schema_id in SCHEMA_IDS
                }
                deployment = {
                    "schemas": schemas,
                    "opencc": asdict(queried.opencc),
                    "rime_version": queried.version,
                }
                if not queried.opencc.ok:
                    errors.append(
                        f"OpenCC 输出不符：{queried.opencc.reason}"
                    )
        except (
            RimeUnavailable,
            RimeDeployError,
            RimeQueryError,
            OSError,
            ValueError,
        ) as error:
            errors.append(str(error))

    ok = not errors
    payload = _payload(
        package, ok=ok, errors=errors, deployment=deployment
    )
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"部署查码报告：{report_path}")
    if ok:
        schemas = payload.get("schemas")
        names = sorted(schemas) if isinstance(schemas, dict) else []
        print(f"schema：{'、'.join(names)}")
        print(
            "OpenCC："
            + json.dumps(payload.get("opencc", {}), ensure_ascii=False)
        )
        return 0
    for error in errors:
        print(f"失败：{error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
