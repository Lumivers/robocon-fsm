"""
ROS2 Actions Base — 针对 ROS2 机器人的动作分发基类
"""

import logging
from typing import Optional

try:
    from geometry_msgs.msg import Twist
    HAS_GEOMETRY_MSGS = True
except ImportError:
    HAS_GEOMETRY_MSGS = False

from ..core.action_base import ActionDispatcher
from ..core.fsm import FSM

log = logging.getLogger("robocon_fsm.ros2.actions")


class Ros2ActionDispatcher(ActionDispatcher):
    """
    基于 ROS2 的动作分发器基类。
    
    自动封装常用 ROS2 动作操作（如 /cmd_vel 发布、底盘速度平滑停止、通用 Publisher 注册）。
    """

    def __init__(self, node=None, fsm: Optional[FSM] = None):
        super().__init__(fsm)
        self.node = node
        self._cmd_vel_pub = None

    def enable_cmd_vel(self, topic_name: str = "/cmd_vel", qos_depth: int = 10) -> None:
        """启用标准底盘速度发布器."""
        if self.node is not None and HAS_GEOMETRY_MSGS:
            self._cmd_vel_pub = self.node.create_publisher(Twist, topic_name, qos_depth)

    def publish_cmd_vel(self, vx: float, vy: float = 0.0, vz: float = 0.0) -> None:
        """发布底盘速度."""
        if self._cmd_vel_pub is None:
            log.warning("cmd_vel publisher is not enabled.")
            return

        msg = Twist()
        msg.linear.x = float(vx)
        msg.linear.y = float(vy)
        msg.angular.z = float(vz)
        self._cmd_vel_pub.publish(msg)

    def stop_cmd_vel(self) -> None:
        """立即停止底盘运动."""
        self.publish_cmd_vel(0.0, 0.0, 0.0)
