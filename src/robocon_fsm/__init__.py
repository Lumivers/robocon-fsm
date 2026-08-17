"""
Robocon Async FSM Framework (robocon-fsm)
----------------------------------------
一个专为全国大学生机器人大赛 (Robocon / RoboMaster / 智能车) 设计的通用异步决策框架。

核心理念:
- 状态即协程: 使用 Python async/await 编写线性决策流，告别繁琐的传统 switch-case / step 状态机。
- 关注点分离: 框架调度 (FSM) + 硬件动作 (ActionDispatcher) + 业务决策 (Decision) + 通信容器 (ROS2/Serial/Mock)。
- 离线可仿真: 支持无物理机器人环境下的本地单步 Mock 调试。
"""

from .core.event import Event, EventMatcher
from .core.fsm import FSM
from .core.action_base import ActionDispatcher
from .core.context import Blackboard

__version__ = "1.0.0"
__all__ = [
    "Event",
    "EventMatcher",
    "FSM",
    "ActionDispatcher",
    "Blackboard",
]
