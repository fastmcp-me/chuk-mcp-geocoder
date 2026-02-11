"""Tests for discovery tool registration and execution."""

import json

import pytest
from unittest.mock import MagicMock

from chuk_mcp_geocoder.tools.discovery.api import register_discovery_tools


@pytest.fixture
def discovery_tools(mock_geocoder):
    """Register discovery tools and return captured tools dict."""
    tools = {}

    def capture_tool(**kwargs):
        def decorator(fn):
            tools[fn.__name__] = fn
            return fn

        return decorator

    mcp = MagicMock()
    mcp.tool = capture_tool
    register_discovery_tools(mcp, mock_geocoder)
    return tools


class TestRegistration:
    def test_registers_four_tools(self, discovery_tools):
        assert len(discovery_tools) == 4

    def test_registers_nearby_places(self, discovery_tools):
        assert "nearby_places" in discovery_tools

    def test_registers_admin_boundaries(self, discovery_tools):
        assert "admin_boundaries" in discovery_tools

    def test_registers_geocoder_status(self, discovery_tools):
        assert "geocoder_status" in discovery_tools

    def test_registers_geocoder_capabilities(self, discovery_tools):
        assert "geocoder_capabilities" in discovery_tools

    def test_all_are_coroutines(self, discovery_tools):
        import asyncio

        for fn in discovery_tools.values():
            assert asyncio.iscoroutinefunction(fn)


class TestNearbyPlacesJSON:
    async def test_returns_json(self, discovery_tools):
        result = await discovery_tools["nearby_places"](lat=40.0, lon=-105.0)
        data = json.loads(result)
        assert "places" in data
        assert "count" in data
        assert "lat" in data
        assert "lon" in data

    async def test_count_matches(self, discovery_tools):
        result = await discovery_tools["nearby_places"](lat=40.0, lon=-105.0)
        data = json.loads(result)
        assert data["count"] == len(data["places"])


class TestNearbyPlacesText:
    async def test_text_output(self, discovery_tools):
        result = await discovery_tools["nearby_places"](lat=40.0, lon=-105.0, output_mode="text")
        assert isinstance(result, str)


class TestNearbyPlacesCategories:
    async def test_categories_param_accepted(self, discovery_tools):
        result = await discovery_tools["nearby_places"](
            lat=40.0, lon=-105.0, categories="natural,tourism"
        )
        data = json.loads(result)
        assert "places" in data

    async def test_no_categories_returns_all(self, discovery_tools):
        result = await discovery_tools["nearby_places"](lat=40.0, lon=-105.0)
        data = json.loads(result)
        assert "places" in data


class TestNearbyPlacesErrors:
    async def test_invalid_lat(self, discovery_tools):
        result = await discovery_tools["nearby_places"](lat=100.0, lon=0.0)
        data = json.loads(result)
        assert "error" in data


class TestAdminBoundariesJSON:
    async def test_returns_json(self, discovery_tools):
        result = await discovery_tools["admin_boundaries"](lat=40.0, lon=-105.0)
        data = json.loads(result)
        assert "boundaries" in data
        assert "display_name" in data

    async def test_has_levels(self, discovery_tools):
        result = await discovery_tools["admin_boundaries"](lat=40.0, lon=-105.0)
        data = json.loads(result)
        levels = [b["level"] for b in data["boundaries"]]
        assert "country" in levels


class TestAdminBoundariesText:
    async def test_text_output(self, discovery_tools):
        result = await discovery_tools["admin_boundaries"](lat=40.0, lon=-105.0, output_mode="text")
        assert isinstance(result, str)
        assert "country" in result


class TestAdminBoundariesErrors:
    async def test_invalid_coordinates(self, discovery_tools):
        result = await discovery_tools["admin_boundaries"](lat=100.0, lon=0.0)
        data = json.loads(result)
        assert "error" in data


class TestGeocoderStatusJSON:
    async def test_returns_json(self, discovery_tools):
        result = await discovery_tools["geocoder_status"]()
        data = json.loads(result)
        assert "server" in data
        assert "version" in data
        assert "nominatim_url" in data
        assert "cache_entries" in data
        assert "tool_count" in data

    async def test_server_name(self, discovery_tools):
        result = await discovery_tools["geocoder_status"]()
        data = json.loads(result)
        assert data["server"] == "chuk-mcp-geocoder"

    async def test_tool_count(self, discovery_tools):
        result = await discovery_tools["geocoder_status"]()
        data = json.loads(result)
        assert data["tool_count"] == 10


class TestGeocoderStatusText:
    async def test_text_output(self, discovery_tools):
        result = await discovery_tools["geocoder_status"](output_mode="text")
        assert isinstance(result, str)
        assert "chuk-mcp-geocoder" in result


class TestGeocoderCapabilitiesJSON:
    async def test_returns_json(self, discovery_tools):
        result = await discovery_tools["geocoder_capabilities"]()
        data = json.loads(result)
        assert "geocoding_tools" in data
        assert "discovery_tools" in data
        assert "llm_guidance" in data

    async def test_tool_lists(self, discovery_tools):
        result = await discovery_tools["geocoder_capabilities"]()
        data = json.loads(result)
        assert "geocode" in data["geocoding_tools"]
        assert "nearby_places" in data["discovery_tools"]

    async def test_llm_guidance_not_empty(self, discovery_tools):
        result = await discovery_tools["geocoder_capabilities"]()
        data = json.loads(result)
        assert len(data["llm_guidance"]) > 0


class TestGeocoderCapabilitiesText:
    async def test_text_output(self, discovery_tools):
        result = await discovery_tools["geocoder_capabilities"](output_mode="text")
        assert isinstance(result, str)
        assert "geocode" in result
