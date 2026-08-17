# Standard Robot 决策开发模板

本模板是专为参赛队伍准备的开箱即用工程骨架。

## 目录结构说明

```
standard_robot/
├── config/
│   └── params.yaml        # 比赛坐标、超时时间等 ROS2 参数
├── my_actions.py          # 硬件动作分发器（发布指令、接收反馈并向状态机投递事件）
├── my_decision.py         # 比赛核心战术（使用 async/await 编写的线性决策流）
└── main_node.py           # ROS2 节点入口（参数加载、Topic 绑定、启动决策）
```

## 开发指南

1. 在 `my_actions.py` 中定义你机器人的硬件动作
   - 比如 `send_navigate(x, y)`、`send_gripper_command(cmd)`。
   - 在 Topic 回调中通过 `self.post_event("YOUR_EVENT_NAME")` 告知状态机动作已完成。

2. 在 `my_decision.py` 中编排全场决策流程
   - 通过 `await fsm.wait_event("...")`、`await fsm.wait(...)` 组织战术。
   - 所有逻辑从上往下线性执行，调试和排查一目了然。

3. 在 `main_node.py` 中注册 Topic 并启动
   - 继承 `Ros2DecisionNodeBase`，框架会自动搞定多线程执行器与 asyncio 事件循环的安全调度
