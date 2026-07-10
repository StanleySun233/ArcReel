# ============================================================
# Stage 1: 构建前端
# ============================================================
FROM node:22-slim AS frontend-builder

WORKDIR /build/frontend

# 启用 corepack；pnpm 版本由 frontend/package.json 的 packageManager 字段固定
# 关闭交互式下载确认，否则 docker build 这种非 TTY 环境会卡在
# "Corepack is about to download ..." 直到超时
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable

# 先复制依赖文件，利用缓存（corepack 按 packageManager 字段自动下载对应 pnpm）
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# 复制前端源码并构建
COPY frontend/ ./
RUN pnpm build

ARG ARCREEL_BASE_IMAGE=registry.kr777.top/arcreel-base:private-dev

FROM ${ARCREEL_BASE_IMAGE} AS production

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --no-dev --no-install-project --frozen

# 复制应用代码
COPY lib/ lib/
COPY server/ server/
COPY alembic/ alembic/
COPY alembic.ini ./
COPY scripts/ scripts/
COPY agent_runtime_profile/ agent_runtime_profile/
COPY public/ public/

# 复制前端构建产物
COPY --from=frontend-builder /build/frontend/dist/ frontend/dist/

# 创建运行时目录
RUN mkdir -p projects vertex_keys

# 暴露端口
EXPOSE 1241

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:1241/health || exit 1

# 启动命令
CMD ["uv", "run", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "1241"]
