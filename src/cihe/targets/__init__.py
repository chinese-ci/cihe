"""目标适配器注册表。

默认 target 固定为 `rime-wubi`；其它 target 必须显式指定。
"""

from __future__ import annotations

from cihe.targets.base import (
    EmittedTarget,
    EncodedTarget,
    Encoder,
    MaterialTree,
    TargetAdapter,
)

DEFAULT_TARGET = "rime-wubi"


def available_targets() -> tuple[str, ...]:
    return (DEFAULT_TARGET,)


def get_target(name: str) -> TargetAdapter:
    if name == DEFAULT_TARGET:
        from cihe.targets.rime_wubi import RimeWubiTarget

        return RimeWubiTarget()
    raise ValueError(
        f"未知 target：{name}；v1 只提供 {DEFAULT_TARGET}"
    )


__all__ = [
    "DEFAULT_TARGET",
    "EncodedTarget",
    "EmittedTarget",
    "Encoder",
    "MaterialTree",
    "TargetAdapter",
    "available_targets",
    "get_target",
]
