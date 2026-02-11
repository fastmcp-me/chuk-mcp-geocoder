"""Tests for the NominatimClient and helper functions."""

import httpx
import pytest
import respx

from chuk_mcp_geocoder.core.nominatim import (
    NominatimClient,
    bbox_buffer_for_rank,
    bbox_union,
    compute_area_km2,
    convert_bbox,
    haversine_distance,
    midpoint,
)


class TestConvertBbox:
    def test_standard_conversion(self):
        # Nominatim: [min_lat, max_lat, min_lon, max_lon]
        # Expected:  [west, south, east, north] = [min_lon, min_lat, max_lon, max_lat]
        result = convert_bbox(["39.9138", "40.0940", "-105.3014", "-105.1731"])
        assert result == [-105.3014, 39.9138, -105.1731, 40.0940]

    def test_negative_coordinates(self):
        result = convert_bbox(["-34.0", "-33.0", "18.0", "19.0"])
        assert result == [18.0, -34.0, 19.0, -33.0]

    def test_zero_crossing(self):
        result = convert_bbox(["-1.0", "1.0", "-1.0", "1.0"])
        assert result == [-1.0, -1.0, 1.0, 1.0]

    def test_returns_floats(self):
        result = convert_bbox(["0", "1", "0", "1"])
        assert all(isinstance(x, float) for x in result)


class TestBboxBufferForRank:
    def test_country_rank(self):
        buffer = bbox_buffer_for_rank(3)
        assert buffer == 10.0

    def test_city_rank(self):
        buffer = bbox_buffer_for_rank(15)
        assert buffer == 0.1

    def test_building_rank(self):
        buffer = bbox_buffer_for_rank(28)
        assert buffer == 0.001

    def test_none_rank(self):
        buffer = bbox_buffer_for_rank(None)
        assert buffer == 0.01  # DEFAULT_BBOX_BUFFER

    def test_out_of_range_rank(self):
        buffer = bbox_buffer_for_rank(99)
        assert buffer == 0.01  # DEFAULT_BBOX_BUFFER


class TestComputeAreaKm2:
    def test_small_area(self):
        # ~1 degree box near equator
        area = compute_area_km2([0.0, 0.0, 1.0, 1.0])
        assert 10000 < area < 15000  # ~12,321 km^2

    def test_zero_area(self):
        area = compute_area_km2([0.0, 0.0, 0.0, 0.0])
        assert area == 0.0

    def test_high_latitude_narrower(self):
        area_equator = compute_area_km2([0.0, 0.0, 1.0, 1.0])
        area_60n = compute_area_km2([0.0, 60.0, 1.0, 61.0])
        # At 60N, longitude degrees are roughly half the width
        assert area_60n < area_equator


class TestHaversineDistance:
    def test_same_point(self):
        d = haversine_distance(40.0, -105.0, 40.0, -105.0)
        assert d == 0.0

    def test_known_distance(self):
        # London to Paris ~343 km
        d = haversine_distance(51.5074, -0.1278, 48.8566, 2.3522)
        assert 340_000 < d < 350_000

    def test_symmetric(self):
        d1 = haversine_distance(40.0, -105.0, 41.0, -104.0)
        d2 = haversine_distance(41.0, -104.0, 40.0, -105.0)
        assert abs(d1 - d2) < 0.01


class TestNominatimClientCache:
    def test_cache_key_deterministic(self):
        client = NominatimClient()
        key1 = client._cache_key("search", {"q": "test", "limit": 5})
        key2 = client._cache_key("search", {"q": "test", "limit": 5})
        assert key1 == key2

    def test_cache_key_different_params(self):
        client = NominatimClient()
        key1 = client._cache_key("search", {"q": "boulder"})
        key2 = client._cache_key("search", {"q": "denver"})
        assert key1 != key2

    def test_cache_put_and_get(self):
        client = NominatimClient()
        client._cache_put("key1", {"data": "value"})
        result = client._cache_get("key1")
        assert result == {"data": "value"}

    def test_cache_miss(self):
        client = NominatimClient()
        result = client._cache_get("nonexistent")
        assert result is None

    def test_cache_eviction(self):
        from chuk_mcp_geocoder.constants import NominatimConfig

        client = NominatimClient()
        # Fill cache beyond max size
        for i in range(NominatimConfig.CACHE_MAX_SIZE + 5):
            client._cache_put(f"key{i}", {"i": i})
        assert len(client._cache) == NominatimConfig.CACHE_MAX_SIZE


class TestNominatimClientInit:
    def test_default_init(self):
        client = NominatimClient()
        assert client._base_url == "https://nominatim.openstreetmap.org"
        assert "chuk-mcp-geocoder" in client._user_agent

    def test_custom_init(self):
        client = NominatimClient(
            base_url="https://custom.nominatim.org",
            user_agent="test/1.0",
            email="test@example.com",
        )
        assert client._base_url == "https://custom.nominatim.org"
        assert client._user_agent == "test/1.0"
        assert client._email == "test@example.com"

    def test_client_starts_none(self):
        client = NominatimClient()
        assert client._client is None

    def test_cache_starts_empty(self):
        client = NominatimClient()
        assert len(client._cache) == 0


# --- Async HTTP tests using respx ---

SEARCH_JSON = [
    {
        "place_id": 1,
        "osm_type": "relation",
        "osm_id": 123,
        "lat": "40.0",
        "lon": "-105.0",
        "display_name": "Boulder, Colorado",
        "boundingbox": ["39.9", "40.1", "-105.3", "-105.1"],
        "importance": 0.65,
        "place_rank": 16,
        "address": {"city": "Boulder"},
        "category": "place",
        "type": "city",
    }
]

REVERSE_JSON = {
    "place_id": 2,
    "osm_type": "node",
    "osm_id": 456,
    "lat": "40.0",
    "lon": "-105.0",
    "display_name": "Boulder, Colorado",
    "boundingbox": ["39.9", "40.1", "-105.3", "-105.1"],
    "address": {"city": "Boulder"},
    "place_rank": 16,
    "importance": 0.65,
}

LOOKUP_JSON = [
    {
        "place_id": 3,
        "osm_type": "relation",
        "osm_id": 789,
        "lat": "40.0",
        "lon": "-105.0",
        "display_name": "Boulder, Colorado",
        "address": {"city": "Boulder"},
    }
]


class TestNominatimClientSearch:
    @respx.mock
    async def test_search_returns_list(self):
        respx.get("https://nominatim.openstreetmap.org/search").mock(
            return_value=httpx.Response(200, json=SEARCH_JSON)
        )
        client = NominatimClient()
        results = await client.search("Boulder")
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0]["display_name"] == "Boulder, Colorado"
        await client.close()

    @respx.mock
    async def test_search_with_countrycodes(self):
        route = respx.get("https://nominatim.openstreetmap.org/search").mock(
            return_value=httpx.Response(200, json=SEARCH_JSON)
        )
        client = NominatimClient()
        await client.search("Boulder", countrycodes="us")
        assert "countrycodes" in str(route.calls[0].request.url)
        await client.close()

    @respx.mock
    async def test_search_with_viewbox(self):
        route = respx.get("https://nominatim.openstreetmap.org/search").mock(
            return_value=httpx.Response(200, json=SEARCH_JSON)
        )
        client = NominatimClient()
        await client.search("Boulder", viewbox="-106,39,-104,41", bounded=True)
        url_str = str(route.calls[0].request.url)
        assert "viewbox" in url_str
        assert "bounded" in url_str
        await client.close()

    @respx.mock
    async def test_search_caches_result(self):
        respx.get("https://nominatim.openstreetmap.org/search").mock(
            return_value=httpx.Response(200, json=SEARCH_JSON)
        )
        client = NominatimClient()
        # First call: cache miss -> HTTP request
        await client.search("Boulder")
        assert len(client._cache) == 1
        # Second call: cache hit -> no HTTP request
        await client.search("Boulder")
        # respx would have only seen 1 call
        await client.close()


class TestNominatimClientReverse:
    @respx.mock
    async def test_reverse_returns_dict(self):
        respx.get("https://nominatim.openstreetmap.org/reverse").mock(
            return_value=httpx.Response(200, json=REVERSE_JSON)
        )
        client = NominatimClient()
        result = await client.reverse(40.0, -105.0)
        assert isinstance(result, dict)
        assert result["display_name"] == "Boulder, Colorado"
        await client.close()

    @respx.mock
    async def test_reverse_with_zoom(self):
        route = respx.get("https://nominatim.openstreetmap.org/reverse").mock(
            return_value=httpx.Response(200, json=REVERSE_JSON)
        )
        client = NominatimClient()
        await client.reverse(40.0, -105.0, zoom=10)
        assert "zoom=10" in str(route.calls[0].request.url)
        await client.close()


class TestNominatimClientLookup:
    @respx.mock
    async def test_lookup_returns_list(self):
        respx.get("https://nominatim.openstreetmap.org/lookup").mock(
            return_value=httpx.Response(200, json=LOOKUP_JSON)
        )
        client = NominatimClient()
        results = await client.lookup(["R789"])
        assert isinstance(results, list)
        assert len(results) == 1
        await client.close()


class TestNominatimClientErrors:
    @respx.mock
    async def test_rate_limited_429(self):
        respx.get("https://nominatim.openstreetmap.org/search").mock(
            return_value=httpx.Response(429, text="Rate limited")
        )
        client = NominatimClient()
        with pytest.raises(RuntimeError, match="rate limit"):
            await client.search("test")
        await client.close()

    @respx.mock
    async def test_server_error_500(self):
        respx.get("https://nominatim.openstreetmap.org/search").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        client = NominatimClient()
        with pytest.raises(RuntimeError, match="500"):
            await client.search("test")
        await client.close()

    @respx.mock
    async def test_network_error(self):
        respx.get("https://nominatim.openstreetmap.org/search").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        client = NominatimClient()
        with pytest.raises(ConnectionError, match="Network error"):
            await client.search("test")
        await client.close()

    @respx.mock
    async def test_timeout_error(self):
        respx.get("https://nominatim.openstreetmap.org/search").mock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        client = NominatimClient()
        with pytest.raises(ConnectionError, match="Network error"):
            await client.search("test")
        await client.close()


class TestNominatimClientClose:
    @respx.mock
    async def test_close_client(self):
        respx.get("https://nominatim.openstreetmap.org/search").mock(
            return_value=httpx.Response(200, json=SEARCH_JSON)
        )
        client = NominatimClient()
        await client.search("test")  # Creates the httpx client
        assert client._client is not None
        await client.close()
        assert client._client is None

    async def test_close_when_not_open(self):
        client = NominatimClient()
        await client.close()  # Should not raise
        assert client._client is None


class TestNominatimClientGetClient:
    @respx.mock
    async def test_lazy_creates_client(self):
        client = NominatimClient()
        assert client._client is None
        httpx_client = await client._get_client()
        assert httpx_client is not None
        assert client._client is httpx_client
        await client.close()

    @respx.mock
    async def test_reuses_client(self):
        client = NominatimClient()
        c1 = await client._get_client()
        c2 = await client._get_client()
        assert c1 is c2
        await client.close()


class TestNominatimClientEmail:
    @respx.mock
    async def test_email_included_in_request(self):
        route = respx.get("https://nominatim.openstreetmap.org/search").mock(
            return_value=httpx.Response(200, json=SEARCH_JSON)
        )
        client = NominatimClient(email="test@example.com")
        await client.search("Boulder")
        assert "email=test" in str(route.calls[0].request.url)
        await client.close()


class TestNominatimClientLanguage:
    @respx.mock
    async def test_search_language_param(self):
        route = respx.get("https://nominatim.openstreetmap.org/search").mock(
            return_value=httpx.Response(200, json=SEARCH_JSON)
        )
        client = NominatimClient()
        await client.search("Boulder", language="de")
        assert "accept-language=de" in str(route.calls[0].request.url)
        await client.close()

    @respx.mock
    async def test_reverse_language_param(self):
        route = respx.get("https://nominatim.openstreetmap.org/reverse").mock(
            return_value=httpx.Response(200, json=REVERSE_JSON)
        )
        client = NominatimClient()
        await client.reverse(40.0, -105.0, language="fr")
        assert "accept-language=fr" in str(route.calls[0].request.url)
        await client.close()

    @respx.mock
    async def test_no_language_by_default(self):
        route = respx.get("https://nominatim.openstreetmap.org/search").mock(
            return_value=httpx.Response(200, json=SEARCH_JSON)
        )
        client = NominatimClient()
        await client.search("Boulder")
        assert "accept-language" not in str(route.calls[0].request.url)
        await client.close()


class TestNominatimClientRetry:
    @respx.mock
    async def test_retry_on_429_then_success(self):
        route = respx.get("https://nominatim.openstreetmap.org/search").mock(
            side_effect=[
                httpx.Response(429, text="Rate limited"),
                httpx.Response(200, json=SEARCH_JSON),
            ]
        )
        client = NominatimClient()
        # Patch retry delay to 0 for fast tests
        from chuk_mcp_geocoder.constants import NominatimConfig

        original_delay = NominatimConfig.RETRY_BASE_DELAY
        NominatimConfig.RETRY_BASE_DELAY = 0.0
        try:
            results = await client.search("Boulder")
            assert len(results) == 1
            assert route.call_count == 2
        finally:
            NominatimConfig.RETRY_BASE_DELAY = original_delay
            await client.close()

    @respx.mock
    async def test_retry_on_503_then_success(self):
        route = respx.get("https://nominatim.openstreetmap.org/search").mock(
            side_effect=[
                httpx.Response(503, text="Service Unavailable"),
                httpx.Response(200, json=SEARCH_JSON),
            ]
        )
        client = NominatimClient()
        from chuk_mcp_geocoder.constants import NominatimConfig

        original_delay = NominatimConfig.RETRY_BASE_DELAY
        NominatimConfig.RETRY_BASE_DELAY = 0.0
        try:
            results = await client.search("Boulder")
            assert len(results) == 1
            assert route.call_count == 2
        finally:
            NominatimConfig.RETRY_BASE_DELAY = original_delay
            await client.close()

    @respx.mock
    async def test_retry_exhausted_raises(self):
        respx.get("https://nominatim.openstreetmap.org/search").mock(
            return_value=httpx.Response(429, text="Rate limited")
        )
        client = NominatimClient()
        from chuk_mcp_geocoder.constants import NominatimConfig

        original_delay = NominatimConfig.RETRY_BASE_DELAY
        NominatimConfig.RETRY_BASE_DELAY = 0.0
        try:
            with pytest.raises(RuntimeError, match="rate limit"):
                await client.search("test")
        finally:
            NominatimConfig.RETRY_BASE_DELAY = original_delay
            await client.close()


class TestCacheKeyNormalization:
    def test_case_insensitive(self):
        client = NominatimClient()
        key1 = client._cache_key("search", {"q": "Boulder"})
        key2 = client._cache_key("search", {"q": "boulder"})
        assert key1 == key2

    def test_whitespace_normalized(self):
        client = NominatimClient()
        key1 = client._cache_key("search", {"q": "Boulder, CO"})
        key2 = client._cache_key("search", {"q": "Boulder,  CO"})
        assert key1 == key2

    def test_leading_trailing_whitespace(self):
        client = NominatimClient()
        key1 = client._cache_key("search", {"q": "Boulder"})
        key2 = client._cache_key("search", {"q": "  Boulder  "})
        assert key1 == key2

    def test_non_string_params_unchanged(self):
        client = NominatimClient()
        key1 = client._cache_key("search", {"q": "test", "limit": 5})
        key2 = client._cache_key("search", {"q": "test", "limit": 5})
        assert key1 == key2

    def test_different_queries_different_keys(self):
        client = NominatimClient()
        key1 = client._cache_key("search", {"q": "boulder"})
        key2 = client._cache_key("search", {"q": "denver"})
        assert key1 != key2


class TestMidpoint:
    def test_same_point(self):
        lat, lon = midpoint(40.0, -105.0, 40.0, -105.0)
        assert lat == pytest.approx(40.0)
        assert lon == pytest.approx(-105.0)

    def test_simple_midpoint(self):
        lat, lon = midpoint(0.0, 0.0, 10.0, 10.0)
        assert lat == pytest.approx(5.0)
        assert lon == pytest.approx(5.0)

    def test_negative_coords(self):
        lat, lon = midpoint(-10.0, -20.0, 10.0, 20.0)
        assert lat == pytest.approx(0.0)
        assert lon == pytest.approx(0.0)

    def test_returns_tuple(self):
        result = midpoint(40.0, -105.0, 41.0, -104.0)
        assert isinstance(result, tuple)
        assert len(result) == 2


class TestBboxUnion:
    def test_single_bbox(self):
        result = bbox_union([[-105.0, 39.0, -104.0, 40.0]])
        assert result == [-105.0, 39.0, -104.0, 40.0]

    def test_two_bboxes(self):
        result = bbox_union(
            [
                [-105.0, 39.0, -104.0, 40.0],
                [-106.0, 38.0, -103.0, 41.0],
            ]
        )
        assert result == [-106.0, 38.0, -103.0, 41.0]

    def test_non_overlapping(self):
        result = bbox_union(
            [
                [0.0, 0.0, 1.0, 1.0],
                [10.0, 10.0, 11.0, 11.0],
            ]
        )
        assert result == [0.0, 0.0, 11.0, 11.0]

    def test_empty_list(self):
        result = bbox_union([])
        assert result == [0.0, 0.0, 0.0, 0.0]

    def test_identical_bboxes(self):
        bbox = [-105.0, 39.0, -104.0, 40.0]
        result = bbox_union([bbox, bbox, bbox])
        assert result == bbox
