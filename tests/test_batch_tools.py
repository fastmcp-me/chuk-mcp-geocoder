"""Tests for batch tool registration and execution."""

import json

import pytest
from unittest.mock import MagicMock

from chuk_mcp_geocoder.tools.batch.api import register_batch_tools


@pytest.fixture
def batch_tools(mock_geocoder):
    """Register batch tools and return captured tools dict."""
    tools = {}

    def capture_tool(**kwargs):
        def decorator(fn):
            tools[fn.__name__] = fn
            return fn

        return decorator

    mcp = MagicMock()
    mcp.tool = capture_tool
    register_batch_tools(mcp, mock_geocoder)
    return tools


class TestRegistration:
    def test_registers_three_tools(self, batch_tools):
        assert len(batch_tools) == 3

    def test_registers_batch_geocode(self, batch_tools):
        assert "batch_geocode" in batch_tools

    def test_registers_route_waypoints(self, batch_tools):
        assert "route_waypoints" in batch_tools

    def test_registers_distance_matrix(self, batch_tools):
        assert "distance_matrix" in batch_tools

    def test_all_are_coroutines(self, batch_tools):
        import asyncio

        for fn in batch_tools.values():
            assert asyncio.iscoroutinefunction(fn)


# --- batch_geocode ---


class TestBatchGeocodeJSON:
    async def test_returns_json(self, batch_tools):
        result = await batch_tools["batch_geocode"](queries='["Boulder, CO"]')
        data = json.loads(result)
        assert "queries" in data
        assert "results" in data
        assert "total" in data
        assert "succeeded" in data
        assert "failed" in data

    async def test_single_query(self, batch_tools):
        result = await batch_tools["batch_geocode"](queries='["Boulder"]')
        data = json.loads(result)
        assert data["total"] == 1
        assert data["succeeded"] == 1
        assert data["failed"] == 0

    async def test_multiple_queries(self, batch_tools):
        result = await batch_tools["batch_geocode"](queries='["Boulder", "Denver"]')
        data = json.loads(result)
        assert data["total"] == 2
        assert data["succeeded"] == 2

    async def test_result_has_coordinates(self, batch_tools):
        result = await batch_tools["batch_geocode"](queries='["Boulder"]')
        data = json.loads(result)
        item = data["results"][0]
        assert item["results"] is not None
        assert item["results"][0]["lat"] is not None

    async def test_message_present(self, batch_tools):
        result = await batch_tools["batch_geocode"](queries='["Boulder"]')
        data = json.loads(result)
        assert "message" in data


class TestBatchGeocodeText:
    async def test_text_output(self, batch_tools):
        result = await batch_tools["batch_geocode"](queries='["Boulder"]', output_mode="text")
        assert isinstance(result, str)
        assert "Boulder" in result


class TestBatchGeocodeErrors:
    async def test_invalid_json(self, batch_tools):
        result = await batch_tools["batch_geocode"](queries="not json")
        data = json.loads(result)
        assert "error" in data

    async def test_not_array(self, batch_tools):
        result = await batch_tools["batch_geocode"](queries='{"key": "value"}')
        data = json.loads(result)
        assert "error" in data

    async def test_empty_array(self, batch_tools):
        result = await batch_tools["batch_geocode"](queries="[]")
        data = json.loads(result)
        assert "error" in data


# --- route_waypoints ---


class TestRouteWaypointsJSON:
    async def test_returns_json(self, batch_tools):
        result = await batch_tools["route_waypoints"](waypoints='["Boulder, CO", "Denver, CO"]')
        data = json.loads(result)
        assert "waypoints" in data
        assert "legs" in data
        assert "total_distance_m" in data
        assert "bbox" in data
        assert "waypoint_count" in data

    async def test_two_waypoints(self, batch_tools):
        result = await batch_tools["route_waypoints"](waypoints='["Boulder", "Denver"]')
        data = json.loads(result)
        assert data["waypoint_count"] == 2
        assert len(data["legs"]) == 1

    async def test_three_waypoints(self, batch_tools):
        result = await batch_tools["route_waypoints"](waypoints='["A", "B", "C"]')
        data = json.loads(result)
        assert data["waypoint_count"] == 3
        assert len(data["legs"]) == 2

    async def test_waypoint_has_coords(self, batch_tools):
        result = await batch_tools["route_waypoints"](waypoints='["Boulder", "Denver"]')
        data = json.loads(result)
        wp = data["waypoints"][0]
        assert "lat" in wp
        assert "lon" in wp
        assert "name" in wp
        assert "bbox" in wp

    async def test_leg_has_distance(self, batch_tools):
        result = await batch_tools["route_waypoints"](waypoints='["Boulder", "Denver"]')
        data = json.loads(result)
        leg = data["legs"][0]
        assert "from_name" in leg
        assert "to_name" in leg
        assert "distance_m" in leg

    async def test_bbox_has_four_elements(self, batch_tools):
        result = await batch_tools["route_waypoints"](waypoints='["Boulder", "Denver"]')
        data = json.loads(result)
        assert len(data["bbox"]) == 4

    async def test_message_present(self, batch_tools):
        result = await batch_tools["route_waypoints"](waypoints='["Boulder", "Denver"]')
        data = json.loads(result)
        assert "message" in data


class TestRouteWaypointsText:
    async def test_text_output(self, batch_tools):
        result = await batch_tools["route_waypoints"](
            waypoints='["Boulder", "Denver"]', output_mode="text"
        )
        assert isinstance(result, str)
        assert "Boulder" in result


class TestRouteWaypointsErrors:
    async def test_invalid_json(self, batch_tools):
        result = await batch_tools["route_waypoints"](waypoints="not json")
        data = json.loads(result)
        assert "error" in data

    async def test_too_few_waypoints(self, batch_tools):
        result = await batch_tools["route_waypoints"](waypoints='["only one"]')
        data = json.loads(result)
        assert "error" in data

    async def test_not_array(self, batch_tools):
        result = await batch_tools["route_waypoints"](waypoints='{"a": "b"}')
        data = json.loads(result)
        assert "error" in data


# --- distance_matrix ---


class TestDistanceMatrixJSON:
    async def test_returns_json(self, batch_tools):
        result = await batch_tools["distance_matrix"](points="[[40.0, -105.0], [39.7, -104.9]]")
        data = json.loads(result)
        assert "points" in data
        assert "distances" in data
        assert "count" in data

    async def test_two_points_array(self, batch_tools):
        result = await batch_tools["distance_matrix"](points="[[40.0, -105.0], [39.7, -104.9]]")
        data = json.loads(result)
        assert data["count"] == 2
        assert len(data["distances"]) == 2
        assert len(data["distances"][0]) == 2

    async def test_diagonal_is_zero(self, batch_tools):
        result = await batch_tools["distance_matrix"](points="[[40.0, -105.0], [39.7, -104.9]]")
        data = json.loads(result)
        assert data["distances"][0][0] == 0.0
        assert data["distances"][1][1] == 0.0

    async def test_symmetric(self, batch_tools):
        result = await batch_tools["distance_matrix"](points="[[40.0, -105.0], [39.7, -104.9]]")
        data = json.loads(result)
        assert data["distances"][0][1] == data["distances"][1][0]

    async def test_named_points(self, batch_tools):
        result = await batch_tools["distance_matrix"](
            points='[{"name": "Boulder", "lat": 40.0, "lon": -105.0}, '
            '{"name": "Denver", "lat": 39.7, "lon": -104.9}]'
        )
        data = json.loads(result)
        assert data["points"][0]["name"] == "Boulder"
        assert data["points"][1]["name"] == "Denver"

    async def test_auto_names(self, batch_tools):
        result = await batch_tools["distance_matrix"](points="[[40.0, -105.0], [39.7, -104.9]]")
        data = json.loads(result)
        assert data["points"][0]["name"] == "Point 1"
        assert data["points"][1]["name"] == "Point 2"

    async def test_three_points(self, batch_tools):
        result = await batch_tools["distance_matrix"](points="[[0, 0], [1, 0], [0, 1]]")
        data = json.loads(result)
        assert data["count"] == 3
        assert len(data["distances"]) == 3
        assert len(data["distances"][0]) == 3

    async def test_distance_positive(self, batch_tools):
        result = await batch_tools["distance_matrix"](points="[[40.0, -105.0], [39.7, -104.9]]")
        data = json.loads(result)
        assert data["distances"][0][1] > 0

    async def test_message_present(self, batch_tools):
        result = await batch_tools["distance_matrix"](points="[[40.0, -105.0], [39.7, -104.9]]")
        data = json.loads(result)
        assert "message" in data


class TestDistanceMatrixText:
    async def test_text_output(self, batch_tools):
        result = await batch_tools["distance_matrix"](
            points="[[40.0, -105.0], [39.7, -104.9]]", output_mode="text"
        )
        assert isinstance(result, str)
        assert "Point 1" in result


class TestDistanceMatrixErrors:
    async def test_invalid_json(self, batch_tools):
        result = await batch_tools["distance_matrix"](points="not json")
        data = json.loads(result)
        assert "error" in data

    async def test_too_few_points(self, batch_tools):
        result = await batch_tools["distance_matrix"](points="[[40.0, -105.0]]")
        data = json.loads(result)
        assert "error" in data

    async def test_not_array(self, batch_tools):
        result = await batch_tools["distance_matrix"](points='{"a": 1}')
        data = json.loads(result)
        assert "error" in data

    async def test_invalid_point_format(self, batch_tools):
        result = await batch_tools["distance_matrix"](points='["bad", "data"]')
        data = json.loads(result)
        assert "error" in data
