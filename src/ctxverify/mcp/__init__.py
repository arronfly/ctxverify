"""MCP server for ctxverify (stdio, no dependencies).

Exposes the linter to agents so that an agent can check the pack it has just
written without leaving its own session. The protocol version is negotiated
with the client; the server itself needs nothing but the standard library.
"""

from __future__ import annotations

from .server import serve

__all__ = ["serve"]
