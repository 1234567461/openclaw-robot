# openclaw-robot

一个自托管的 AI 机器人框架，用 Python 从零写成。参考 [OpenClaw](https://github.com/openclaw/openclaw) 的设计，把 **IM 渠道 + 物理机器人 + Minecraft 游戏内 bot 玩家** 三种形态统一到一个 Agent 框架下。支持 **网页 / IM** 两种聊天方式，AI 可 **本地或云端** 部署。

```
你 (网页 / 飞书 / Telegram / MC 聊天)
 │
 ▼
┌──────────┐     ┌──────────┐     ┌──────────┐
│ Channel  │────▶│ Gateway  │────▶│  Agent   │  ← LLM + 记忆 + 工具
└──────────┘     └──────────┘     └────┬─────┘
   (Web/IM)                            │
┌──────────┐                           ├────▶ chat / 采集 / 建造
│  Robot   │────┐                      │
└──────────┘    │                      ├────▶ Unitree 运动 / 传感器
   (物理)       │                      │
┌──────────┐    │                      └────▶ 多 Agent 编排 (Orchestrator)
│   MC     │────┘
└──────────┘
  (游戏内)

        LLM 后端：OpenAI / DeepSeek（云端）· Ollama / vLLM（本地）
```

## 为什么自己写

OpenClaw 主体是 Node.js（pnpm workspace），适合云端/桌面。但树莓派 + Minecraft bot 场景下，Python 生态（`quarry` 协议库、`openai` SDK、`lark-oapi`）更顺手、更轻量。本仓库把 Gateway / Agent / 工具调度那一套用 Python 重写，并提供三种机器人形态的适配器。

## 模块

| 模块 | 作用 | 关键文件 |
| --- | --- | --- |
| `core/` | 通用 Agent 框架：LLM 抽象、SQLite 记忆、工具注册调度、Gateway 控制面、多 Agent 编排 | [core/agent.py](src/openclaw_robot/core/agent.py) |
| `channels/` | 聊天渠道适配：**Web**、Telegram、飞书 | [channels/web.py](src/openclaw_robot/channels/web.py) |
| `robots/` | 物理机器人适配器：抽象接口 + Unitree 桩 | [robots/base.py](src/openclaw_robot/robots/base.py) |
| `minecraft/` | **MC 游戏内 bot 玩家**（重点）：连接服务器、监听聊天、LLM 决策、采集/建造/对话 | [minecraft/bot.py](src/openclaw_robot/minecraft/bot.py) |

## 快速开始

### 安装

#### 方式一：一键部署脚本（推荐，会自动问你本地还是云端 AI）

```bash
git clone https://github.com/1234567461/openclaw-robot.git
cd openclaw-robot
./deploy.sh
```

脚本会用人话一步步引导你选：
1. 跑网页聊天还是 Minecraft 机器人
2. AI 用本地（Ollama，自动下模型，可选模板或自定义模型名）还是云端（填 API Key）
3. 自动写好 `.env`、装好依赖、启动服务

#### 方式二：手动

```bash
git clone https://github.com/1234567461/openclaw-robot.git
cd openclaw-robot
pip install -e ".[web,telegram,feishu]"
cp .env.example .env  # 填 LLM_API_KEY 等
```

### 配置 AI（本地 / 云端）

切换后端只需改环境变量，代码不用动。`.env` 示例：

```dotenv
# 云端（任选一个）
LLM_API_BASE=https://api.openai.com/v1      # OpenAI
LLM_API_KEY=sk-xxx
LLM_MODEL=gpt-4o-mini

# 或 DeepSeek
LLM_API_BASE=https://api.deepseek.com
LLM_API_KEY=sk-xxx
LLM_MODEL=deepseek-chat

# 本地（任选一个，key 任意非空）
LLM_API_BASE=http://localhost:11434/v1      # Ollama
LLM_API_KEY=ollama
LLM_MODEL=qwen2.5:7b

LLM_API_BASE=http://localhost:8000/v1      # vLLM
LLM_API_KEY=EMPTY
LLM_MODEL=qwen2.5-7b
```

也可在代码里用预设工厂：

```python
from openclaw_robot.core.llm import LLM

llm_cloud  = LLM.create("openai",   api_key="sk-xxx")     # 云端
llm_local  = LLM.create("ollama")                          # 本地（key 自动填）
llm_local2 = LLM.create("vllm")                             # 本地
llm_cloud2 = LLM.create("deepseek", api_key="sk-xxx")      # 云端

llm.is_local  # True / False，判断当前后端是否本地部署
```

预设覆盖 `openai` / `deepseek` / `ollama` / `vllm` / `siliconflow`。

### 聊天方式一：网页（推荐快速体验）

```bash
openclaw-web          # 启动 FastAPI + WebSocket 服务
```

浏览器打开 `http://localhost:8080` 即可和机器人对话。一个标签页 = 一个会话，支持实时双向消息、自动重连。`WEB_HOST` / `WEB_PORT` 可改监听地址。

也可在程序里挂到自己的 Gateway：

```python
from openclaw_robot.channels.web import WebChannel

web = WebChannel(gateway=gw, port=8080)
gw.register("web", web)
web.run()
```

### 聊天方式二：跑本地 Gateway REPL（CLI 对话）

```bash
openclaw-gateway
```

### 聊天方式三：接 IM 渠道

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
4. 游戏里对 bot 说"帮我挖点木头"或"在哪"，bot 会用 LLM 理解 → 调用工具（带世界快照 + A* 寻路）→ 回复。

### 多 Agent 编排

Orchestrator 根据任务描述路由到专门 Agent，每个 Agent 有自己的工具集与系统提示：

```python
from openclaw_robot.core.orchestrator import build_default_orchestrator, Orchestrator
from openclaw_robot.core.llm import LLM

orch = Orchestrator(llm=LLM())
orch.add_specialist("miner",   "负责采集和挖掘",   miner_agent)
orch.add_specialist("builder", "负责建造",          builder_agent)
orch.add_specialist("chat",    "负责与玩家对话",     chat_agent)

reply = orch.delegate("帮我挖 10 个石头", "web", "user1")
# → [miner] 已挖到 10 个石头...
```

`build_default_orchestrator(llm)` 提供开箱即用的对话 specialist。

## 部署到树莓派

```bash
cd deploy/rpi
docker compose up -d
```

配合 [auto-deploy-linux](https://github.com/1234567461/auto-deploy-linux) 的 cloud-init，可在烧卡时就把本服务装好开机自启。

## 状态与路线图

- [x] core Agent 框架（LLM + 记忆 + 工具调度 + Gateway）
- [x] MC bot 协议连接 + 聊天监听 + LLM 决策循环
- [x] MC 世界快照（World 类：方块查询 / 最近方块 / 可通行判定）
- [x] MC A* 寻路（3D 网格 + 跳跃/下落处理）
- [x] MC 技能骨架：采集 / 建造 / 对话
- [x] **Web 聊天渠道**（FastAPI + WebSocket + 前端页面）
- [x] Telegram / 飞书渠道骨架
- [x] Unitree 物理机器人适配器（`unitree_sdk2_python` 实接：Move/RecoveryStand/StandDown/GetState，无硬件时自动降级桩模式）
- [x] **多 Agent 编排**（Orchestrator + 路由）
- [x] **LLM 本地 / 云端部署适配**（预设工厂 + `is_local`）
- [x] **Unitree SDK 实际运动指令接入**（unitree_sdk2_python SportClient）
- [x] **MC bot chunk 订阅与寻路联调**（palette + packed bit array 解析 → World → A*）
- [x] **一键部署脚本**（人话交互，自动选本地/云端 AI 并下载模型）

## 测试

```bash
pytest -q          # 56 个测试（含 Web 渠道、LLM 部署、chunk 解析、寻路）
ruff check src/ tests/
```

## License

MIT
