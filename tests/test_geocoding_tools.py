"""Tests for geocoding tool registration and execution."""

import json

import pytest
from unittest.mock import MagicMock

from chuk_mcp_geocoder.tools.geocoding.api import register_geocoding_tools


@pytest.fixture
def geocoding_tools(mock_geocoder):
    """Register geocoding tools and return captured tools dict."""
    tools = {}

    def capture_tool(**kwargs):
        def decorator(fn):
            tools[fn.__name__] = fn
            return fn

        return decorator

    mcp = MagicMock()
    mcp.tool = capture_tool
    register_geocoding_tools(mcp, mock_geocoder)
    return tools


class TestRegistration:
    def test_registers_three_tools(self, geocoding_tools):
        assert len(geocoding_tools) == 3

    def test_registers_geocode(self, geocoding_tools):
        assert "geocode" in geocoding_tools

    def test_registers_reverse_geocode(self, geocoding_tools):
        assert "reverse_geocode" in geocoding_tools

    def test_registers_bbox_from_place(self, geocoding_tools):
        assert "bbox_from_place" in geocoding_tools

    def test_all_are_coroutines(self, geocoding_tools):
        import asyncio

        for fn in geocoding_tools.values():
            assert asyncio.iscoroutinefunction(fn)


class TestGeocodeJSON:
    async def test_returns_json(self, geocoding_tools):
        result = await geocoding_tools["geocode"](query="Boulder")
        data = json.loads(result)
        assert "query" in data
        assert "results" in data
        assert "count" in data

    async def test_result_has_coordinates(self, geocoding_tools):
        result = await geocoding_tools["geocode"](query="Boulder")
        data = json.loads(result)
        r = data["results"][0]
        assert "lat" in r
        assert "lon" in r
        assert "bbox" in r
        assert "display_name" in r

    async def test_count_matches_results(self, geocoding_tools):
        result = await geocoding_tools["geocode"](query="Boulder")
        data = json.loads(result)
        assert data["count"] == len(data["results"])

    async def test_message_present(self, geocoding_tools):
        result = await geocoding_tools["geocode"](query="Boulder")
        data = json.loads(result)
        assert "message" in data
        assert "Boulder" in data["message"]


class TestGeocodeText:
    async def test_text_output(self, geocoding_tools):
        result = await geocoding_tools["geocode"](query="Boulder", output_mode="text")
        assert isinstance(result, str)
        assert "Boulder" in result


class TestGeocodeErrors:
    async def test_empty_query(self, geocoding_tools):
        result = await geocoding_tools["geocode"](query="")
        data = json.loads(result)
        assert "error" in data
        assert "empty" in data["error"].lower()


class TestReverseGeocodeJSON:
    async def test_returns_json(self, geocoding_tools):
        result = await geocoding_tools["reverse_geocode"](lat=40.0, lon=-105.0)
        data = json.loads(result)
        assert "display_name" in data
        assert "address" in data
        assert "bbox" in data

    async def test_has_message(self, geocoding_tools):
        result = await geocoding_tools["reverse_geocode"](lat=40.0, lon=-105.0)
        data = json.loads(result)
        assert "message" in data


class TestReverseGeocodeText:
    async def test_text_output(self, geocoding_tools):
        result = await geocoding_tools["reverse_geocode"](lat=40.0, lon=-105.0, output_mode="text")
        assert isinstance(result, str)
        assert "Boulder" in result


class TestReverseGeocodeErrors:
    async def test_invalid_lat(self, geocoding_tools):
        result = await geocoding_tools["reverse_geocode"](lat=100.0, lon=0.0)
        data = json.loads(result)
        assert "error" in data


class TestBboxFromPlaceJSON:
    async def test_returns_json(self, geocoding_tools):
        result = await geocoding_tools["bbox_from_place"](query="Boulder")
        data = json.loads(result)
        assert "place_name" in data
        assert "bbox" in data
        assert "center" in data

    async def test_bbox_has_four_elements(self, geocoding_tools):
        result = await geocoding_tools["bbox_from_place"](query="Boulder")
        data = json.loads(result)
        assert len(data["bbox"]) == 4

    async def test_center_has_two_elements(self, geocoding_tools):
        result = await geocoding_tools["bbox_from_place"](query="Boulder")
        data = json.loads(result)
        assert len(data["center"]) == 2

    async def test_area_present(self, geocoding_tools):
        result = await geocoding_tools["bbox_from_place"](query="Boulder")
        data = json.loads(result)
        assert "area_km2" in data
        assert data["area_km2"] > 0


class TestBboxFromPlaceText:
    async def test_text_output(self, geocoding_tools):
        result = await geocoding_tools["bbox_from_place"](query="Boulder", output_mode="text")
        assert isinstance(result, str)
        assert "Boulder" in result


class TestBboxPaddingTool:
    async def test_padding_zero_returns_json(self, geocoding_tools):
        result = await geocoding_tools["bbox_from_place"](query="Boulder", padding=0.0)
        data = json.loads(result)
        assert "bbox" in data

    async def test_padding_expands(self, geocoding_tools):
        r0 = json.loads(await geocoding_tools["bbox_from_place"](query="Boulder", padding=0.0))
        r1 = json.loads(await geocoding_tools["bbox_from_place"](query="Boulder", padding=0.1))
        # Padded west should be smaller
        assert r1["bbox"][0] < r0["bbox"][0]
        # Padded east should be larger
        assert r1["bbox"][2] > r0["bbox"][2]


class TestGeocodeLangTool:
    async def test_language_param_accepted(self, geocoding_tools):
        result = await geocoding_tools["geocode"](query="Boulder", language="de")
        data = json.loads(result)
        assert "results" in data

    async def test_reverse_language_param_accepted(self, geocoding_tools):
        result = await geocoding_tools["reverse_geocode"](lat=40.0, lon=-105.0, language="fr")
        data = json.loads(result)
        assert "display_name" in data


class TestBboxFromPlaceErrors:
    async def test_empty_query(self, geocoding_tools):
        result = await geocoding_tools["bbox_from_place"](query="")
        data = json.loads(result)
        assert "error" in data
