#!/bin/bash
# Start the mem0 MCP proxy server
# Run this at boot or in your shell profile

export MEM0_API_KEY="m0sk_cnXJbvnid7V2K8on6Y8nB2POCgY2YBCah_452UBRYYs"
export MEM0_USER_ID="pi-agent"
export MEM0_API_URL="http://localhost:8888"

cd /root/mem0/mcp-proxy

# Kill any existing instance bound to this proxy script.
pkill -f "/root/mem0/mcp-proxy/server.py" 2>/dev/null || true
pkill -f "python3 server.py" 2>/dev/null || true
sleep 1

# Start the server
nohup python3 server.py > /root/.mem0/mcp-proxy.log 2>&1 &
echo "mem0 MCP proxy started (PID: $!)"
