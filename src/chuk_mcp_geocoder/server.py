#!/usr/bin/env python3
"""
Geocoder MCP Server - Entry Point

Provides forward/reverse geocoding, bounding box extraction, nearby places
discovery, and administrative boundary lookup via Nominatim/OpenStreetMap.
Supports both stdio (for Claude Desktop) and HTTP (for API access) transports.
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .constants import EnvVar

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

logger = logging.getLogger(__name__)

# Import mcp instance and all registered tools from async server
from .async_server import mcp  # noqa: F401, E402


def main() -> None:
    """Main entry point for the MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Geocoder MCP Server")
    parser.add_argument(
        "mode",
        nargs="?",
        choices=["stdio", "http"],
        default=None,
        help="Transport mode (stdio for Claude Desktop, http for API)",
    )
    parser.add_argument(
        "--host", default="localhost", help="Host for HTTP mode (default: localhost)"
    )
    parser.add_argument("--port", type=int, default=8010, help="Port for HTTP mode (default: 8010)")

    args = parser.parse_args()

    if args.mode == "stdio":
        print("Geocoder MCP Server starting in STDIO mode", file=sys.stderr)
        mcp.run(stdio=True)
    elif args.mode == "http":
        print(
            f"Geocoder MCP Server starting in HTTP mode on {args.host}:{args.port}",
            file=sys.stderr,
        )
        mcp.run(host=args.host, port=args.port, stdio=False)
    else:
        if os.environ.get(EnvVar.MCP_STDIO) or (not sys.stdin.isatty()):
            print("Geocoder MCP Server starting in STDIO mode (auto-detected)", file=sys.stderr)
            mcp.run(stdio=True)
        else:
            print(
                f"Geocoder MCP Server starting in HTTP mode on {args.host}:{args.port}",
                file=sys.stderr,
            )
            mcp.run(host=args.host, port=args.port, stdio=False)


if __name__ == "__main__":
    main()
