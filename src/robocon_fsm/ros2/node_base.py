"""
ROS2 Base Node — 异步决策节点基类

封装 ROS2 节点生命周期与 asyncio 事件循环的双线程桥接。
"""

import asyncio
import logging
import threading
from typing import Optional

try:
    import rclpy
    from rclpy.node import Node
    from rclpy.executors import MultiThreadedExecutor
    HAS_RCLPY = True
except ImportError:
    HAS_RCLPY = False
    Node = object  # 兼容无 ROS2 环境时的导入

from ..core.fsm import FSM
from ..core.action_base import ActionDispatcher
from ..core.context import Blackboard

log = logging.getLogger("robocon_fsm.ros2")


class Ros2DecisionNodeBase(Node if HAS_RCLPY else object):
    """
    通用 ROS2 决策节点基类。

    职责:
      1. 托管 ROS2 Node 生命周期与多线程执行器。
      2. 在独立子线程中运行 asyncio 事件循环，保障主决策协程顺畅运行。
      3. 自动连接 FSM 与 ActionDispatcher，保证 ROS2 回调中 post_event 跨线程安全。
    """

    def __init__(self, node_name: str = "decision_node"):
        if not HAS_RCLPY:
            raise ImportError(
                "rclpy is not installed. Please install ROS 2 to use Ros2DecisionNodeBase."
            )
        super().__init__(node_name)

        # 核心框架组件
        self.fsm = FSM()
        self.blackboard = Blackboard()
        self.act: Optional[ActionDispatcher] = None

        # 异步线程与事件循环
        self._loop = asyncio.new_event_loop()
        self.fsm.set_loop(self._loop)
        self._decision_thread: Optional[threading.Thread] = None
        self._is_running = True

        self.get_logger().info(f"[{node_name}] Initialized. Preparing decision subsystem.")

    def set_action_dispatcher(self, action_dispatcher: ActionDispatcher) -> None:
        """注册并绑定动作分发器."""
        self.act = action_dispatcher
        self.act.bind_fsm(self.fsm)

    def start_decision(self) -> None:
        """启动后台决策协程线程."""
        if self.act is None:
            self.get_logger().warn("ActionDispatcher is not set before start_decision!")

        def _run_loop():
            asyncio.set_event_loop(self._loop)
            self.get_logger().info("Asyncio decision loop started.")
            try:
                self._loop.run_until_complete(self.run_mission())
            except asyncio.CancelledError:
                self.get_logger().info("Decision mission cancelled.")
            except Exception as e:
                self.get_logger().error(f"Unhandled exception in decision mission: {e}", exc_info=True)
            finally:
                self.get_logger().info("Decision mission ended.")

        self._decision_thread = threading.Thread(target=_run_loop, daemon=True, name="DecisionWorker")
        self._decision_thread.start()

    async def run_mission(self) -> None:
        """
        全场决策主流程（虚方法，由用户子类覆盖实现具体比赛战术）。
        """
        raise NotImplementedError("Subclasses must implement 'async def run_mission(self)'.")

    def destroy_node(self) -> None:
        """清理并优雅终止节点."""
        self._is_running = False
        if self._loop.is_running():
            self._loop.call_soon_threadsafe(self.fsm.clear)
            self._loop.call_soon_threadsafe(self._loop.stop)
        super().destroy_node()


def run_decision_node(node_factory):
    """
    标准的 ROS2 节点启动引导器（自动处理 MultiThreadedExecutor 与异常退出）。
    
    Usage:
        def main(args=None):
            run_decision_node(lambda: MyRobotDecisionNode())
    """
    if not HAS_RCLPY:
        raise ImportError("rclpy is not installed.")

    rclpy.init()
    node = node_factory()
    executor = MultiThreadedExecutor()
    executor.add_node(node)

    # 启动决策协程
    node.start_decision()

    try:
        executor.spin()
    except KeyboardInterrupt:
        node.get_logger().info("KeyboardInterrupt received, shutting down...")
    finally:
        node.destroy_node()
        rclpy.shutdown()
