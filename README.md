# openclaw-robot

一个自托管的 AI 机器人框架，用 Python 从零写成。参考 [OpenClaw](https://github.com/openclaw/openclaw) 的设计，把 **IM 渠道 + 物理机器人 + Minecraft 游戏内 bot 玩家** 三种形态统一到一个 Agent 框架下。

```
你 (飞书/Telegram/MC 聊天)
 │
 ▼
┌──────────┐     ┌──────────┐     ┌──────────┐
│ Channel  │────▶│ Gateway  │────▶│  Agent   │  ← LLM + 记忆 + 工具
└──────────┘     └──────────┘     └────┬─────┘
   (IM)                                │
┌──────────┐                           ├────▶ chat / 采集 / 建造
│  Robot   │────┐                      │
└──────────┘    │                      ├────▶ Unitree 运动 / 传感器
   (物理)       │                      │
┌──────────┐    │                      └────▶ 物理机器人 SLAM
│   MC     │────┘
└──────────┘
  (游戏内)
```

## 为什么自己写

OpenClaw 主体是 Node.js（pnpm workspace），适合云端/桌面。但树莓派 + Minecraft bot 场景下，Python 生态（`quarry` 协议库、`openai` SDK、`lark-oapi`）更顺手、更轻量。本仓库把 Gateway / Agent / 工具调度那一套用 Python 重写，并提供三种机器人形态的适配器。

## 模块

| 模块 | 作用 | 关键文件 |
| --- | --- | --- |
| `core/` | 通用 Agent 框架：LLM 抽象、SQLite 记忆、工具注册调度、Gateway 控制面 | [core/agent.py](src/openclaw_robot/core/agent.py) |
| `channels/` | IM 渠道适配：Telegram、飞书 | [channels/base.py](src/openclaw_robot/channels/base.py) |
| `robots/` | 物理机器人适配器：抽象接口 + Unitree 桩 | [robots/base.py](src/openclaw_robot/robots/base.py) |
| `minecraft/` | **MC 游戏内 bot 玩家**（重点）：连接服务器、监听聊天、LLM 决策、采集/建造/对话 | [minecraft/bot.py](src/openclaw_robot/minecraft/bot.py) |

## 快速开始

### 安装

```bash
git clone https://github.com/1234567461/openclaw-robot.git
cd openclaw-robot
pip install -e ".[telegram,feishu]"
cp .env.example .env  # 填 LLM_API_KEY 等
```

### 跑 Minecraft bot（重点）

1. 启动一个 MC 服务器（`online-mode=false` 离线模式最简单，可用本仓库的 [auto-deploy-linux](https://github.com/1234567461/auto-deploy-linux) 一键部署）
2. 配置 `.env`：
   ```
   MC_HOST=127.0.0.1
   MC_PORT=25565
   MC_USERNAME=ClawBot
   MC_AUTH=offline
   LLM_API_KEY=sk-xxx
   ```
3. 启动：
   ```bash
   openclaw-mc            # 连接服务器
   openclaw-mc --cli      # 桩模式本地调试（不连服务器）
   ```
4. 游戏里对 bot 说"帮我挖点木头"或"在哪"，bot 会用 LLM 理解 → 调用工具 → 回复。

### 跑本地 Gateway REPL（不接 MC，纯 LLM 对话）

```bash
openclaw-gateway
```

### 接 IM 渠道

```python
from openclaw_robot.core.agent import Agent
from openclaw_robot.core.gateway import Gateway
from openclaw_robot.core.llm import LLM
from openclaw_robot.core.memory import Memory
from openclaw_robot.channels.telegram import TelegramChannel

gw = Gateway(agent=Agent(llm=LLM(), memory=Memory()))
tg = TelegramChannel(gateway=gw)
gw.register("telegram", tg)
tg.run()  # 阻塞监听
```

## 部署到树莓派

```bash
cd deploy/rpi
docker compose up -d
```

配合 [auto-deploy-linux](https://github.com/1234567461/auto-deploy-linux) 的 cloud-init，可在烧卡时就把本服务装好开机自启。

## 状态与路线图

- [x] core Agent 框架（LLM + 记忆 + 工具调度 + Gateway）
- [x] MC bot 协议连接 + 聊天监听 + LLM 决策循环
- [x] MC 技能骨架：采集 / 建造 / 对话（寻路与 chunk 快照为桩，待补）
- [x] Telegram / 飞书渠道骨架
- [x] Unitree 物理机器人适配器接口（运动为桩，待接 SDK）
- [ ] MC A* 寻路 + 世界快照（订阅 chunk data）
- [ ] Unitree SDK 实际运动指令
- [ ] 多 Agent 编排（Orchestrator）

## 测试

```bash
pytest -q          # 14 个测试
ruff check src/ tests/
```

## License

MIT
