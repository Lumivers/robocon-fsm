"""
示例 01: 纯 Python 异步状态机极简上手

无需 ROS 2，无需硬件，直接用 python main.py 即可运行。
带你快速体会 "用 async/await 写决策" 的核心魅力。
"""

import asyncio
import os
import sys

# 导入框架
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from robocon_fsm import FSM, Event


async def simulated_hardware_driver(fsm: FSM):
    """模拟外部硬件（如下位机、传感器）在后台异步发送完成信号."""
    print("  [硬件驱动] 正在导航前往取球区 (1.5m, 2.0m)...")
    await asyncio.sleep(1.0)
    print("  [硬件驱动] 收到底盘到达信号！向状态机投递 NAV_DONE 事件。")
    fsm.post_event("NAV_DONE", success=True, data={"x": 1.5, "y": 2.0})

    await asyncio.sleep(0.8)
    print("  [硬件驱动] 机械臂抓取完成！向状态机投递 ARM_DONE 事件。")
    fsm.post_event("ARM_DONE", success=True)


async def robot_decision_main(fsm: FSM):
    """
    机器人主决策流程:
    代码从上往下读，每个 await 就是一次状态切换，完全不需要 step 计数器和复杂的 switch-case！
    """
    print("\n>>> 比赛开始：全自动决策启动！")

    print("[Step 1] 指令：底盘导航前往取物区...")
    # 等待底盘到达事件（支持超时控制）
    event = await fsm.wait_event("NAV_DONE", timeout=3.0)
    print(f"[Step 1 完成] 成功到达目标点: {event.data}")

    print("\n[Step 2] 指令：等待 0.2 秒稳定车身...")
    await fsm.wait(0.2)

    print("\n[Step 3] 指令：启动机械臂抓取...")
    arm_event = await fsm.wait_event("ARM_DONE", timeout=2.0)
    print(f"[Step 3 完成] 机械臂状态: success={arm_event.success}")

    print("\n>>> 全场任务顺利完成！\n")


async def main():
    fsm = FSM()
    fsm.set_loop(asyncio.get_running_loop())

    # 同时启动硬件模拟协程与主决策协程
    await asyncio.gather(
        robot_decision_main(fsm),
        simulated_hardware_driver(fsm),
    )


if __name__ == "__main__":
    asyncio.run(main())
