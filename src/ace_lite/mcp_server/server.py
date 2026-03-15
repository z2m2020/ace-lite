from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ace_lite.mcp_server.config import AceLiteMcpConfig
from ace_lite.mcp_server.server_tool_registration import register_mcp_tools
from ace_lite.mcp_server.service import AceLiteMcpService


def build_mcp_server(*, config: AceLiteMcpConfig) -> FastMCP:
    service = AceLiteMcpService(config=config)
    server = FastMCP(
        name=config.server_name,
        instructions=(
            "ACE-Lite tools for deterministic code context planning, indexing, "
            "repomap generation, and local memory note operations."
        ),
        log_level="INFO",
    )
    register_mcp_tools(server=server, service=service)
    return server


__all__ = ["build_mcp_server"]
