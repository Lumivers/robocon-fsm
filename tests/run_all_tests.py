"""
==============================================================================
Robocon Async FSM Framework — 框架核心自动化单元测试套件
==============================================================================
本脚本用于全方位测试 robocon_fsm 状态机调度引擎的各项核心机制是否正常。
基于 Python 内置的 unittest 和 asyncio 实现，无需安装任何第三方库，直接运行即可。

测试项包含:
  1. 单事件正常到达与唤醒 (test_fsm_wait_event_success)
  2. 事件超时保护与异常抛出 (test_fsm_wait_event_timeout)
  3. 竞态等待: 多事件谁先到响应谁 (test_fsm_wait_any)
  4. 并行等待: 多个事件全部完成才继续 (test_fsm_wait_all)
  5. 复杂谓词匹配: 按功能码/条件过滤事件 (test_predicate_matcher)
  6. 下位机丢包可靠性重发机制 (test_retry_until_ack)
  7. 全局比赛黑板数据共享 (test_blackboard)
==============================================================================
"""

import asyncio
import os
import sys
import unittest

# 将源码目录添加到模块搜索路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from robocon_fsm import FSM, Event, Blackboard
from robocon_fsm.core.fsm import FSMTimeoutError
from robocon_fsm.mock import MockActionDispatcher


class TestRoboconFSM(unittest.IsolatedAsyncioTestCase):
    """FSM 核心调度原语单元测试集合."""

    async def test_fsm_wait_event_success(self):
        """
        【测试 1】基础事件等待机制:
        验证主协程在 await fsm.wait_event 时挂起，当后台子任务投递匹配事件后，能否立刻唤醒并拿到数据。
        """
        fsm = FSM()
        fsm.set_loop(asyncio.get_running_loop())

        # 模拟后台硬件驱动/ROS回调在 20ms 后发来 "NAV_DONE" 到位信号
        async def mock_hardware_post():
            await asyncio.sleep(0.02)
            fsm.post_event("NAV_DONE", success=True, data={"x": 1.5, "y": 2.0})

        asyncio.create_task(mock_hardware_post())

        # 主协程等待 NAV_DONE 到达
        ev = await fsm.wait_event("NAV_DONE", timeout=1.0)
        self.assertEqual(ev.type, "NAV_DONE")
        self.assertTrue(ev.success)
        self.assertEqual(ev.data, {"x": 1.5, "y": 2.0})

    async def test_fsm_wait_event_timeout(self):
        """
        【测试 2】超时保护机制:
        验证当等待的事件在指定超时时间内（0.03s）没有到达时，系统能否准时抛出 FSMTimeoutError 异常，
        避免机器人程序在场上因硬件掉电或丢包而无限死等卡死。
        """
        fsm = FSM()
        fsm.set_loop(asyncio.get_running_loop())

        # 等待一个永远不会到达的事件，期望抛出超时异常
        with self.assertRaises(FSMTimeoutError):
            await fsm.wait_event("NEVER_ARRIVES", timeout=0.03)

    async def test_fsm_wait_any(self):
        """
        【测试 3】竞态等待机制 (wait_any):
        常用于比赛中的“底盘正常到达 VS 遇到障碍物报警”竞态场景。
        验证只要其中任意一个事件先到达，状态机就会立刻响应并返回该事件。
        """
        fsm = FSM()
        fsm.set_loop(asyncio.get_running_loop())

        # 模拟路上突然触发了 "OBSTACLE_WARNING" 避障报警
        async def mock_obstacle_trigger():
            await asyncio.sleep(0.02)
            fsm.post_event("OBSTACLE_WARNING", success=False)

        asyncio.create_task(mock_obstacle_trigger())

        # 谁先到就响应谁
        ev = await fsm.wait_any("NAV_DONE", "OBSTACLE_WARNING", timeout=1.0)
        self.assertEqual(ev.type, "OBSTACLE_WARNING")
        self.assertFalse(ev.success)

    async def test_fsm_wait_all(self):
        """
        【测试 4】并行等待机制 (wait_all):
        常用于需要多个机构或多个传感器同时准备就绪的场景（如：机械臂回位 + 底盘停稳）。
        验证两个事件均到达后才继续执行。
        """
        fsm = FSM()
        fsm.set_loop(asyncio.get_running_loop())

        # 模拟机械臂 10ms 完成
        async def mock_arm_done():
            await asyncio.sleep(0.01)
            fsm.post_event("ARM_DONE")

        # 模拟底盘 20ms 完成
        async def mock_chassis_done():
            await asyncio.sleep(0.02)
            fsm.post_event("CHASSIS_DONE")

        asyncio.create_task(mock_arm_done())
        asyncio.create_task(mock_chassis_done())

        # 并行等待全部到达
        events = await fsm.wait_all("ARM_DONE", "CHASSIS_DONE", timeout=1.0)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].type, "ARM_DONE")
        self.assertEqual(events[1].type, "CHASSIS_DONE")

    async def test_predicate_matcher(self):
        """
        【测试 5】高级条件过滤匹配 (Predicate Matcher):
        验证事件不仅可以按名字字符串匹配，还可以传入 lambda 条件函数按 command 指令码等属性精准过滤。
        """
        fsm = FSM()
        fsm.set_loop(asyncio.get_running_loop())

        async def mock_ack_sequence():
            await asyncio.sleep(0.01)
            fsm.post_event("ACK", command=0x01)  # 不是我们想要的 0x05 指令响应
            await asyncio.sleep(0.01)
            fsm.post_event("ACK", command=0x05)  # 匹配的目标响应

        asyncio.create_task(mock_ack_sequence())

        # 只等待 command 为 0x05 的 ACK 事件
        ev = await fsm.wait_event(lambda e: e.type == "ACK" and e.command == 0x05, timeout=1.0)
        self.assertEqual(ev.type, "ACK")
        self.assertEqual(ev.command, 0x05)

    async def test_retry_until_ack(self):
        """
        【测试 6】下位机可靠性超时自动重发机制 (retry_until_ack):
        验证当下位机前两次丢包未回复 ACK 时，驱动层会自动重试发送，直到第 3 次收到 ACK 后成功返回。
        """
        fsm = FSM()
        fsm.set_loop(asyncio.get_running_loop())

        mock_act = MockActionDispatcher(fsm=fsm, auto_ack=False)
        send_count = 0

        # 模拟发包函数：前 2 次不回 ACK，第 3 次发送才回 ACK
        def do_send():
            nonlocal send_count
            send_count += 1
            if send_count >= 3:
                fsm.post_event("ACK", command=0x09)

        # 启动重发机制（每次超时 0.03s，最多重试 5 次）
        ev = await mock_act.retry_until_ack(
            send_fn=do_send,
            ack_matcher=lambda e: e.type == "ACK" and e.command == 0x09,
            timeout=0.03,
            max_retries=5,
            interval=0.01,
        )
        self.assertEqual(ev.type, "ACK")
        self.assertEqual(send_count, 3)

    def test_blackboard(self):
        """
        【测试 7】全局黑板状态读写 (Blackboard):
        验证跨模块共享数据容器是否支持动态属性读写、键值提取与状态修改。
        """
        bb = Blackboard(is_red_side=True, score=0)
        self.assertTrue(bb.is_red_side)
        self.assertEqual(bb.score, 0)

        # 动态修改与追加数据
        bb.score += 10
        bb.target_pos = (1.0, 2.0)
        self.assertEqual(bb.score, 10)
        self.assertEqual(bb.get("target_pos"), (1.0, 2.0))


if __name__ == "__main__":
    unittest.main()
