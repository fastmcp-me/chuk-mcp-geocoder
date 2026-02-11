"""Tests validating bbox output format for DEM/STAC compatibility."""

import json

import pytest

from chuk_mcp_geocoder.core.nominatim import convert_bbox


class TestBboxFormatWestSouthEastNorth:
    """All bbox outputs must be [west, south, east, north]."""

    def test_convert_bbox_order(self):
        bbox = convert_bbox(["39.9", "40.1", "-105.3", "-105.1"])
        west, south, east, north = bbox
        assert west < east
        assert south < north

    def test_convert_bbox_values_are_floats(self):
        bbox = convert_bbox(["39.9", "40.1", "-105.3", "-105.1"])
        assert all(isinstance(v, float) for v in bbox)

    def test_convert_bbox_valid_lat_range(self):
        bbox = convert_bbox(["39.9", "40.1", "-105.3", "-105.1"])
        _, south, _, north = bbox
        assert -90 <= south <= 90
        assert -90 <= north <= 90

    def test_convert_bbox_valid_lon_range(self):
        bbox = convert_bbox(["39.9", "40.1", "-105.3", "-105.1"])
        west, _, east, _ = bbox
        assert -180 <= west <= 180
        assert -180 <= east <= 180


class TestGeocodeToolBboxFormat:
    """Geocode tool bbox outputs match DEM/STAC input format."""

    @pytest.fixture
    def geocoding_tools(self, mock_geocoder):
        from unittest.mock import MagicMock

        from chuk_mcp_geocoder.tools.geocoding.api import register_geocoding_tools

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

    async def test_geocode_bbox_format(self, geocoding_tools):
        result = json.loads(await geocoding_tools["geocode"](query="Boulder"))
        for r in result["results"]:
            west, south, east, north = r["bbox"]
            assert west <= east, f"west ({west}) must be <= east ({east})"
            assert south <= north, f"south ({south}) must be <= north ({north})"

    async def test_bbox_from_place_format(self, geocoding_tools):
        result = json.loads(await geocoding_tools["bbox_from_place"](query="Boulder"))
        west, south, east, north = result["bbox"]
        assert west <= east
        assert south <= north

    async def test_bbox_from_place_padded_still_valid(self, geocoding_tools):
        result = json.loads(await geocoding_tools["bbox_from_place"](query="Boulder", padding=0.5))
        west, south, east, north = result["bbox"]
        assert west < east
        assert south < north

    async def test_reverse_geocode_bbox_format(self, geocoding_tools):
        result = json.loads(await geocoding_tools["reverse_geocode"](lat=40.0, lon=-105.0))
        west, south, east, north = result["bbox"]
        assert west <= east
        assert south <= north
