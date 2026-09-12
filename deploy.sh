#!/usr/bin/env bash
# ============================================================
#  openclaw-robot 一键部署脚本
#  人话版：跟着提示走，不用懂技术也能跑起来
# ============================================================
set -e

# ---------- 颜色 & 工具函数 ----------
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[提示]${NC} $*" >&2; }
ok()      { echo -e "${GREEN}[成功]${NC} $*" >&2; }
warn()    { echo -e "${YELLOW}[注意]${NC} $*" >&2; }
err()     { echo -e "${RED}[错误]${NC} $*" >&2; }

# ask "问题" "默认值"  -> 返回用户输入（回车用默认值）
ask() {
  local prompt="$1" default="$2" ans
  if [ -n "$default" ]; then
    read -rp "$(echo -e "${CYAN}?${NC} $prompt ${YELLOW}[$default]${NC}: ")" ans
    echo "${ans:-$default}"
  else
    read -rp "$(echo -e "${CYAN}?${NC} $prompt: ")" ans
    echo "$ans"
  fi
}

# choose "问题" "选项1" "选项2" ... -> 仅把选中项输出到 stdout（菜单走 stderr）
choose() {
  local prompt="$1"; shift
  local options=("$@")
  echo -e "${CYAN}?${NC} $prompt" >&2
  for i in "${!options[@]}"; do
    echo -e "   ${GREEN}$((i+1)))${NC} ${options[$i]}" >&2
  done
  local n
  while true; do
    read -rp "$(echo -e "${CYAN}?${NC} 输入数字 [1-${#options[@]}]: ")" n
    if [[ "$n" =~ ^[0-9]+$ ]] && [ "$n" -ge 1 ] && [ "$n" -le "${#options[@]}" ]; then
      echo "${options[$((n-1))]}"
      return 0
    fi
    err "请输入 1 到 ${#options[@]} 之间的数字"
  done
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ============================================================
#  开场
# ============================================================
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   openclaw-robot  一键部署   （跟着提示走就行）            ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================
#  1. 选跑哪个服务
# ============================================================
info "先选一个你想跑的功能："
SERVICE=$(choose "跑哪个？" \
  "网页聊天（推荐，浏览器里就能和机器人聊）" \
  "Minecraft 机器人（游戏里的 AI 玩家）" \
  "两个都跑")

case "$SERVICE" in
  "网页聊天"*)                MODE="web" ;;
  "Minecraft"*)               MODE="mc" ;;
  "两个都跑"*)                MODE="both" ;;
esac

# ============================================================
#  2. 选 AI 后端：本地 or 云端
# ============================================================
echo ""
info "AI 大脑用本地还是云端？"
AI_TYPE=$(choose "AI 部署方式？" \
  "本地部署（不用联网，但要下载模型，占硬盘/显存）" \
  "云端部署（需要 API Key，速度快，按量计费）")

echo ""
# ---------- 本地部署 ----------
if [[ "$AI_TYPE" == "本地"* ]]; then
  info "好，用本地 AI。需要装 Ollama 来跑模型。"

  # 装 Ollama
  if command -v ollama &>/dev/null; then
    ok "检测到你已经装了 Ollama，跳过安装。"
  else
    warn "没检测到 Ollama，现在装（需要 sudo 权限）。"
    curl -fsSL https://ollama.com/install.sh | sh || {
      err "Ollama 安装失败。你可以手动装：https://ollama.com/download"
      exit 1
    }
    ok "Ollama 装好了。"
  fi

  # 启动 Ollama 服务
  if ! pgrep -x ollama &>/dev/null; then
    info "启动 Ollama 后台服务..."
    ollama serve >/tmp/ollama.log 2>&1 &
    sleep 3
  fi

  # 选模型
  echo ""
  info "选个模型。模板是常见的，也可以自己输名字（比如 llama3.1:8b）。"
  info "模型越大越聪明，但下载越慢、占资源越多。"

  MODEL_CHOICE=$(choose "用哪个模型？" \
    "qwen2.5:7b（70亿参数，中文好，推荐）" \
    "qwen2.5:14b（140亿参数，更聪明，吃显存）" \
    "llama3.1:8b（80亿参数，英文好）" \
    "phi3:3.8b（38亿参数，轻快）" \
    "自己输入模型名")

  case "$MODEL_CHOICE" in
    "qwen2.5:7b"*)   MODEL="qwen2.5:7b" ;;
    "qwen2.5:14b"*)  MODEL="qwen2.5:14b" ;;
    "llama3.1:8b"*)  MODEL="llama3.1:8b" ;;
    "phi3:3.8b"*)    MODEL="phi3:3.8b" ;;
    "自己输入"*)      MODEL=$(ask "输入模型名（要 Ollama 支持的，去 ollama.com/library 查）" "qwen2.5:7b") ;;
  esac

  # 拉模型
  echo ""
  info "开始下载模型 $MODEL（第一次比较慢，耐心等）..."
  ollama pull "$MODEL" || { err "模型下载失败，检查网络或模型名。"; exit 1; }
  ok "模型 $MODEL 下载完成。"

  # 写 .env（本地）
  cat > .env <<EOF
# ===== LLM 后端：本地 Ollama =====
LLM_API_BASE=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=$MODEL

# ===== Web 聊天渠道 =====
WEB_HOST=0.0.0.0
WEB_PORT=8080

# ===== Minecraft bot（RCON，需在 server.properties 开启 enable-rcon=true）=====
MC_HOST=127.0.0.1
MC_USERNAME=ClawBot
MC_RCON_PORT=25575
MC_RCON_PASSWORD=
EOF

  ok "环境配置已写入 .env（本地 Ollama + 模型 $MODEL）"

# ---------- 云端部署 ----------
else
  info "好，用云端 AI。需要你提供 API Key。"

  CLOUD_PROVIDER=$(choose "用哪家云端？" \
    "DeepSeek（便宜，中文好，推荐）" \
    "OpenAI（GPT，最强但贵）" \
    "硅基流动 SiliconFlow（国内，模型多）" \
    "其他 OpenAI 兼容接口")

  case "$CLOUD_PROVIDER" in
    "DeepSeek"*)
      API_BASE="https://api.deepseek.com"
      DEFAULT_MODEL="deepseek-chat"
      KEY_HINT="去 https://platform.deepseek.com 申请"
      ;;
    "OpenAI"*)
      API_BASE="https://api.openai.com/v1"
      DEFAULT_MODEL="gpt-4o-mini"
      KEY_HINT="去 https://platform.openai.com 申请"
      ;;
    "硅基流动"*)
      API_BASE="https://api.siliconflow.cn/v1"
      DEFAULT_MODEL="Qwen/Qwen2.5-7B-Instruct"
      KEY_HINT="去 https://cloud.siliconflow.cn 申请"
      ;;
    "其他"*)
      API_BASE=$(ask "输入 API Base URL（必须是 OpenAI 兼容的，比如 https://xxx.com/v1）")
      DEFAULT_MODEL=$(ask "输入默认模型名" "gpt-4o-mini")
      KEY_HINT="向你的服务商申请"
      ;;
  esac

  echo ""
  warn "API Key 获取：$KEY_HINT"
  API_KEY=$(ask "输入你的 API Key")
  if [ -z "$API_KEY" ]; then
    err "API Key 不能为空。"
    exit 1
  fi

  MODEL=$(ask "用哪个模型（回车用默认 $DEFAULT_MODEL）" "$DEFAULT_MODEL")

  # 写 .env（云端）
  cat > .env <<EOF
# ===== LLM 后端：云端 $CLOUD_PROVIDER =====
LLM_API_BASE=$API_BASE
LLM_API_KEY=$API_KEY
LLM_MODEL=$MODEL

# ===== Web 聊天渠道 =====
WEB_HOST=0.0.0.0
WEB_PORT=8080

# ===== Minecraft bot（RCON，需在 server.properties 开启 enable-rcon=true）=====
MC_HOST=127.0.0.1
MC_USERNAME=ClawBot
MC_RCON_PORT=25575
MC_RCON_PASSWORD=
EOF

  ok "环境配置已写入 .env（云端 $CLOUD_PROVIDER + 模型 $MODEL）"
fi

# ============================================================
#  3. 安装 Python 依赖
# ============================================================
echo ""
info "安装 openclaw-robot 及其依赖..."
if [ ! -d "venv" ]; then
  warn "没检测到虚拟环境，建议用 venv 隔离。"
  USE_VENV=$(choose "要不要创建虚拟环境？" "要（推荐）" "不要，直接装到系统")
  if [[ "$USE_VENV" == "要"* ]]; then
    python3 -m venv venv
    # shellcheck disable=SC1091
    source venv/bin/activate
    ok "虚拟环境已创建并激活：venv/"
  fi
fi

pip install -e ".[web,telegram,feishu]" 2>&1 | tail -5 || {
  err "依赖安装失败，检查 Python 版本（需 3.11+）。"
  exit 1
}
ok "依赖安装完成。"

# ============================================================
#  4. 启动服务
# ============================================================
echo ""
echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
ok "部署完成！准备启动..."
echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
echo ""

if [[ "$MODE" == "web" || "$MODE" == "both" ]]; then
  info "启动网页聊天服务：openclaw-web"
  info "浏览器打开 → http://localhost:8080"
  echo ""
  if [[ "$MODE" == "both" ]]; then
    openclaw-web &
    WEB_PID=$!
    info "网页服务已后台启动（PID $WEB_PID）"
  else
    exec openclaw-web
  fi
fi

if [[ "$MODE" == "mc" || "$MODE" == "both" ]]; then
  echo ""
  warn "注意：Minecraft 机器人需要一个运行中的 MC 服务器（任意版本 1.9+）。"
  warn "服务器需在 server.properties 开启 RCON：enable-rcon=true"
  MC_HOST=$(ask "MC 服务器地址" "127.0.0.1")
  MC_USERNAME=$(ask "机器人在游戏里的名字" "ClawBot")
  MC_RCON_PASSWORD=$(ask "RCON 密码（server.properties 里的 rcon.password）")

  sed -i "s/^MC_HOST=.*/MC_HOST=$MC_HOST/" .env
  sed -i "s/^MC_USERNAME=.*/MC_USERNAME=$MC_USERNAME/" .env
  sed -i "s/^MC_RCON_PASSWORD=.*/MC_RCON_PASSWORD=$MC_RCON_PASSWORD/" .env

  info "启动 Minecraft 机器人..."
  exec openclaw-mc
fi
