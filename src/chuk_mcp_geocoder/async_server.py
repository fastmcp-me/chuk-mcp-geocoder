#!/usr/bin/env python3
"""
Async Geocoder MCP Server using chuk-mcp-server

Forward/reverse geocoding, bounding box extraction, nearby places
discovery, and administrative boundary lookup via Nominatim/OpenStreetMap.
"""

import logging

from chuk_mcp_server import ChukMCPServer

from .core.geocoder import Geocoder
from .tools.batch import register_batch_tools
from .tools.discovery import register_discovery_tools
from .tools.geocoding import register_geocoding_tools

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the MCP server instance
mcp = ChukMCPServer("chuk-mcp-geocoder")

# Create geocoder manager instance
geocoder = Geocoder()

# Register all tool modules
register_geocoding_tools(mcp, geocoder)
register_discovery_tools(mcp, geocoder)
register_batch_tools(mcp, geocoder)

# Run the server
if __name__ == "__main__":
    logger.info("Starting Geocoder MCP Server...")
    mcp.run(stdio=True)
