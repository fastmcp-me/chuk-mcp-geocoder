"""
Geocoding tool registration for chuk-mcp-geocoder.

Registers forward geocoding, reverse geocoding, and bbox extraction tools.
"""

import logging

from ...constants import NominatimConfig, SuccessMessages
from ...models.responses import (
    BboxResponse,
    ErrorResponse,
    GeocodeResponse,
    GeocodeResult,
    ReverseGeocodeResponse,
    format_response,
)

logger = logging.getLogger(__name__)


def register_geocoding_tools(mcp, geocoder):
    """Register geocoding tools with the MCP server."""

    @mcp.tool()
    async def geocode(
        query: str,
        limit: int = NominatimConfig.DEFAULT_LIMIT,
        countrycodes: str | None = None,
        language: str | None = None,
        output_mode: str = "json",
    ) -> str:
        """Forward geocode a place name to coordinates.

        Searches the OpenStreetMap/Nominatim database for places matching
        the query and returns coordinates, bounding boxes, and address details.

        Args:
            query: Place name or address to search for (e.g. "Boulder, Colorado")
            limit: Maximum results (1-50, default 5)
            countrycodes: Comma-separated ISO 3166-1 country codes to filter (e.g. "us,gb")
            language: Preferred response language (e.g. "en", "de", "fr")
            output_mode: "json" (default) or "text"

        Returns:
            List of matching places with coordinates, bbox, and address details

        CRITICAL — LLM retry workflow when no results are found:
            Nominatim works best with simple, well-known place names. Specific
            or compound names (e.g. "Strood Causeway, Mersea Island, UK") often
            return nothing.

            If the query returns no results, you MUST retry automatically — do
            NOT ask the user. Follow this cascade:

            1. Remove qualifiers and landmarks — keep only the core place name.
               "Strood Causeway, Mersea Island, UK" → "Mersea Island, UK"
               "Portland Harbor, Maine" → "Portland, Maine"
            2. Simplify further — drop region/country qualifiers.
               "Mersea Island, UK" → "Mersea Island"
               "Portland, Maine" → "Portland"
            3. Use countrycodes to narrow broad queries (e.g. countrycodes="gb").
            4. If the place is near a well-known location, geocode that instead
               and report the approximate area.
            5. Try alternative or official names — "The Strood" instead of
               "Strood Causeway", etc.

            Always retry at least twice with progressively simpler terms before
            telling the user the location could not be found.
        """
        try:
            items = await geocoder.geocode(
                query, limit=limit, countrycodes=countrycodes, language=language
            )
            results = [
                GeocodeResult(
                    lat=item.lat,
                    lon=item.lon,
                    display_name=item.display_name,
                    bbox=item.bbox,
                    osm_type=item.osm_type,
                    osm_id=item.osm_id,
                    importance=item.importance,
                    place_rank=item.place_rank,
                    address=item.address,
                    category=item.category,
                    place_type=item.place_type,
                )
                for item in items
            ]
            response = GeocodeResponse(
                query=query,
                results=results,
                count=len(results),
                message=SuccessMessages.GEOCODE_FOUND.format(len(results), query),
            )
            return format_response(response, output_mode)
        except Exception as e:
            logger.error("geocode failed: %s", e)
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool()
    async def reverse_geocode(
        lat: float,
        lon: float,
        zoom: int = 18,
        language: str | None = None,
        output_mode: str = "json",
    ) -> str:
        """Reverse geocode coordinates to a place name and address.

        Looks up the nearest place for the given coordinates and returns
        the display name, structured address, and bounding box.

        Args:
            lat: Latitude (-90 to 90)
            lon: Longitude (-180 to 180)
            zoom: Detail level 0-18 (18=building, 10=city, 3=country, default 18)
            language: Preferred response language (e.g. "en", "de", "fr")
            output_mode: "json" (default) or "text"

        Returns:
            Place name, address components, and bounding box
        """
        try:
            result = await geocoder.reverse_geocode(lat, lon, zoom=zoom, language=language)
            response = ReverseGeocodeResponse(
                lat=result.lat,
                lon=result.lon,
                display_name=result.display_name,
                address=result.address,
                bbox=result.bbox,
                osm_type=result.osm_type,
                osm_id=result.osm_id,
                place_rank=result.place_rank,
                message=SuccessMessages.REVERSE_FOUND.format(lat, lon, result.display_name),
            )
            return format_response(response, output_mode)
        except Exception as e:
            logger.error("reverse_geocode failed: %s", e)
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool()
    async def bbox_from_place(
        query: str,
        padding: float = 0.0,
        output_mode: str = "json",
    ) -> str:
        """Get a bounding box for a place, suitable for DEM/STAC tools.

        Returns bbox as [west, south, east, north] in EPSG:4326, compatible
        with dem_fetch, stac_search, dem_slope, and other geospatial tools.

        Args:
            query: Place name to get bbox for (e.g. "Palm Jumeirah, Dubai")
            padding: Fractional padding to expand bbox (0.1 = 10% on each side, default 0.0)
            output_mode: "json" (default) or "text"

        Returns:
            Bounding box [west, south, east, north], center point, and approximate area

        CRITICAL — LLM retry workflow when no results are found:
            If the query returns no results, you MUST retry automatically — do
            NOT ask the user. Simplify the query progressively:

            1. Remove specific landmarks/features, keep the broader place.
               "Strood Causeway, Mersea Island" → "Mersea Island"
            2. Drop region/country qualifiers if still no results.
               "Mersea Island, Essex, UK" → "Mersea Island"
            3. Try alternative or official names for the place.
            4. If using a broader place, consider adding padding to cover the
               area of interest (e.g. padding=0.1 for 10% expansion).

            Always retry at least twice before reporting failure.
        """
        try:
            result = await geocoder.bbox_from_place(query, padding=padding)
            response = BboxResponse(
                place_name=result.place_name,
                bbox=result.bbox,
                center=result.center,
                area_km2=result.area_km2,
                message=SuccessMessages.BBOX_EXTRACTED.format(result.place_name, *result.bbox),
            )
            return format_response(response, output_mode)
        except Exception as e:
            logger.error("bbox_from_place failed: %s", e)
            return format_response(ErrorResponse(error=str(e)), output_mode)
