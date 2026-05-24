#!/bin/bash
# WSL 启动恢复脚本 — 幂等地拉起 mem0 全栈服务
# 可被 /etc/wsl.conf [boot] command 或 .bashrc 调用
# 安全反复执行，不会重复启动已运行的服务

set -euo pipefail

LOG_FILE="/root/.mem0/boot.log"
PID_FILE="/tmp/mem0-mcp-proxy.pid"
COMPOSE_DIR="/root/mem0/server"
PROXY_DIR="/root/mem0/mcp-proxy"

mkdir -p /root/.mem0

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# ── 阶段 1: 等待 Docker Daemon ─────────────────────────────────
wait_docker() {
    log "等待 Docker daemon..."
    for i in $(seq 1 30); do
        if docker info >/dev/null 2>&1; then
            log "Docker daemon 就绪"
            return 0
        fi
        sleep 2
    done
    log "WARNING: Docker daemon 未就绪，跳过 Docker 服务恢复"
    return 1
}

# ── 阶段 2: 拉起 Docker 容器（幂等） ────────────────────────────
start_containers() {
    if [ ! -d "$COMPOSE_DIR" ]; then
        log "ERROR: compose 目录不存在: $COMPOSE_DIR"
        return 1
    fi
    log "执行 docker compose up -d ..."
    cd "$COMPOSE_DIR"
    if docker compose up -d 2>>"$LOG_FILE"; then
        log "docker compose 执行成功"
    else
        log "WARNING: docker compose 返回非零，栈追踪见日志"
    fi
}

# ── 阶段 3: 等待 API 健康 ──────────────────────────────────────
wait_api() {
    log "等待 mem0 API 就绪 (port 8888)..."
    for i in $(seq 1 30); do
        if curl -sf "http://localhost:8888/memories" >/dev/null 2>&1; then
            log "mem0 API 就绪"
            return 0
        fi
        sleep 2
    done
    log "WARNING: mem0 API 未在 60s 内就绪，继续尝试启动 proxy"
    return 1
}

# ── 阶段 4: 启动 MCP Proxy（带 PID 检查防止重复） ──────────────
start_proxy() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        log "MCP Proxy 已在运行 (PID $(cat "$PID_FILE"))，跳过"
        return 0
    fi

    if ss -tlnp | grep -q ":8765 "; then
        log "MCP Proxy 端口 8765 已在监听，跳过"
        return 0
    fi

    log "启动 MCP Proxy..."
    cd "$PROXY_DIR"
    nohup python3 server.py >> /root/.mem0/mcp-proxy.log 2>&1 &
    PROXY_PID=$!
    echo "$PROXY_PID" > "$PID_FILE"
    log "MCP Proxy 已启动 (PID $PROXY_PID)"
}

# ── 执行 ──────────────────────────────────────────────────────
log "=== wsl-boot.sh 开始 ==="

wait_docker && start_containers
wait_api
start_proxy

log "=== wsl-boot.sh 完成 ==="
