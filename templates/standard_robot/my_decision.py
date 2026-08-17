"""
模板: 赛题主决策逻辑 (my_decision.py)

在此文件中编写你队伍机器人的核心全场策略。
全部采用 async/await 线性书写。
"""

import logging
from robocon_fsm import FSM, Blackboard
from my_actions import MyRobotActions

log = logging.getLogger("my_decision")


async def go_to(fsm: FSM, act: MyRobotActions, x: float, y: float, timeout: float = 10.0):
    """
    导航辅助协程: 发送导航指令并等待到达事件
    """
    act.send_navigate(x, y)
    # 等待导航完成事件
    event = await fsm.wait_event("NAV_DONE", timeout=timeout)
    return event


async def grab_object(fsm: FSM, act: MyRobotActions, timeout: float = 3.0):
    """
    抓取辅助协程: 发送抓取指令并等待机械爪到位
    """
    act.send_gripper_command(2)  # 2: 闭合
    event = await fsm.wait_event("GRIPPER_DONE", timeout=timeout)
    return event


async def run_mission(fsm: FSM, act: MyRobotActions, bb: Blackboard):
    """
    全场主任务流程:
    """
    log.info(">>> 机器人比赛决策启动！队伍模式: %s", "红方" if bb.is_red_side else "蓝方")

    # Step 1: 从起点移动到取块区
    log.info("[Phase 1] 前往取块区...")
    await go_to(fsm, act, x=bb.get("loading_pos_x", 2.0), y=bb.get("loading_pos_y", 1.0))

    # Step 2: 抓取物块
    log.info("[Phase 2] 执行抓取...")
    await grab_object(fsm, act)

    # Step 3: 等待 0.5s 确认抓取稳定
    await fsm.wait(0.5)

    # Step 4: 前往放置区
    log.info("[Phase 3] 前往放置区...")
    await go_to(fsm, act, x=bb.get("scoring_pos_x", 4.0), y=bb.get("scoring_pos_y", 2.5))

    # Step 5: 张开机械爪释放物块
    log.info("[Phase 4] 释放物块...")
    act.send_gripper_command(1)  # 1: 张开
    await fsm.wait_event("GRIPPER_DONE", timeout=2.0)

    log.info(">>> 全场任务执行完毕！")
