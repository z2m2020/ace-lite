"""ACE-Lite MCP server package.

This package hosts the MCP server implementation used by ``ace-lite-mcp`` and
``python -m ace_lite.mcp_server``. Public exports remain available from the
package root for backward compatibility.
"""

from __future__ import annotations

from ace_lite.mcp_server.cli import main
from ace_lite.mcp_server.config import AceLiteMcpConfig
from ace_lite.mcp_server.server import build_mcp_server
from ace_lite.mcp_server.service import AceLiteMcpService

__all__ = [
    "AceLiteMcpConfig",
    "AceLiteMcpService",
    "build_mcp_server",
    "main",
]
