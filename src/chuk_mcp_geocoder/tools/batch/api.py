"""
Batch tool registration for chuk-mcp-geocoder.

Registers batch_geocode, route_waypoints, and distance_matrix tools.
"""

import json
import logging

from ...constants import ErrorMessages, SuccessMessages
from ...models.responses import (
    BatchGeocodeItem,
    BatchGeocodeResponse,
    DistanceMatrixPoint,
    DistanceMatrixResponse,
    ErrorResponse,
    GeocodeResult,
    RouteLeg,
    RouteResponse,
    RouteWaypoint,
    format_response,
)

logger = logging.getLogger(__name__)


def register_batch_tools(mcp, geocoder):
    """Register batch tools with the MCP server."""

    @mcp.tool()
    async def batch_geocode(
        queries: str,
        limit: int = 1,
        output_mode: str = "json",
    ) -> str:
        """Geocode multiple place names in one call.

        Each query is processed sequentially to respect Nominatim rate limits.
        Individual failures don't abort the batch.

        Args:
            queries: JSON array of place names (e.g. '["Boulder, CO", "Denver, CO"]')
            limit: Maximum results per query (default 1)
            output_mode: "json" (default) or "text"

        Returns:
            Per-query results with coordinates, or error for failed queries
        """
        try:
            try:
                query_list = json.loads(queries)
            except (json.JSONDecodeError, TypeError) as e:
                raise ValueError(ErrorMessages.INVALID_JSON.format(e))

            if not isinstance(query_list, list):
                raise ValueError(ErrorMessages.INVALID_JSON.format("Expected a JSON array"))

            items = await geocoder.batch_geocode(query_list, limit=limit)

            results = []
            succeeded = 0
            failed = 0
            for item in items:
                if item.error:
                    failed += 1
                    results.append(
                        BatchGeocodeItem(query=item.query, results=None, error=item.error)
                    )
                else:
                    succeeded += 1
                    geocode_results = [
                        GeocodeResult(
                            lat=r.lat,
                            lon=r.lon,
                            display_name=r.display_name,
                            bbox=r.bbox,
                            osm_type=r.osm_type,
                            osm_id=r.osm_id,
                            importance=r.importance,
                            place_rank=r.place_rank,
                            address=r.address,
                            category=r.category,
                            place_type=r.place_type,
                        )
                        for r in (item.results or [])
                    ]
                    results.append(
                        BatchGeocodeItem(query=item.query, results=geocode_results, error=None)
                    )

            response = BatchGeocodeResponse(
                queries=query_list,
                results=results,
                total=len(query_list),
                succeeded=succeeded,
                failed=failed,
                message=SuccessMessages.BATCH_GEOCODE.format(succeeded, len(query_list)),
            )
            return format_response(response, output_mode)
        except Exception as e:
            logger.error("batch_geocode failed: %s", e)
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool()
    async def route_waypoints(
        waypoints: str,
        output_mode: str = "json",
    ) -> str:
        """Geocode waypoints in order and compute route distances.

        Resolves each waypoint to coordinates, then computes haversine
        distances between consecutive points.

        Args:
            waypoints: JSON array of place names in route order
                       (e.g. '["Boulder, CO", "Denver, CO", "Aspen, CO"]')
            output_mode: "json" (default) or "text"

        Returns:
            Resolved waypoints, leg distances, total distance, and bounding box
        """
        try:
            try:
                wp_list = json.loads(waypoints)
            except (json.JSONDecodeError, TypeError) as e:
                raise ValueError(ErrorMessages.INVALID_JSON.format(e))

            if not isinstance(wp_list, list):
                raise ValueError(ErrorMessages.INVALID_JSON.format("Expected a JSON array"))

            result = await geocoder.route_waypoints(wp_list)

            wps = [
                RouteWaypoint(
                    name=wp.name,
                    lat=wp.lat,
                    lon=wp.lon,
                    bbox=wp.bbox,
                )
                for wp in result.waypoints
            ]
            legs = [
                RouteLeg(
                    from_name=leg.from_name,
                    to_name=leg.to_name,
                    distance_m=leg.distance_m,
                )
                for leg in result.legs
            ]

            response = RouteResponse(
                waypoints=wps,
                legs=legs,
                total_distance_m=result.total_distance_m,
                bbox=result.bbox,
                waypoint_count=len(wps),
                message=SuccessMessages.ROUTE_WAYPOINTS.format(
                    len(wps), result.total_distance_m / 1000.0
                ),
            )
            return format_response(response, output_mode)
        except Exception as e:
            logger.error("route_waypoints failed: %s", e)
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool()
    async def distance_matrix(
        points: str,
        output_mode: str = "json",
    ) -> str:
        """Compute haversine distance matrix between multiple points.

        Pure computation — no API calls needed. Accepts points as either
        [lat, lon] pairs or {"name": ..., "lat": ..., "lon": ...} objects.

        Args:
            points: JSON array of points. Each point is either:
                    - [lat, lon] pair (auto-named "Point 1", "Point 2", ...)
                    - {"name": "Label", "lat": 40.0, "lon": -105.0}
            output_mode: "json" (default) or "text"

        Returns:
            NxN distance matrix in metres between all point pairs
        """
        from ...core.nominatim import haversine_distance

        try:
            try:
                raw_points = json.loads(points)
            except (json.JSONDecodeError, TypeError) as e:
                raise ValueError(ErrorMessages.INVALID_JSON.format(e))

            if not isinstance(raw_points, list):
                raise ValueError(ErrorMessages.INVALID_JSON.format("Expected a JSON array"))

            if len(raw_points) < 2:
                raise ValueError(ErrorMessages.POINTS_MIN)

            # Parse points into (name, lat, lon) tuples
            parsed = []
            for i, p in enumerate(raw_points):
                if isinstance(p, list) and len(p) >= 2:
                    parsed.append((f"Point {i + 1}", float(p[0]), float(p[1])))
                elif isinstance(p, dict) and "lat" in p and "lon" in p:
                    name = p.get("name", f"Point {i + 1}")
                    parsed.append((name, float(p["lat"]), float(p["lon"])))
                else:
                    raise ValueError(
                        ErrorMessages.INVALID_JSON.format(
                            f"Point {i + 1}: expected [lat, lon] or {{name, lat, lon}}"
                        )
                    )

            # Compute NxN distance matrix
            n = len(parsed)
            matrix = []
            for i in range(n):
                row = []
                for j in range(n):
                    if i == j:
                        row.append(0.0)
                    else:
                        dist = haversine_distance(
                            parsed[i][1],
                            parsed[i][2],
                            parsed[j][1],
                            parsed[j][2],
                        )
                        row.append(round(dist, 1))
                matrix.append(row)

            dm_points = [
                DistanceMatrixPoint(name=name, lat=lat, lon=lon) for name, lat, lon in parsed
            ]

            response = DistanceMatrixResponse(
                points=dm_points,
                distances=matrix,
                count=n,
                message=SuccessMessages.DISTANCE_MATRIX.format(n),
            )
            return format_response(response, output_mode)
        except Exception as e:
            logger.error("distance_matrix failed: %s", e)
            return format_response(ErrorResponse(error=str(e)), output_mode)
