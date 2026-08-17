"""
FSM — 异步状态机调度引擎

让复杂的分步状态机写成直观、线性的 async/await Python 协程代码。
"""

import asyncio
import logging
from typing import Any, Callable, Coroutine, List, Optional, Tuple, Union

from .event import Event, EventMatcher, match_event

log = logging.getLogger("robocon_fsm.fsm")


class FSMTimeoutError(asyncio.TimeoutError):
    """状态机等待事件超时异常."""
    pass


class FSM:
    """
    异步状态机调度器 (Finite State Machine).

    核心能力:
      1. 线程安全的事件注入: 支持从 ROS2 回调、串口中断、视觉子线程通过 post_event 投递事件。
      2. 强大的 async 调度原语:
         - await fsm.wait(seconds)
         - await fsm.wait_event("NAV_DONE", timeout=10.0)
         - await fsm.wait_any("NAV_DONE", "OBSTACLE", timeout=5.0)
         - await fsm.wait_all("ARM_DONE", "CHASSIS_READY", timeout=8.0)
      3. 全局事件钩子与审计追踪: 方便比赛调试与日志回放。
    """

    def __init__(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        self._loop: Optional[asyncio.AbstractEventLoop] = loop
        # 等待队列: [(matcher, future, is_cancelled)]
        self._waiters: List[Tuple[EventMatcher, asyncio.Future]] = []
        self._event_history: List[Event] = []
        self._max_history = 100
        self._event_hooks: List[Callable[[Event], None]] = []

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """设置绑定的 asyncio 事件循环."""
        self._loop = loop

    def get_loop(self) -> asyncio.AbstractEventLoop:
        """获取绑定的 asyncio 事件循环，如果未设置则尝试获取当前运行的循环."""
        if self._loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                pass
        if self._loop is None:
            raise RuntimeError("FSM event loop is not set. Call fsm.set_loop(loop) first.")
        return self._loop

    def add_event_hook(self, hook: Callable[[Event], None]) -> None:
        """注册全局事件监听钩子（用于调试日志、可视化或数据记录）."""
        self._event_hooks.append(hook)

    # ── 线程安全的事件分发 ──────────────────────────────────────────

    def post_event(self, event: Union[Event, str], success: bool = True, command: int = 0, data: Any = None) -> None:
        """
        从任意线程（ROS2 回调线程、串口监听线程等）向状态机投递事件。
        内部自动调用 call_soon_threadsafe 确保跨线程安全。
        """
        if isinstance(event, str):
            ev = Event(type=event, success=success, command=command, data=data)
        else:
            ev = event

        if self._loop is None:
            log.warning("post_event(%s) dropped: event loop not set", ev.type)
            return

        if self._loop.is_closed():
            log.warning("post_event(%s) dropped: event loop is closed", ev.type)
            return

        if self._loop.is_running():
            self._loop.call_soon_threadsafe(self._dispatch_event, ev)
        else:
            self._loop.call_soon(self._dispatch_event, ev)

    def _dispatch_event(self, event: Event) -> None:
        """在 asyncio 主循环中触发匹配的分发处理."""
        log.info("[EVENT] %s", event)

        # 记录历史
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)

        # 触发钩子
        for hook in self._event_hooks:
            try:
                hook(event)
            except Exception as e:
                log.error("Error in event hook: %s", e)

        # 遍历等待队列，唤醒匹配的 Future
        still_waiting = []
        for matcher, future in self._waiters:
            if not future.done() and match_event(matcher, event):
                future.set_result(event)
            elif not future.done():
                still_waiting.append((matcher, future))
        self._waiters = still_waiting

    # ── 核心 Async 等待原语 ─────────────────────────────────────────

    async def wait(self, seconds: float) -> None:
        """异步非阻塞等待指定的秒数."""
        await asyncio.sleep(seconds)

    async def wait_event(
        self,
        matcher: EventMatcher,
        timeout: Optional[float] = None
    ) -> Event:
        """
        等待单个匹配的事件到达。

        Args:
            matcher: 事件类型字符串 (如 "NAV_DONE") 或谓词函数 (lambda e: e.type == "ACK" and e.command == 1)
            timeout: 超时时间（秒）。如果为 None 则无限等待直至到达。

        Returns:
            到达并匹配的 Event 对象。

        Raises:
            FSMTimeoutError: 如果在 timeout 秒内未收到匹配事件。
        """
        loop = self.get_loop()
        fut = loop.create_future()
        self._waiters.append((matcher, fut))

        try:
            if timeout is not None:
                return await asyncio.wait_for(fut, timeout=timeout)
            else:
                return await fut
        except asyncio.TimeoutError:
            matcher_name = matcher if isinstance(matcher, str) else getattr(matcher, "__name__", "predicate")
            raise FSMTimeoutError(f"Timed out waiting for event '{matcher_name}' after {timeout}s")
        finally:
            # 清理 waiter
            self._waiters = [item for item in self._waiters if item[1] is not fut]

    async def wait_any(
        self,
        *matchers: EventMatcher,
        timeout: Optional[float] = None
    ) -> Event:
        """
        等待多个事件中的【任意一个】到达（常用于“正常到达 vs 撞障/急停”竞赛）。

        Args:
            *matchers: 一个或多个事件匹配器
            timeout: 超时时间（秒）

        Returns:
            率先到达的 Event 对象。
        """
        if not matchers:
            raise ValueError("wait_any requires at least one matcher")

        loop = self.get_loop()
        composite_fut = loop.create_future()

        # 注册一组 waiter，任意一个匹配即可 resolve composite_fut
        sub_waiters: List[Tuple[EventMatcher, asyncio.Future]] = []

        def make_callback(sub_fut: asyncio.Future):
            def _done(f: asyncio.Future):
                if not composite_fut.done() and not f.cancelled() and f.exception() is None:
                    composite_fut.set_result(f.result())
            return _done

        for m in matchers:
            f = loop.create_future()
            f.add_done_callback(make_callback(f))
            sub_waiters.append((m, f))
            self._waiters.append((m, f))

        try:
            if timeout is not None:
                return await asyncio.wait_for(composite_fut, timeout=timeout)
            else:
                return await composite_fut
        except asyncio.TimeoutError:
            names = [m if isinstance(m, str) else "predicate" for m in matchers]
            raise FSMTimeoutError(f"Timed out in wait_any({names}) after {timeout}s")
        finally:
            # 清理所有子 waiter
            sub_futs = {item[1] for item in sub_waiters}
            self._waiters = [item for item in self._waiters if item[1] not in sub_futs]
            for _, f in sub_waiters:
                if not f.done():
                    f.cancel()

    async def wait_all(
        self,
        *matchers: EventMatcher,
        timeout: Optional[float] = None
    ) -> List[Event]:
        """
        等待给定的【所有】事件全部到达（常用于并行任务全部完成检测）。

        Args:
            *matchers: 一个或多个事件匹配器
            timeout: 超时时间（秒）

        Returns:
            所有到达的 Event 列表，顺序与 matchers 参数对应。
        """
        if not matchers:
            return []

        coros = [self.wait_event(m) for m in matchers]
        try:
            if timeout is not None:
                return await asyncio.wait_for(asyncio.gather(*coros), timeout=timeout)
            else:
                return await asyncio.gather(*coros)
        except asyncio.TimeoutError:
            names = [m if isinstance(m, str) else "predicate" for m in matchers]
            raise FSMTimeoutError(f"Timed out in wait_all({names}) after {timeout}s")

    async def race(
        self,
        coroutine: Coroutine,
        timeout: Optional[float] = None
    ) -> Any:
        """执行任意异步协程，并可附加超时保护."""
        if timeout is not None:
            return await asyncio.wait_for(coroutine, timeout=timeout)
        return await coroutine

    def clear(self) -> None:
        """清理所有正在等待的 Future，通常在决策重置时调用."""
        for _, fut in self._waiters:
            if not fut.done():
                fut.cancel()
        self._waiters.clear()
