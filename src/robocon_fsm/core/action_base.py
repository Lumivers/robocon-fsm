"""
Action Base — 硬件动作分发器抽象基类

- 决策层(decision.py)只调用ActionDispatcher声明的方法。
- 通信/驱动层(ROS2 / 纯串口 / 虚拟仿真)实现具体的子类。
"""

import asyncio
import logging
from abc import ABC
from typing import Any, Callable, Optional, Union

from .event import Event, EventMatcher
from .fsm import FSM, FSMTimeoutError

log = logging.getLogger("robocon_fsm.actions")


class ActionDispatcher(ABC):
    """
    硬件动作分发器基类。

    所有机器人的具体动作实现（如 `MyRobotActions` 或 `R2Actions`）都应继承此类。
    """

    def __init__(self, fsm: Optional[FSM] = None):
        self.fsm: Optional[FSM] = fsm
        # 兼容简易回调设置
        self._post_event_cb: Optional[Callable[[Event], None]] = None

    def bind_fsm(self, fsm: FSM) -> None:
        """绑定关联的 FSM 状态机实例."""
        self.fsm = fsm

    def post_event(
        self,
        event: Union[Event, str],
        success: bool = True,
        command: int = 0,
        data: Any = None
    ) -> None:
        """
        向绑定的 FSM 投递事件（供 ROS 回调或下位机监听线程调用）.
        """
        if self.fsm is not None:
            self.fsm.post_event(event, success=success, command=command, data=data)
        elif self._post_event_cb is not None:
            if isinstance(event, str):
                ev = Event(type=event, success=success, command=command, data=data)
            else:
                ev = event
            self._post_event_cb(ev)
        else:
            log.warning("post_event called on ActionDispatcher with no FSM or callback bound!")

    async def retry_until_ack(
        self,
        send_fn: Callable[[], None],
        ack_matcher: EventMatcher,
        timeout: float = 0.5,
        max_retries: int = 5,
        interval: float = 0.05,
    ) -> Event:
        """
        通用的下位机可靠性重发逻辑:
        执行发送 -> 异步等待 ACK 确认 -> 若超时则重试 -> 超过最大次数抛出超时异常。

        Args:
            send_fn: 发送指令的无参函数 (如 lambda: self.pub_cmd.publish(msg))
            ack_matcher: 期望收到的 ACK 事件名称或匹配器 (如 "UPPER_ACK" 或 lambda e: e.command == 0x01)
            timeout: 单次等待 ACK 的超时时间（秒）
            max_retries: 最大重试次数
            interval: 重试前的短暂退避时间（秒）

        Returns:
            收到的确认 Event
        """
        if self.fsm is None:
            raise RuntimeError("Cannot use retry_until_ack without a bound FSM instance.")

        last_error = None
        for attempt in range(1, max_retries + 1):
            send_fn()
            try:
                event = await self.fsm.wait_event(ack_matcher, timeout=timeout)
                return event
            except FSMTimeoutError as err:
                last_error = err
                log.warning(
                    "ACK timeout (attempt %d/%d) for %s. Retrying...",
                    attempt, max_retries, ack_matcher
                )
                if interval > 0:
                    await asyncio.sleep(interval)

        raise FSMTimeoutError(
            f"Failed to receive ACK for '{ack_matcher}' after {max_retries} attempts."
        ) from last_error

    def emergency_stop(self) -> None:
        """急停接口，子类可覆盖实现底盘刹车、机构断电等逻辑."""
        log.warning("ActionDispatcher.emergency_stop() called (base implementation)")
