"""
Geocoder manager — async orchestrator for geocoding operations.

Wraps NominatimClient with validation, parsing, and typed dataclass results.
"""

import logging
from dataclasses import dataclass

from ..constants import ADMIN_LEVEL_KEYS, BATCH_MAX_QUERIES, ErrorMessages, ZoomLevel
from .nominatim import (
    NominatimClient,
    bbox_buffer_for_rank,
    bbox_union,
    compute_area_km2,
    convert_bbox,
    haversine_distance,
)

logger = logging.getLogger(__name__)


@dataclass
class GeocodeItem:
    """Parsed result from forward geocoding."""

    lat: float
    lon: float
    display_name: str
    bbox: list[float]
    osm_type: str | None = None
    osm_id: int | None = None
    importance: float | None = None
    place_rank: int | None = None
    address: dict[str, str] | None = None
    category: str | None = None
    place_type: str | None = None


@dataclass
class ReverseResult:
    """Parsed result from reverse geocoding."""

    lat: float
    lon: float
    display_name: str
    address: dict[str, str]
    bbox: list[float]
    osm_type: str | None = None
    osm_id: int | None = None
    place_rank: int | None = None


@dataclass
class BboxResult:
    """Bounding box result for a place."""

    place_name: str
    bbox: list[float]
    center: list[float]
    area_km2: float | None = None


@dataclass
class NearbyItem:
    """A single nearby place with distance."""

    display_name: str
    lat: float
    lon: float
    distance_m: float | None = None
    place_type: str | None = None
    osm_type: str | None = None
    importance: float | None = None


@dataclass
class AdminBoundaryItem:
    """A single administrative boundary level."""

    level: str
    name: str
    osm_type: str | None = None
    osm_id: int | None = None


@dataclass
class BatchItem:
    """Result for a single query in a batch geocode."""

    query: str
    results: list[GeocodeItem] | None = None
    error: str | None = None


@dataclass
class RouteWaypointItem:
    """A resolved waypoint in a route."""

    name: str
    lat: float
    lon: float
    bbox: list[float]


@dataclass
class RouteLegItem:
    """A leg between two consecutive waypoints."""

    from_name: str
    to_name: str
    distance_m: float


@dataclass
class RouteResult:
    """Result of route waypoint resolution."""

    waypoints: list[RouteWaypointItem]
    legs: list[RouteLegItem]
    total_distance_m: float
    bbox: list[float]


class Geocoder:
    """Central manager for geocoding operations.

    Wraps NominatimClient with input validation, result parsing,
    and typed dataclass returns.
    """

    def __init__(self, client: NominatimClient | None = None):
        self._client = client or NominatimClient()

    # --- Validation helpers ---

    @staticmethod
    def _validate_coordinates(lat: float, lon: float) -> None:
        """Validate lat/lon ranges."""
        if not (-90 <= lat <= 90):
            raise ValueError(ErrorMessages.INVALID_LAT.format(lat))
        if not (-180 <= lon <= 180):
            raise ValueError(ErrorMessages.INVALID_LON.format(lon))

    @staticmethod
    def _validate_query(query: str) -> None:
        """Validate search query is not empty."""
        if not query or not query.strip():
            raise ValueError(ErrorMessages.EMPTY_QUERY)

    # --- Primary operations ---

    async def geocode(
        self,
        query: str,
        limit: int = 5,
        countrycodes: str | None = None,
        language: str | None = None,
    ) -> list[GeocodeItem]:
        """Forward geocode: place name to coordinates.

        Args:
            query: Place name or address to search for
            limit: Maximum results
            countrycodes: Comma-separated ISO country codes to filter
            language: Preferred response language (e.g. "en", "de")

        Returns:
            List of GeocodeItem results

        Raises:
            ValueError: If query is empty or no results found
        """
        self._validate_query(query)
        raw_results = await self._client.search(
            query, limit=limit, countrycodes=countrycodes, language=language
        )
        if not raw_results:
            raise ValueError(ErrorMessages.NO_RESULTS.format(query))
        return [self._parse_search_result(r) for r in raw_results]

    async def reverse_geocode(
        self,
        lat: float,
        lon: float,
        zoom: int = 18,
        language: str | None = None,
    ) -> ReverseResult:
        """Reverse geocode: coordinates to place name.

        Args:
            lat: Latitude (-90 to 90)
            lon: Longitude (-180 to 180)
            zoom: Detail level 0-18
            language: Preferred response language (e.g. "en", "de")

        Returns:
            ReverseResult with place details

        Raises:
            ValueError: If coordinates are invalid
        """
        self._validate_coordinates(lat, lon)
        raw = await self._client.reverse(lat, lon, zoom=zoom, language=language)
        return self._parse_reverse_result(raw, lat, lon)

    async def bbox_from_place(self, query: str, padding: float = 0.0) -> BboxResult:
        """Get a bounding box for a place, suitable for DEM/STAC tools.

        Args:
            query: Place name to get bbox for
            padding: Fractional padding to expand bbox (0.1 = 10% on each side)

        Returns:
            BboxResult with bbox as [west, south, east, north]

        Raises:
            ValueError: If query is empty or no results found
        """
        self._validate_query(query)
        raw_results = await self._client.search(query, limit=1)
        if not raw_results:
            raise ValueError(ErrorMessages.NO_RESULTS.format(query))
        item = self._parse_search_result(raw_results[0])
        bbox = item.bbox
        if padding > 0:
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            bbox = [
                bbox[0] - width * padding,
                bbox[1] - height * padding,
                bbox[2] + width * padding,
                bbox[3] + height * padding,
            ]
        area = compute_area_km2(bbox)
        return BboxResult(
            place_name=item.display_name,
            bbox=bbox,
            center=[item.lon, item.lat],
            area_km2=round(area, 2),
        )

    async def nearby_places(
        self,
        lat: float,
        lon: float,
        limit: int = 10,
        categories: list[str] | None = None,
    ) -> list[NearbyItem]:
        """Find places near a coordinate.

        Uses reverse geocoding at multiple zoom levels to discover
        nearby places at different scales.

        Args:
            lat: Latitude
            lon: Longitude
            limit: Maximum number of results

        Returns:
            List of NearbyItem sorted by distance
        """
        self._validate_coordinates(lat, lon)
        seen_names: set[str] = set()
        items: list[NearbyItem] = []

        # Reverse geocode at multiple zoom levels for different-scale places
        for zoom in [ZoomLevel.BUILDING, ZoomLevel.STREET, ZoomLevel.SUBURB, ZoomLevel.CITY]:
            try:
                raw = await self._client.reverse(lat, lon, zoom=zoom)
                name = raw.get("display_name", "")
                if not name or name in seen_names:
                    continue
                seen_names.add(name)
                result_lat = float(raw.get("lat", lat))
                result_lon = float(raw.get("lon", lon))
                dist = haversine_distance(lat, lon, result_lat, result_lon)
                items.append(
                    NearbyItem(
                        display_name=name,
                        lat=result_lat,
                        lon=result_lon,
                        distance_m=round(dist, 1),
                        place_type=raw.get("type"),
                        osm_type=raw.get("osm_type"),
                        importance=float(raw["importance"]) if raw.get("importance") else None,
                    )
                )
            except Exception:
                logger.debug("Reverse geocode at zoom %d failed", zoom, exc_info=True)
                continue

        # Also search nearby with a viewbox
        try:
            buffer = 0.01  # ~1.1 km
            viewbox = f"{lon - buffer},{lat - buffer},{lon + buffer},{lat + buffer}"
            search_results = await self._client.search(
                query=f"{lat},{lon}",
                limit=5,
                viewbox=viewbox,
                bounded=True,
            )
            for r in search_results:
                name = r.get("display_name", "")
                if not name or name in seen_names:
                    continue
                seen_names.add(name)
                result_lat = float(r.get("lat", lat))
                result_lon = float(r.get("lon", lon))
                dist = haversine_distance(lat, lon, result_lat, result_lon)
                items.append(
                    NearbyItem(
                        display_name=name,
                        lat=result_lat,
                        lon=result_lon,
                        distance_m=round(dist, 1),
                        place_type=r.get("type"),
                        osm_type=r.get("osm_type"),
                        importance=float(r["importance"]) if r.get("importance") else None,
                    )
                )
        except Exception:
            logger.debug("Nearby search failed", exc_info=True)

        # Filter by category if specified
        if categories:
            cat_set = set(categories)
            items = [i for i in items if i.place_type in cat_set]

        # Sort by distance and limit
        items.sort(key=lambda x: x.distance_m or float("inf"))
        return items[:limit]

    async def admin_boundaries(
        self,
        lat: float,
        lon: float,
    ) -> tuple[str, list[AdminBoundaryItem]]:
        """Get administrative boundary hierarchy for a location.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Tuple of (display_name, list of AdminBoundaryItem)
        """
        self._validate_coordinates(lat, lon)
        raw = await self._client.reverse(lat, lon, zoom=ZoomLevel.BUILDING)
        display_name = raw.get("display_name", "")
        address = raw.get("address", {})

        boundaries: list[AdminBoundaryItem] = []
        for addr_key, level_name in ADMIN_LEVEL_KEYS:
            if addr_key in address:
                boundaries.append(AdminBoundaryItem(level=level_name, name=address[addr_key]))

        return display_name, boundaries

    # --- Batch operations ---

    async def batch_geocode(
        self,
        queries: list[str],
        limit: int = 1,
    ) -> list[BatchItem]:
        """Geocode multiple place names in one call.

        Each query is processed sequentially to respect rate limits.
        Individual failures don't abort the batch.

        Args:
            queries: List of place names to geocode
            limit: Maximum results per query

        Returns:
            List of BatchItem with results or error for each query

        Raises:
            ValueError: If queries list is empty or exceeds max size
        """
        if not queries:
            raise ValueError(ErrorMessages.BATCH_EMPTY)
        if len(queries) > BATCH_MAX_QUERIES:
            raise ValueError(ErrorMessages.BATCH_TOO_LARGE.format(len(queries), BATCH_MAX_QUERIES))

        items: list[BatchItem] = []
        for query in queries:
            try:
                results = await self.geocode(query, limit=limit)
                items.append(BatchItem(query=query, results=results))
            except Exception as e:
                items.append(BatchItem(query=query, error=str(e)))
        return items

    async def route_waypoints(
        self,
        waypoints: list[str],
    ) -> RouteResult:
        """Geocode waypoints in order and compute route distances.

        Args:
            waypoints: List of place names in route order

        Returns:
            RouteResult with resolved waypoints, legs, total distance, and bbox

        Raises:
            ValueError: If fewer than 2 waypoints
        """
        if len(waypoints) < 2:
            raise ValueError(ErrorMessages.WAYPOINTS_MIN)

        resolved: list[RouteWaypointItem] = []
        for wp in waypoints:
            items = await self.geocode(wp, limit=1)
            item = items[0]
            resolved.append(
                RouteWaypointItem(
                    name=item.display_name,
                    lat=item.lat,
                    lon=item.lon,
                    bbox=item.bbox,
                )
            )

        legs: list[RouteLegItem] = []
        total_distance = 0.0
        for i in range(len(resolved) - 1):
            a, b = resolved[i], resolved[i + 1]
            dist = haversine_distance(a.lat, a.lon, b.lat, b.lon)
            legs.append(RouteLegItem(from_name=a.name, to_name=b.name, distance_m=round(dist, 1)))
            total_distance += dist

        all_bboxes = [wp.bbox for wp in resolved]
        combined_bbox = bbox_union(all_bboxes)

        return RouteResult(
            waypoints=resolved,
            legs=legs,
            total_distance_m=round(total_distance, 1),
            bbox=combined_bbox,
        )

    # --- Parsing helpers ---

    @staticmethod
    def _parse_search_result(raw: dict) -> GeocodeItem:
        """Parse a Nominatim search result into a GeocodeItem."""
        lat = float(raw["lat"])
        lon = float(raw["lon"])
        bbox_raw = raw.get("boundingbox")
        if bbox_raw:
            bbox = convert_bbox(bbox_raw)
        else:
            rank = int(raw["place_rank"]) if raw.get("place_rank") else None
            buffer = bbox_buffer_for_rank(rank)
            bbox = [lon - buffer, lat - buffer, lon + buffer, lat + buffer]

        return GeocodeItem(
            lat=lat,
            lon=lon,
            display_name=raw.get("display_name", ""),
            bbox=bbox,
            osm_type=raw.get("osm_type"),
            osm_id=int(raw["osm_id"]) if raw.get("osm_id") else None,
            importance=float(raw["importance"]) if raw.get("importance") else None,
            place_rank=int(raw["place_rank"]) if raw.get("place_rank") else None,
            address=raw.get("address"),
            category=raw.get("category"),
            place_type=raw.get("type"),
        )

    @staticmethod
    def _parse_reverse_result(raw: dict, lat: float, lon: float) -> ReverseResult:
        """Parse a Nominatim reverse result."""
        result_lat = float(raw.get("lat", lat))
        result_lon = float(raw.get("lon", lon))
        bbox_raw = raw.get("boundingbox")
        if bbox_raw:
            bbox = convert_bbox(bbox_raw)
        else:
            bbox = [result_lon - 0.001, result_lat - 0.001, result_lon + 0.001, result_lat + 0.001]

        return ReverseResult(
            lat=result_lat,
            lon=result_lon,
            display_name=raw.get("display_name", ""),
            address=raw.get("address", {}),
            bbox=bbox,
            osm_type=raw.get("osm_type"),
            osm_id=int(raw["osm_id"]) if raw.get("osm_id") else None,
            place_rank=int(raw["place_rank"]) if raw.get("place_rank") else None,
        )

    @property
    def cache_entries(self) -> int:
        """Number of entries in the API cache."""
        return len(self._client._cache)
