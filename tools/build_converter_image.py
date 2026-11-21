"""构建 tracer 使用的 imewlconverter v3.6.0 镜像。"""

from __future__ import annotations

import subprocess
from pathlib import Path

from cihe.encoding import DEFAULT_IMAGE


def main() -> None:
    context = Path(__file__).resolve().parent / "imewlconverter"
    subprocess.run(
        ["docker", "build", "-t", DEFAULT_IMAGE, str(context)],
        check=True,
    )
    print(f"已构建 {DEFAULT_IMAGE}")


if __name__ == "__main__":
    main()
