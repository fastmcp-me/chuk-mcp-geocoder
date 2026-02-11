"""Tests for chuk-mcp-geocoder constants."""

from chuk_mcp_geocoder.constants import (
    ADMIN_LEVEL_KEYS,
    ALL_TOOLS,
    BATCH_MAX_QUERIES,
    BATCH_TOOLS,
    DEFAULT_BBOX_BUFFER,
    DISCOVERY_TOOLS,
    GEOCODING_TOOLS,
    NEARBY_CATEGORIES,
    PLACE_RANK_BUFFERS,
    EnvVar,
    ErrorMessages,
    NominatimConfig,
    ServerConfig,
    SuccessMessages,
    ZoomLevel,
)


class TestServerConfig:
    def test_name(self):
        assert ServerConfig.NAME == "chuk-mcp-geocoder"

    def test_version(self):
        assert ServerConfig.VERSION == "0.1.0"

    def test_description_not_empty(self):
        assert len(ServerConfig.DESCRIPTION) > 0


class TestNominatimConfig:
    def test_base_url(self):
        assert NominatimConfig.BASE_URL.startswith("https://")

    def test_rate_limit(self):
        assert NominatimConfig.RATE_LIMIT_SECONDS >= 1.0

    def test_default_limit(self):
        assert 1 <= NominatimConfig.DEFAULT_LIMIT <= NominatimConfig.MAX_LIMIT

    def test_cache_ttl_positive(self):
        assert NominatimConfig.CACHE_TTL_SECONDS > 0

    def test_cache_max_size_positive(self):
        assert NominatimConfig.CACHE_MAX_SIZE > 0

    def test_default_zoom(self):
        assert 0 <= NominatimConfig.DEFAULT_ZOOM <= 18

    def test_max_retries_positive(self):
        assert NominatimConfig.MAX_RETRIES >= 1

    def test_retry_base_delay_positive(self):
        assert NominatimConfig.RETRY_BASE_DELAY > 0

    def test_retryable_status_codes(self):
        assert 429 in NominatimConfig.RETRYABLE_STATUS_CODES
        assert 503 in NominatimConfig.RETRYABLE_STATUS_CODES


class TestEnvVar:
    def test_mcp_stdio(self):
        assert EnvVar.MCP_STDIO == "MCP_STDIO"

    def test_nominatim_email(self):
        assert EnvVar.NOMINATIM_EMAIL == "NOMINATIM_EMAIL"


class TestZoomLevel:
    def test_country_lt_city(self):
        assert ZoomLevel.COUNTRY < ZoomLevel.CITY

    def test_city_lt_building(self):
        assert ZoomLevel.CITY < ZoomLevel.BUILDING

    def test_building_is_18(self):
        assert ZoomLevel.BUILDING == 18


class TestPlaceRankBuffers:
    def test_not_empty(self):
        assert len(PLACE_RANK_BUFFERS) > 0

    def test_buffers_decrease_with_rank(self):
        prev_buffer = float("inf")
        for (low, high), buffer in sorted(PLACE_RANK_BUFFERS.items()):
            assert buffer < prev_buffer
            prev_buffer = buffer

    def test_default_buffer_positive(self):
        assert DEFAULT_BBOX_BUFFER > 0


class TestToolLists:
    def test_geocoding_tools(self):
        assert "geocode" in GEOCODING_TOOLS
        assert "reverse_geocode" in GEOCODING_TOOLS
        assert "bbox_from_place" in GEOCODING_TOOLS

    def test_discovery_tools(self):
        assert "nearby_places" in DISCOVERY_TOOLS
        assert "admin_boundaries" in DISCOVERY_TOOLS
        assert "geocoder_status" in DISCOVERY_TOOLS
        assert "geocoder_capabilities" in DISCOVERY_TOOLS

    def test_all_tools_is_union(self):
        assert ALL_TOOLS == GEOCODING_TOOLS + DISCOVERY_TOOLS + BATCH_TOOLS

    def test_tool_count(self):
        assert len(ALL_TOOLS) == 10

    def test_batch_tools(self):
        assert "batch_geocode" in BATCH_TOOLS
        assert "route_waypoints" in BATCH_TOOLS
        assert "distance_matrix" in BATCH_TOOLS

    def test_batch_max_queries(self):
        assert BATCH_MAX_QUERIES == 50


class TestNearbyCategories:
    def test_not_empty(self):
        assert len(NEARBY_CATEGORIES) > 0

    def test_contains_natural(self):
        assert "natural" in NEARBY_CATEGORIES

    def test_contains_tourism(self):
        assert "tourism" in NEARBY_CATEGORIES

    def test_all_strings(self):
        assert all(isinstance(c, str) for c in NEARBY_CATEGORIES)


class TestAdminLevelKeys:
    def test_not_empty(self):
        assert len(ADMIN_LEVEL_KEYS) > 0

    def test_country_first(self):
        assert ADMIN_LEVEL_KEYS[0] == ("country", "country")

    def test_tuples_of_two(self):
        for item in ADMIN_LEVEL_KEYS:
            assert len(item) == 2


class TestErrorMessages:
    def test_no_results_format(self):
        msg = ErrorMessages.NO_RESULTS.format("test")
        assert "test" in msg

    def test_invalid_lat_format(self):
        msg = ErrorMessages.INVALID_LAT.format(100)
        assert "100" in msg

    def test_api_error_format(self):
        msg = ErrorMessages.API_ERROR.format(500, "Internal Server Error")
        assert "500" in msg


class TestSuccessMessages:
    def test_geocode_found_format(self):
        msg = SuccessMessages.GEOCODE_FOUND.format(3, "Boulder")
        assert "3" in msg
        assert "Boulder" in msg

    def test_reverse_found_format(self):
        msg = SuccessMessages.REVERSE_FOUND.format(40.0, -105.0, "Boulder")
        assert "Boulder" in msg

    def test_bbox_extracted_format(self):
        msg = SuccessMessages.BBOX_EXTRACTED.format("Boulder", -105.3, 39.9, -105.2, 40.1)
        assert "Boulder" in msg
