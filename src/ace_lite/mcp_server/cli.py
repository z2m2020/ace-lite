from __future__ import annotations

import argparse
import json
import logging
from typing import Literal, cast

from ace_lite.mcp_server.config import AceLiteMcpConfig
from ace_lite.mcp_server.server import build_mcp_server
from ace_lite.mcp_server.service import AceLiteMcpService
from ace_lite.version import get_version_info

logger = logging.getLogger(__name__)

TransportMode = Literal["stdio", "sse", "streamable-http"]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ACE-Lite MCP server.")
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=("stdio", "sse", "streamable-http"),
        help="MCP transport mode.",
    )
    parser.add_argument(
        "--root",
        default="",
        help="Default repository root (overrides ACE_LITE_DEFAULT_ROOT).",
    )
    parser.add_argument(
        "--skills-dir",
        default="",
        help="Default skills directory (overrides ACE_LITE_DEFAULT_SKILLS_DIR).",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Print server self-test payload and exit.",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        help="Python logging level.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.WARNING),
        format="%(levelname)s %(name)s %(message)s",
    )

    config = AceLiteMcpConfig.from_env(
        default_root=args.root or None,
        default_skills_dir=args.skills_dir or None,
    )
    service = AceLiteMcpService(config=config)
    version_info = get_version_info()
    if bool(version_info.get("drifted")):
        logger.warning(
            "version.drift: pyproject=%s installed=%s dist=%s (run: python -m pip install -e .[dev])",
            version_info.get("pyproject_version"),
            version_info.get("installed_version"),
            version_info.get("dist_name"),
        )

    if bool(args.self_test):
        print(json.dumps(service.health(), ensure_ascii=False))
        return

    logger.info(
        "mcp.server.start",
        extra={
            "transport": args.transport,
            "default_root": str(config.default_root),
        },
    )
    server = build_mcp_server(config=config)
    transport_raw = str(args.transport)
    if transport_raw not in ("stdio", "sse", "streamable-http"):
        raise SystemExit(f"Invalid --transport value: {transport_raw}")
    transport = cast(TransportMode, transport_raw)
    server.run(transport=transport)


__all__ = ["main"]
