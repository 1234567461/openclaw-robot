FROM python:3.11-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 先装依赖（利用缓存层）
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[telegram,feishu]"

# 复制源码
COPY src/ ./src/
COPY README.md LICENSE ./

# 默认启动 MC bot
ENTRYPOINT ["openclaw-mc"]
