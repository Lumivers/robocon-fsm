"""
Mock Action Dispatcher — 离线虚拟动作器与硬件仿真

允许在没有物理机器人、没有下位机甚至没有 ROS2 的环境下，
在个人电脑上对完整的决策状态机逻辑进行单元测试与仿真验证。
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from ..core.action_base import ActionDispatcher
from ..core.event import Event
from ..core.fsm import FSM

log = logging.getLogger("robocon_fsm.mock")


class MockActionDispatcher(ActionDispatcher):
    """
    虚拟动作器。

    特性:
      1. 自动记录所有被调用的动作与发送的指令 (action_log)。
      2. 可配置模拟耗时 (如导航需 0.5 秒完成，机械臂动作需 0.2 秒完成)。
      3. 可配置模拟下位机 ACK 自动回复。
      4. 可在指定延迟后自动投递完成事件 (如 "NAV_DONE", "ARM_DONE")。
    """

    def __init__(
        self,
        fsm: Optional[FSM] = None,
        auto_ack: bool = True,
        ack_delay: float = 0.01,
        default_action_duration: float = 0.05,
    ):
        super().__init__(fsm)
        self.auto_ack = auto_ack
        self.ack_delay = ack_delay
        self.default_action_duration = default_action_duration

        # 记录所有调用的动作: [(method_name, args, kwargs)]
        self.history: List[Tuple[str, tuple, dict]] = []
        # 虚拟传感器数据存储
        self.sensor_data: Dict[str, Any] = {}

    def _record(self, method_name: str, *args, **kwargs) -> None:
        """记录动作调用."""
        log.info("[MOCK ACTION] %s(args=%s, kwargs=%s)", method_name, args, kwargs)
        self.history.append((method_name, args, kwargs))

    def simulate_navigation(
        self,
        target_x: float,
        target_y: float,
        target_theta: float = 0.0,
        duration: Optional[float] = None,
        success: bool = True
    ) -> None:
        """
        模拟底盘导航。记录动作并在 duration 秒后触发 NAV_DONE 事件。
        """
        self._record("navigate", target_x, target_y, target_theta)
        delay = duration if duration is not None else self.default_action_duration

        async def _finish():
            await asyncio.sleep(delay)
            self.post_event("NAV_DONE", success=success, data={"x": target_x, "y": target_y, "theta": target_theta})

        if self.fsm is not None:
            loop = self.fsm.get_loop()
            asyncio.run_coroutine_threadsafe(_finish(), loop)

    def simulate_actuator(
        self,
        actuator_name: str,
        command_id: int,
        done_event_type: str,
        duration: Optional[float] = None,
        success: bool = True
    ) -> None:
        """
        模拟任意机构执行并自动回报完成事件。
        """
        self._record("actuator", actuator_name, command_id, done_event_type)
        delay = duration if duration is not None else self.default_action_duration

        async def _finish():
            if self.auto_ack:
                await asyncio.sleep(self.ack_delay)
                self.post_event("ACK", success=True, command=command_id)
            await asyncio.sleep(delay)
            self.post_event(done_event_type, success=success, command=command_id)

        if self.fsm is not None:
            loop = self.fsm.get_loop()
            asyncio.run_coroutine_threadsafe(_finish(), loop)
