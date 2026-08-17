"""
模板: ROS2 决策节点入口 (main_node.py)

继承自 robocon_fsm.ros2.Ros2DecisionNodeBase，负责：
1. 声明与加载 ROS 2 参数到 Blackboard
2. 订阅比赛相关 Topic 并连接到 MyRobotActions 回调
3. 挂载 run_mission 决策主流程
"""

import sys
from std_msgs.msg import Bool, UInt8

from robocon_fsm.ros2 import Ros2DecisionNodeBase, run_decision_node
from my_actions import MyRobotActions
from my_decision import run_mission


class MyRobotDecisionNode(Ros2DecisionNodeBase):
    def __init__(self):
        super().__init__(node_name="my_decision_node")

        # 1. 实例化动作分发器并绑定到节点
        self.actions = MyRobotActions(node=self)
        self.set_action_dispatcher(self.actions)

        # 2. 从 ROS2 参数服务器加载比赛配置
        self._load_parameters()

        # 3. 注册 ROS2 订阅器 (将外部消息分流给 actions 处理)
        self.create_subscription(
            Bool,
            "/robot/nav_reached",
            self.actions.on_nav_reach_callback,
            10
        )
        self.create_subscription(
            UInt8,
            "/robot/gripper_status",
            self.actions.on_gripper_status_callback,
            10
        )

    def _load_parameters(self):
        """声明与加载参数."""
        self.declare_parameter("is_red_side", True)
        self.declare_parameter("loading_pos_x", 2.0)
        self.declare_parameter("loading_pos_y", 1.0)
        self.declare_parameter("scoring_pos_x", 4.0)
        self.declare_parameter("scoring_pos_y", 2.5)

        # 将参数同步存入 Blackboard 黑板中供决策读取
        self.blackboard.is_red_side = self.get_parameter("is_red_side").value
        self.blackboard.loading_pos_x = self.get_parameter("loading_pos_x").value
        self.blackboard.loading_pos_y = self.get_parameter("loading_pos_y").value
        self.blackboard.scoring_pos_x = self.get_parameter("scoring_pos_x").value
        self.blackboard.scoring_pos_y = self.get_parameter("scoring_pos_y").value

    async def run_mission(self):
        """实现基类的 run_mission 虚方法，调用 my_decision 模块中的全场流程."""
        await run_mission(self.fsm, self.actions, self.blackboard)


def main(args=None):
    # 使用框架自带的标准引导函数启动
    run_decision_node(lambda: MyRobotDecisionNode())


if __name__ == "__main__":
    main()
