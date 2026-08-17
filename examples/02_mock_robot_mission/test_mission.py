"""
示例 02: 离线虚拟仿真与全场决策测试

演示如何利用 MockActionDispatcher 在本地没有真车、没有 ROS 的情况下，
完整仿真并验证一套复杂的全场比赛策略（包含导航、重试抓取、多事件竞态处理等）。
"""

import asyncio
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from robocon_fsm import FSM, Blackboard
from robocon_fsm.mock import MockActionDispatcher


class SimulatedCompetitionRobot:
    def __init__(self):
        self.fsm = FSM()
        self.mock_act = MockActionDispatcher(self.fsm, auto_ack=True, default_action_duration=0.1)
        self.bb = Blackboard(
            is_red_team=True,
            current_score=0,
            retries=0,
        )

    async def go_to(self, x: float, y: float, theta: float = 0.0, timeout: float = 2.0):
        """通用导航辅助函数: 发送导航 -> 等待到达或避障报警"""
        logging.info("--> [底盘导航] 前往坐标 (x=%.2f, y=%.2f, theta=%.2f)", x, y, theta)
        self.mock_act.simulate_navigation(x, y, theta, duration=0.15)

        # 竞态等待: 要么 NAV_DONE，要么 OBSTACLE 警告
        event = await self.fsm.wait_any("NAV_DONE", "OBSTACLE", timeout=timeout)
        if event.type == "OBSTACLE":
            logging.warning("⚠️ 路上遇到障碍物！触发局部避障重试...")
            await self.fsm.wait(0.1)
            return await self.go_to(x, y, theta, timeout)
        logging.info("<-- [底盘导航] 成功到达 (%.2f, %.2f)", x, y)
        return event

    async def grab_block(self, block_id: int):
        """通用机构抓取动作: 发送指令 -> 等待机构完成"""
        logging.info("--> [机构动作] 启动机械臂抓取物块 #%d...", block_id)
        self.mock_act.simulate_actuator(
            actuator_name="gripper",
            command_id=block_id,
            done_event_type="ARM_DONE",
            duration=0.1,
        )
        await self.fsm.wait_event("ARM_DONE", timeout=1.0)
        logging.info("<-- [机构动作] 机械臂抓取物块 #%d 完成！", block_id)

    async def place_block(self):
        """通用机构放块动作"""
        logging.info("--> [机构动作] 释放并放置物块...")
        self.mock_act.simulate_actuator(
            actuator_name="gripper",
            command_id=0,
            done_event_type="ARM_DONE",
            duration=0.1,
        )
        await self.fsm.wait_event("ARM_DONE", timeout=1.0)
        logging.info("<-- [机构动作] 物块放置完成！")

    async def run_full_mission(self):
        """全场主战术协程"""
        logging.info("==========================================")
        logging.info(">>> 比赛开始！队伍模式: %s", "红方" if self.bb.is_red_team else "蓝方")
        logging.info("==========================================")

        # 阶段 1: 启动并前往取块区
        await self.go_to(1.2, 0.5)

        # 阶段 2: 连续抓取 2 个块
        for block_idx in [1, 2]:
            await self.grab_block(block_idx)
            self.bb.current_score += 10
            logging.info("当前得分: %d 分", self.bb.current_score)

        # 阶段 3: 前往放块区
        await self.go_to(3.5, 2.0)

        # 阶段 4: 并行等待两组传感器稳定
        logging.info("--> [状态同步] 并行等待底盘刹停与激光雷达定位校准...")
        # 模拟外部事件
        async def _trigger_sync():
            await asyncio.sleep(0.05)
            self.fsm.post_event("LIDAR_CALIBRATED")
            self.fsm.post_event("CHASSIS_STABLE")
        asyncio.create_task(_trigger_sync())

        await self.fsm.wait_all("LIDAR_CALIBRATED", "CHASSIS_STABLE", timeout=1.0)
        logging.info("<-- [状态同步] 姿态校准完毕！")

        # 阶段 5: 放块得分
        await self.place_block()
        self.bb.current_score += 30
        logging.info("==========================================")
        logging.info(">>> 比赛结束！最终得分: %d 分", self.bb.current_score)
        logging.info("==========================================")


async def main():
    bot = SimulatedCompetitionRobot()
    bot.fsm.set_loop(asyncio.get_running_loop())
    await bot.run_full_mission()


if __name__ == "__main__":
    asyncio.run(main())
