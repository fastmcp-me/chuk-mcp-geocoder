"""
Discovery tool registration for chuk-mcp-geocoder.

Registers nearby places, admin boundaries, status, and capabilities tools.
"""

import logging

from ...constants import (
    ALL_TOOLS,
    BATCH_TOOLS,
    DISCOVERY_TOOLS,
    GEOCODING_TOOLS,
    ServerConfig,
    SuccessMessages,
)
from ...models.responses import (
    AdminBoundaryLevel,
    AdminBoundaryResponse,
    CapabilitiesResponse,
    ErrorResponse,
    NearbyPlace,
    NearbyPlacesResponse,
    StatusResponse,
    format_response,
)

logger = logging.getLogger(__name__)


def register_discovery_tools(mcp, geocoder):
    """Register discovery tools with the MCP server."""

    @mcp.tool()
    async def nearby_places(
        lat: float,
        lon: float,
        limit: int = 10,
        categories: str | None = None,
        output_mode: str = "json",
    ) -> str:
        """Find places near a coordinate.

        Discovers nearby places at different scales (buildings, streets,
        suburbs, cities) using reverse geocoding at multiple zoom levels.

        Args:
            lat: Latitude (-90 to 90)
            lon: Longitude (-180 to 180)
            limit: Maximum number of results (default 10)
            categories: Comma-separated OSM categories to filter (e.g. "natural,tourism")
            output_mode: "json" (default) or "text"

        Returns:
            List of nearby places with distances, sorted by proximity
        """
        try:
            cat_list = [c.strip() for c in categories.split(",")] if categories else None
            items = await geocoder.nearby_places(lat, lon, limit=limit, categories=cat_list)
            places = [
                NearbyPlace(
                    display_name=item.display_name,
                    lat=item.lat,
                    lon=item.lon,
                    distance_m=item.distance_m,
                    place_type=item.place_type,
                    osm_type=item.osm_type,
                    importance=item.importance,
                )
                for item in items
            ]
            response = NearbyPlacesResponse(
                lat=lat,
                lon=lon,
                places=places,
                count=len(places),
                message=SuccessMessages.NEARBY_FOUND.format(len(places), lat, lon),
            )
            return format_response(response, output_mode)
        except Exception as e:
            logger.error("nearby_places failed: %s", e)
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool()
    async def admin_boundaries(
        lat: float,
        lon: float,
        output_mode: str = "json",
    ) -> str:
        """Get administrative boundary hierarchy for a location.

        Returns the full admin hierarchy from country down to neighbourhood
        for the given coordinates.

        Args:
            lat: Latitude (-90 to 90)
            lon: Longitude (-180 to 180)
            output_mode: "json" (default) or "text"

        Returns:
            Administrative boundaries from largest to smallest
        """
        try:
            display_name, items = await geocoder.admin_boundaries(lat, lon)
            boundaries = [
                AdminBoundaryLevel(
                    level=item.level,
                    name=item.name,
                    osm_type=item.osm_type,
                    osm_id=item.osm_id,
                )
                for item in items
            ]
            response = AdminBoundaryResponse(
                lat=lat,
                lon=lon,
                boundaries=boundaries,
                display_name=display_name,
                message=SuccessMessages.ADMIN_BOUNDARIES.format(lat, lon),
            )
            return format_response(response, output_mode)
        except Exception as e:
            logger.error("admin_boundaries failed: %s", e)
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool()
    async def geocoder_status(output_mode: str = "json") -> str:
        """Get geocoder server status.

        Returns server version, Nominatim URL, cache stats, and tool count.

        Args:
            output_mode: "json" (default) or "text"

        Returns:
            Server status information
        """
        try:
            response = StatusResponse(
                server=ServerConfig.NAME,
                version=ServerConfig.VERSION,
                nominatim_url=geocoder._client._base_url,
                cache_entries=geocoder.cache_entries,
                tool_count=len(ALL_TOOLS),
                message=SuccessMessages.STATUS.format(ServerConfig.VERSION),
            )
            return format_response(response, output_mode)
        except Exception as e:
            logger.error("geocoder_status failed: %s", e)
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool()
    async def geocoder_capabilities(output_mode: str = "json") -> str:
        """Get full server capabilities.

        Returns the complete list of tools, Nominatim API details,
        and LLM-friendly usage guidance.

        Args:
            output_mode: "json" (default) or "text"

        Returns:
            Full server capabilities including tool lists and guidance
        """
        try:
            response = CapabilitiesResponse(
                server=ServerConfig.NAME,
                version=ServerConfig.VERSION,
                geocoding_tools=GEOCODING_TOOLS,
                discovery_tools=DISCOVERY_TOOLS,
                batch_tools=BATCH_TOOLS,
                tool_count=len(ALL_TOOLS),
                nominatim_url=geocoder._client._base_url,
                llm_guidance=(
                    "Use 'geocode' to convert place names to coordinates. "
                    "Use 'bbox_from_place' to get a bounding box suitable for "
                    "DEM elevation, STAC satellite imagery, and other geospatial tools. "
                    "Use 'reverse_geocode' to identify a location from coordinates. "
                    "Use 'nearby_places' to discover what is around a point. "
                    "Use 'admin_boundaries' to get the administrative hierarchy. "
                    "Use 'batch_geocode' for multiple place names at once. "
                    "Use 'route_waypoints' for ordered A→B→C route distances. "
                    "Use 'distance_matrix' for pairwise distances between points."
                ),
                message=SuccessMessages.CAPABILITIES.format(
                    ServerConfig.NAME, ServerConfig.VERSION
                ),
            )
            return format_response(response, output_mode)
        except Exception as e:
            logger.error("geocoder_capabilities failed: %s", e)
            return format_response(ErrorResponse(error=str(e)), output_mode)
