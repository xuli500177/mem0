"""
Lightweight MCP proxy server for self-hosted Mem0.

Exposes mem0 REST API (localhost:8888) as MCP tools for Claude Code.
Uses Streamable HTTP transport on port 8765.
"""

import os
import re
import httpx
from mcp.server.fastmcp import FastMCP

MEM0_API_URL = os.environ.get("MEM0_API_URL", "http://localhost:8888")
MEM0_API_KEY = os.environ.get("MEM0_API_KEY", "")
DEFAULT_USER_ID = os.environ.get("MEM0_USER_ID", "pi-agent")
ENABLE_RERANK = os.environ.get("MEM0_RERANK", "true").lower() in ("true", "1", "yes")

mcp = FastMCP(
    "mem0",
    instructions="Mem0 memory tools backed by self-hosted server",
    host="0.0.0.0",
    port=8765,
    stateless_http=True,
)


def _headers():
    return {"X-API-Key": MEM0_API_KEY, "Content-Type": "application/json"}


@mcp.tool()
def add_memory(text: str, user_id: str = "", infer: bool = True) -> str:
    """Add a new memory. Store user preferences, decisions, or any useful information."""
    uid = user_id or DEFAULT_USER_ID
    payload = {"messages": [{"role": "user", "content": text}], "user_id": uid, "infer": infer}
    with httpx.Client(timeout=30) as c:
        r = c.post(f"{MEM0_API_URL}/memories", json=payload, headers=_headers())
        r.raise_for_status()
        data = r.json()
    results = data.get("results", data.get("memories", []))
    if isinstance(results, list):
        ids = [m.get("id", "?") for m in results]
        return f"Stored {len(ids)} memory/memories: {', '.join(ids)}"
    return str(data)


@mcp.tool()
def search_memories(query: str, user_id: str = "", limit: int = 20, filters: dict = None) -> str:
    """Search stored memories by query. Returns matching memories with scores.
    PRO TIP: Use Query Expansion. Provide bilingual synonyms in the query (e.g., '手机语音 phone voice input') to maximize retrieval success."""
    uid = user_id or DEFAULT_USER_ID
    
    # Auto-expand query for BM25 to handle paths and hyphenated terms gracefully
    cleaned_query = re.sub(r'[\-_\\/]', ' ', query)
    if cleaned_query != query and cleaned_query.strip():
        query = f"{query} {cleaned_query}"

    payload = {"query": query, "user_id": uid, "limit": limit}
    if ENABLE_RERANK:
        payload["rerank"] = True
    if filters:
        payload["filters"] = filters
    with httpx.Client(timeout=120) as c:
        r = c.post(f"{MEM0_API_URL}/search", json=payload, headers=_headers())
        r.raise_for_status()
        data = r.json()
    results = data.get("results", [])
    if not results:
        return "No memories found."
    # Sort by rerank_score if available, otherwise by score
    results.sort(key=lambda x: x.get("rerank_score", x.get("score", 0)), reverse=True)
    lines = []
    for m in results:
        score = m.get("rerank_score", m.get("score", "?"))
        mem = m.get("memory", "")
        mid = m.get("id", "?")
        meta = m.get("metadata", {})
        lines.append(f"[{score}] {mem}  (id={mid}, metadata={meta})")
    return "\n".join(lines)


@mcp.tool()
def get_memories(user_id: str = "", limit: int = 100) -> str:
    """List all stored memories for the user."""
    uid = user_id or DEFAULT_USER_ID
    with httpx.Client(timeout=30) as c:
        r = c.get(f"{MEM0_API_URL}/memories", params={"user_id": uid, "limit": limit}, headers=_headers())
        r.raise_for_status()
        data = r.json()
    results = data.get("results", data.get("memories", []))
    if not results:
        return "No memories found."
    lines = []
    for m in results:
        mid = m.get("id", "?")
        mem = m.get("memory", "")
        meta = m.get("metadata", {})
        created = m.get("created_at", "")
        lines.append(f"- [{mid}] {mem}  (metadata={meta}, created={created})")
    return "\n".join(lines)


@mcp.tool()
def get_memory(memory_id: str) -> str:
    """Retrieve a single memory by its ID."""
    with httpx.Client(timeout=30) as c:
        r = c.get(f"{MEM0_API_URL}/memories/{memory_id}", headers=_headers())
        r.raise_for_status()
        data = r.json()
    return str(data)


@mcp.tool()
def update_memory(memory_id: str, text: str) -> str:
    """Update an existing memory with new content."""
    with httpx.Client(timeout=30) as c:
        r = c.put(f"{MEM0_API_URL}/memories/{memory_id}", json={"memory": text}, headers=_headers())
        r.raise_for_status()
        data = r.json()
    return f"Memory {memory_id} updated: {data}"


@mcp.tool()
def delete_memory(memory_id: str) -> str:
    """Delete a specific memory by ID."""
    with httpx.Client(timeout=30) as c:
        r = c.delete(f"{MEM0_API_URL}/memories/{memory_id}", headers=_headers())
        r.raise_for_status()
    return f"Memory {memory_id} deleted."


@mcp.tool()
def delete_all_memories(user_id: str = "") -> str:
    """Delete all memories for the user."""
    uid = user_id or DEFAULT_USER_ID
    with httpx.Client(timeout=30) as c:
        r = c.delete(f"{MEM0_API_URL}/memories", params={"user_id": uid}, headers=_headers())
        r.raise_for_status()
    return f"All memories for user {uid} deleted."


@mcp.tool()
def memory_history(memory_id: str) -> str:
    """Get the change history for a specific memory."""
    with httpx.Client(timeout=30) as c:
        r = c.get(f"{MEM0_API_URL}/memories/{memory_id}/history", headers=_headers())
        r.raise_for_status()
        data = r.json()
    return str(data)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
