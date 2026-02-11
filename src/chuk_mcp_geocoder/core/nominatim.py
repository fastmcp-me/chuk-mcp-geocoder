"""
Low-level async HTTP client for the Nominatim API.

Handles rate limiting, caching, and bbox format conversion.
"""

import asyncio
import hashlib
import json
import logging
import math
import time
from collections import OrderedDict
from dataclasses import dataclass

import httpx

from ..constants import (
    DEFAULT_BBOX_BUFFER,
    PLACE_RANK_BUFFERS,
    ErrorMessages,
    NominatimConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cached API response with timestamp."""

    data: dict | list
    timestamp: float


class NominatimClient:
    """Async HTTP client for the Nominatim geocoding API.

    Features:
    - Rate limiting (1 request/second for public API)
    - LRU cache with TTL
    - Automatic User-Agent header
    """

    def __init__(
        self,
        base_url: str = NominatimConfig.BASE_URL,
        user_agent: str = NominatimConfig.USER_AGENT,
        email: str = "",
    ):
        self._base_url = base_url
        self._user_agent = user_agent
        self._email = email
        self._last_request_time: float = 0.0
        self._rate_lock = asyncio.Lock()
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazily create httpx client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": self._user_agent},
                timeout=NominatimConfig.TIMEOUT_SECONDS,
            )
        return self._client

    async def _rate_limit(self) -> None:
        """Enforce minimum delay between requests."""
        async with self._rate_lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < NominatimConfig.RATE_LIMIT_SECONDS:
                await asyncio.sleep(NominatimConfig.RATE_LIMIT_SECONDS - elapsed)
            self._last_request_time = time.monotonic()

    def _cache_key(self, endpoint: str, params: dict) -> str:
        """Generate cache key from endpoint + normalized sorted params."""
        normalized = {}
        for k, v in params.items():
            if isinstance(v, str):
                v = " ".join(v.lower().split())
            normalized[k] = v
        raw = f"{endpoint}:{json.dumps(normalized, sort_keys=True)}"
        return hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()  # noqa: S324

    def _cache_get(self, key: str) -> dict | list | None:
        """Get from cache if not expired."""
        if key not in self._cache:
            return None
        entry = self._cache[key]
        if time.time() - entry.timestamp > NominatimConfig.CACHE_TTL_SECONDS:
            del self._cache[key]
            return None
        # Move to end (most recently used)
        self._cache.move_to_end(key)
        return entry.data

    def _cache_put(self, key: str, data: dict | list) -> None:
        """Put into cache, evicting oldest if over max size."""
        if key in self._cache:
            self._cache.move_to_end(key)
            self._cache[key] = CacheEntry(data=data, timestamp=time.time())
        else:
            if len(self._cache) >= NominatimConfig.CACHE_MAX_SIZE:
                self._cache.popitem(last=False)
            self._cache[key] = CacheEntry(data=data, timestamp=time.time())

    async def _request(self, endpoint: str, params: dict) -> dict | list:
        """Make a cached, rate-limited request to Nominatim."""
        # Add common params
        params.setdefault("format", NominatimConfig.DEFAULT_FORMAT)
        params.setdefault("addressdetails", "1")
        if self._email:
            params.setdefault("email", self._email)

        # Check cache
        cache_key = self._cache_key(endpoint, params)
        cached = self._cache_get(cache_key)
        if cached is not None:
            logger.debug("Cache hit for %s", endpoint)
            return cached

        # Rate limit and make request with retry
        client = await self._get_client()
        url = f"{self._base_url}/{endpoint}"

        for attempt in range(NominatimConfig.MAX_RETRIES + 1):
            await self._rate_limit()
            try:
                response = await client.get(url, params=params)
            except httpx.ConnectError as e:
                raise ConnectionError(ErrorMessages.NETWORK_ERROR.format(e)) from e
            except httpx.TimeoutException as e:
                raise ConnectionError(ErrorMessages.NETWORK_ERROR.format(e)) from e

            if (
                response.status_code in NominatimConfig.RETRYABLE_STATUS_CODES
                and attempt < NominatimConfig.MAX_RETRIES
            ):
                delay = NominatimConfig.RETRY_BASE_DELAY * (2**attempt)
                logger.warning(
                    "Nominatim %d, retrying in %.1fs (attempt %d/%d)",
                    response.status_code,
                    delay,
                    attempt + 1,
                    NominatimConfig.MAX_RETRIES,
                )
                await asyncio.sleep(delay)
                continue
            break

        if response.status_code == 429:
            raise RuntimeError(ErrorMessages.RATE_LIMITED)
        if response.status_code != 200:
            raise RuntimeError(
                ErrorMessages.API_ERROR.format(response.status_code, response.text[:200])
            )

        data = response.json()
        self._cache_put(cache_key, data)
        return data

    async def search(
        self,
        query: str,
        limit: int = NominatimConfig.DEFAULT_LIMIT,
        countrycodes: str | None = None,
        viewbox: str | None = None,
        bounded: bool = False,
        language: str | None = None,
    ) -> list[dict]:
        """Forward geocode: search for places by name.

        Args:
            query: Free-form place name or address
            limit: Maximum number of results (1-50)
            countrycodes: Comma-separated ISO 3166-1 country codes
            viewbox: Bias results to box "x1,y1,x2,y2"
            bounded: Restrict results strictly to viewbox
            language: Preferred response language (e.g. "en", "de", "fr")

        Returns:
            List of Nominatim result dicts
        """
        params: dict[str, str | int] = {"q": query, "limit": limit}
        if countrycodes:
            params["countrycodes"] = countrycodes
        if viewbox:
            params["viewbox"] = viewbox
            if bounded:
                params["bounded"] = "1"
        if language:
            params["accept-language"] = language
        result = await self._request("search", params)
        return result if isinstance(result, list) else [result]

    async def reverse(
        self,
        lat: float,
        lon: float,
        zoom: int = 18,
        language: str | None = None,
    ) -> dict:
        """Reverse geocode: coordinates to place.

        Args:
            lat: Latitude
            lon: Longitude
            zoom: Detail level 0-18 (18=building, 10=city, 3=country)
            language: Preferred response language (e.g. "en", "de", "fr")

        Returns:
            Single Nominatim result dict
        """
        params: dict[str, str | int | float] = {
            "lat": lat,
            "lon": lon,
            "zoom": zoom,
        }
        if language:
            params["accept-language"] = language
        result = await self._request("reverse", params)
        return result if isinstance(result, dict) else result[0]

    async def lookup(self, osm_ids: list[str]) -> list[dict]:
        """Lookup specific OSM objects by ID.

        Args:
            osm_ids: List of OSM IDs prefixed by type (e.g., ["R146656", "W104393803"])

        Returns:
            List of Nominatim result dicts
        """
        params: dict[str, str] = {"osm_ids": ",".join(osm_ids)}
        result = await self._request("lookup", params)
        return result if isinstance(result, list) else [result]

    async def close(self) -> None:
        """Close the httpx client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None


def convert_bbox(nominatim_bbox: list[str]) -> list[float]:
    """Convert Nominatim bbox to standard format.

    Nominatim returns [min_lat, max_lat, min_lon, max_lon] as strings.
    Standard geospatial format is [west, south, east, north] as floats.

    Args:
        nominatim_bbox: ["min_lat", "max_lat", "min_lon", "max_lon"]

    Returns:
        [west, south, east, north] = [min_lon, min_lat, max_lon, max_lat]
    """
    min_lat, max_lat, min_lon, max_lon = [float(x) for x in nominatim_bbox]
    return [min_lon, min_lat, max_lon, max_lat]


def bbox_buffer_for_rank(place_rank: int | None) -> float:
    """Return a bbox buffer in degrees based on place_rank.

    Args:
        place_rank: Nominatim place rank (0-30), or None

    Returns:
        Buffer in degrees to add around the point
    """
    if place_rank is None:
        return DEFAULT_BBOX_BUFFER
    for (low, high), buffer in PLACE_RANK_BUFFERS.items():
        if low <= place_rank <= high:
            return buffer
    return DEFAULT_BBOX_BUFFER


def compute_area_km2(bbox: list[float]) -> float:
    """Approximate area of a bbox in km^2 using lat/lon.

    Args:
        bbox: [west, south, east, north]

    Returns:
        Area in square kilometres
    """
    west, south, east, north = bbox
    mid_lat = (south + north) / 2.0
    width_km = (east - west) * 111.32 * math.cos(math.radians(mid_lat))
    height_km = (north - south) * 111.32
    return abs(width_km * height_km)


def midpoint(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    """Calculate the geographic midpoint between two coordinates.

    Args:
        lat1, lon1: First point coordinates
        lat2, lon2: Second point coordinates

    Returns:
        Tuple of (lat, lon) for the midpoint
    """
    return ((lat1 + lat2) / 2.0, (lon1 + lon2) / 2.0)


def bbox_union(bboxes: list[list[float]]) -> list[float]:
    """Merge multiple bboxes into one encompassing bbox.

    Args:
        bboxes: List of [west, south, east, north] bboxes

    Returns:
        Single [west, south, east, north] bbox covering all inputs
    """
    if not bboxes:
        return [0.0, 0.0, 0.0, 0.0]
    west = min(b[0] for b in bboxes)
    south = min(b[1] for b in bboxes)
    east = max(b[2] for b in bboxes)
    north = max(b[3] for b in bboxes)
    return [west, south, east, north]


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in metres using Haversine formula.

    Args:
        lat1, lon1: First point coordinates
        lat2, lon2: Second point coordinates

    Returns:
        Distance in metres
    """
    r = 6371000.0  # Earth radius in metres
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c
