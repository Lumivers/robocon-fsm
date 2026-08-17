# Robocon Async FSM Framework (robocon-fsm)

[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![ROS 2 Compatible](https://img.shields.io/badge/ROS_2-Humble%20%7C%20Iron%20%7C%20Jazzy-orange.svg)](https://docs.ros.org/)

写在前面：

个人在2026rc中关于决策节点的开发吃了不少亏，包括但不限于：开局不知道写什么，中期和电控交流不够导致一堆屎山，后期快上场了还在改流程。所以我把今年的代码去除2026赛题相关之后，抽象成了一个决策框架，供各位取用。然后也是希望各位品鉴完之后有什么可以改进的地方可以提出来，我深知我的个人能力肯定是不够的，也请各位不吝赐教。个人QQ：2423109915。

推荐阅读个人文章：[RC上位机：从入门到入土](https://lumivers.feishu.cn/wiki/I0S2wsP9DiUsGdkp1kkc9s48ngb)

---

## 为什么需要写框架？

在传统机器人开发中，写上位机代码通常面临以下痛点：
1. 机械电控没调好上位机不知道写什么
2. 决策没有一个具体的框架不知道怎么写
3. 队内交流不够导致各种改需求到最后代码里面一堆死流程
4. 有C++情节所以用c++写的代码，导致每次改代码都得重新编译然后因为协程语法问题导致代码的可读性极其低下

### 框架核心理念：用python的async/await写决策

python因为其语法简单，可读性高，非常适合写决策这种直到比赛前都需要频繁改动的代码。而且其async/await语法完美契合状态机的逻辑。

**代码从上往下读，每一个await都是一次状态转移**

```python
# 示例代码
async def my_robot_mission(fsm: FSM, act: ActionDispatcher, bb: Blackboard):
    # 1. 发送底盘导航，非阻塞等待到达
    act.send_navigate(x=1.5, y=2.0)
    await fsm.wait_event("NAV_DONE", timeout=10.0)

    # 2. 停稳0.2秒
    await fsm.wait(0.2)
    # 我个人是很不喜欢这种等几秒的代码，但是考虑到机械硬件很可能没有加上回调相关传感器，所以这也是有必要的

    # 3. 启动机械臂抓取，等待完成信号
    act.send_gripper(cmd=1)
    await fsm.wait_event("GRIPPER_DONE", timeout=3.0)

    # 4. 竞态等待：要么到达目标点，要么触发避障报警
    event = await fsm.wait_any("NAV_DONE", "OBSTACLE_WARNING", timeout=5.0)
    if event.type == "OBSTACLE_WARNING":
        act.emergency_stop()
```

---

## 架构分层设计

框架是基于**关注点分离**与**控制反转 (IoC)**原则设计的

```
robocon-fsm/
├── src/                         # 【ROS2工作空间源码目录(colcon build一键编译)】
│   ├── robocon_fsm/             #   ├─ 核心决策框架 (Python / ament_python / 可独立 pip 安装)
│   │   ├── core/                #   │   └─ 异步状态机调度引擎 (FSM, Event, ActionBase, Blackboard)
│   │   ├── ros2/                #   │   └─ ROS2原生双线程桥接器与动作辅助
│   │   └── mock/                #   │   └─ 离线虚拟仿真与单测工具
│   └── robot_serial/            #   └─ 通用下位机串口通信驱动包 (C++ / ament_cmake)
│       ├── include/robot_serial/#       └─ CRC16校验、对齐协议包结构体、驱动节点头文件
│       ├── msg/                 #       └─ 通用Command.msg / Ack.msg接口
│       └── src/                 #       └─ 50Hz定时发送与接收解析实现
│
├── templates/                   # 【开箱即用开发模板】
│   └── standard_robot/          # 新队伍直接拷贝此目录即可开始新赛题开发
│       ├── config/params.yaml   # 场地坐标与参数
│       ├── my_actions.py        # 本车硬件接口实现(继承ActionDispatcher)
│       ├── my_decision.py       # 线性全场决策流
│       └── main_node.py         # ROS 2 节点入口(继承Ros2DecisionNodeBase)
│
├── examples/                    # 【教学与参考示例】
│   ├── 01_pure_python_fsm/      # 上手Demo(无 ROS 依赖)
│   └── 02_mock_robot_mission/   # 本地离线全流程仿真与测试Demo
│
└── tests/                       # 【单元测试套件】
    └── run_all_tests.py         # 核心框架原语自动化测试(一键运行)
```

---

## 快速上手

### 1. 体验状态机(无需 ROS 2)
```bash
python examples/01_pure_python_fsm/main.py
```

### 2. 运行离线全场决策仿真(带自动重发与事件竞态)
```bash
python examples/02_mock_robot_mission/test_mission.py
```

### 3. 执行框架单元测试
```bash
python tests/run_all_tests.py
```

---

## 新队伍开发流程

只需拷贝 `templates/standard_robot/` 到你的项目中：

1. **Step 1 (`my_actions.py`)**：定义你的机器人动作（如 `send_navigate`, `send_arm`），并在 ROS 2 订阅回调中调用 `self.post_event("EVENT_NAME")` 告知状态机。
2. **Step 2 (`my_decision.py`)**：使用 `await fsm.wait_event(...)` 编排比赛策略。
3. **Step 3 (`main_node.py`)**：启动节点，框架会自动处理 ROS 2 多线程回调与异步协程之间的线程安全桥接。

---

## 核心 API 快速参考

| API 原语 | 说明 |
|---|---|
| `await fsm.wait(seconds)` | 异步非阻塞延时等待 |
| `await fsm.wait_event("NAME", timeout=...)` | 等待指定事件到达，支持超时 |
| `await fsm.wait_event(lambda e: ...)` | 谓词匹配：按事件内容/指令码过滤 |
| `await fsm.wait_any("A", "B", timeout=...)` | 等待任意一个事件到达 |
| `await fsm.wait_all("A", "B", timeout=...)` | 并行等待所有事件全部到达 |
| `fsm.post_event("NAME", success=..., data=...)` | 线程安全地从任意线程投递事件 |
| `await act.retry_until_ack(...)` | 下位机可靠性重发机制 (自动超时重试) |
| `bb = Blackboard()` | 全局黑板，跨模块共享红蓝方/比赛得分等状态 |

---

## 环境依赖与安装 (Requirements & Installation)

### 1. 基础环境
- **Python**: `>= 3.8` (核心调度引擎基于 Python 原生asyncio，无强制第三方依赖)
- **操作系统**: Linux (Ubuntu 22.04 / 24.04 推荐) / Windows 10/11 / macOS

### 2. ROS 2 环境 (真车运行与驱动支持)
- **ROS 2 版本**: Humble / Iron / Jazzy
- **ROS 2 依赖包**:
  - `rclpy`, `std_msgs`, `geometry_msgs`, `nav_msgs`
  - `serial_driver` (用于 C++ 串口驱动编译，可通过 `sudo apt install ros-${ROS_DISTRO}-serial-driver` 安装)

### 3. 安装与构建

#### 模式 A: 作为 Python 库安装 (用于个人电脑开发/离线战术仿真)
```bash
pip install -e .
# 或安装可选测试依赖
pip install -r requirements.txt
```

#### 模式 B: 作为 ROS 2 工作空间编译 (用于真车工控机部署)
```bash
# 在工作空间根目录下
colcon build --symlink-install
source install/setup.bash
```