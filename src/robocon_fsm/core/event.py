"""
Event System — 异步状态机事件定义与匹配器
"""

from dataclasses import dataclass, field
import time
from typing import Any, Callable, Union

@dataclass
class Event:
    """
    状态机事件载体.

    Attributes:
        type: 事件类型名称，如 "NAV_DONE", "ARM_DONE", "ACK", "COLLISION_WARNING" 等
        success: 该事件所代表的操作是否成功完成
        command: 指令编号或功能码（下位机通信常用）
        data: 附加数据（任意类型，如坐标、视觉识别结果、传感器读数等）
        timestamp: 事件生成的时间戳
    """
    type: str
    success: bool = True
    command: int = 0
    data: Any = None
    timestamp: float = field(default_factory=time.time)

    def __str__(self) -> str:
        data_str = f", data={self.data}" if self.data is not None else ""
        cmd_str = f", cmd={self.command}" if self.command != 0 else ""
        return f"Event({self.type}, success={self.success}{cmd_str}{data_str})"


# 事件匹配规则: 可以是事件名称字符串，或者是返回布尔值的判定函数
EventMatcher = Union[str, Callable[[Event], bool]]


def match_event(matcher: EventMatcher, event: Event) -> bool:
    """检查事件是否符合给定的匹配器规则."""
    if isinstance(matcher, str):
        return event.type == matcher
    elif callable(matcher):
        try:
            return bool(matcher(event))
        except Exception:
            return False
    return False
