"""
Context & Blackboard — 决策上下文与黑板系统

用于在状态机、不同决策协程与各传感器节点之间安全共享比赛状态（如红蓝区、当前得分、目标位姿等）。
"""

from typing import Any, Dict, Optional


class Blackboard:
    """
    通用黑板（全局数据与状态容器）。

    提供键值对存储与属性化快速访问，支持数据监听与重置。
    """

    def __init__(self, **kwargs):
        self._data: Dict[str, Any] = dict(kwargs)

    def set(self, key: str, value: Any) -> None:
        """设置数据项."""
        self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """获取数据项，支持默认值."""
        return self._data.get(key, default)

    def has(self, key: str) -> bool:
        """是否存在某个数据项."""
        return key in self._data

    def remove(self, key: str) -> Optional[Any]:
        """删除数据项."""
        return self._data.pop(key, None)

    def clear(self) -> None:
        """清空所有数据项."""
        self._data.clear()

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            return super().__getattribute__(name)
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"'Blackboard' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            self._data[name] = value

    def __repr__(self) -> str:
        return f"Blackboard({self._data})"
