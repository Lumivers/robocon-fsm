"""
模板: 硬件动作分发器实现 (my_actions.py)

在此文件中实现你队伍机器人的具体硬件控制函数 (例如发送底盘导航、机械臂抓取、发射等)，
并将 ROS2 的订阅消息转换为状态机事件 (post_event)。
"""

from robocon_fsm.ros2 import Ros2ActionDispatcher
from std_msgs.msg import Bool, UInt8
from geometry_msgs.msg import PoseStamped


class MyRobotActions(Ros2ActionDispatcher):
    """
    动作分发器.
    继承自 Ros2ActionDispatcher，自动具备 cmd_vel 发布与 FSM 事件绑定能力。
    """

    def __init__(self, node=None):
        super().__init__(node=node)

        # 1. 注册ROS2 Publisher
        if self.node is not None:
            self.pub_nav_goal = self.node.create_publisher(PoseStamped, "/goal_pose", 10)
            self.pub_gripper = self.node.create_publisher(UInt8, "/robot/gripper_cmd", 10)

            # 启用默认底盘速度控制 (发布 /cmd_vel)
            self.enable_cmd_vel("/cmd_vel")

    # ── 下发动作接口 (供 my_decision.py 调用) ───────────────────────

    def send_navigate(self, x: float, y: float, yaw: float = 0.0) -> None:
        """下发底盘导航目标点."""
        if self.node is None:
            return
        msg = PoseStamped()
        msg.header.stamp = self.node.get_clock().now().to_msg()
        msg.header.frame_id = "map"
        msg.pose.position.x = float(x)
        msg.pose.position.y = float(y)
        # 此处可根据需要填充四元数姿态
        self.pub_nav_goal.publish(msg)
        self.node.get_logger().info(f"Published nav goal: ({x}, {y})")

    def send_gripper_command(self, cmd_id: int) -> None:
        """下发机械臂指令 (1: 张开, 2: 闭合)."""
        if self.node is None:
            return
        msg = UInt8()
        msg.data = cmd_id
        self.pub_gripper.publish(msg)
        self.node.get_logger().info(f"Published gripper command: {cmd_id}")

    # ── ROS2 消息回调 (将硬件反馈转化为 FSM 事件) ───────────────────

    def on_nav_reach_callback(self, msg: Bool) -> None:
        """导航完成回调 (如导航节点发布到达话题)."""
        if msg.data:
            # 向状态机投递 NAV_DONE 事件
            self.post_event("NAV_DONE", success=True)

    def on_gripper_status_callback(self, msg: UInt8) -> None:
        """机械臂状态回调."""
        # 向状态机投递 GRIPPER_DONE 事件
        self.post_event("GRIPPER_DONE", success=True, command=msg.data)
