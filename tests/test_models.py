"""Tests for chuk-mcp-geocoder response models."""

import json

import pytest
from pydantic import ValidationError

from chuk_mcp_geocoder.models.responses import (
    AdminBoundaryLevel,
    AdminBoundaryResponse,
    BatchGeocodeItem,
    BatchGeocodeResponse,
    BboxResponse,
    CapabilitiesResponse,
    DistanceMatrixPoint,
    DistanceMatrixResponse,
    ErrorResponse,
    GeocodeResponse,
    GeocodeResult,
    NearbyPlace,
    NearbyPlacesResponse,
    ReverseGeocodeResponse,
    RouteLeg,
    RouteResponse,
    RouteWaypoint,
    StatusResponse,
    format_response,
)


class TestErrorResponse:
    def test_create(self):
        r = ErrorResponse(error="Something went wrong")
        assert r.error == "Something went wrong"

    def test_to_text(self):
        r = ErrorResponse(error="fail")
        assert r.to_text() == "Error: fail"

    def test_extra_forbid(self):
        with pytest.raises(ValidationError):
            ErrorResponse(error="ok", extra_field="bad")

    def test_json_roundtrip(self):
        r = ErrorResponse(error="test")
        data = json.loads(r.model_dump_json())
        assert data["error"] == "test"


class TestGeocodeResult:
    def test_create_minimal(self):
        r = GeocodeResult(
            lat=40.0, lon=-105.0, display_name="Boulder", bbox=[-105.3, 39.9, -105.2, 40.1]
        )
        assert r.lat == 40.0
        assert r.osm_type is None

    def test_create_full(self):
        r = GeocodeResult(
            lat=40.0,
            lon=-105.0,
            display_name="Boulder, CO",
            bbox=[-105.3, 39.9, -105.2, 40.1],
            osm_type="relation",
            osm_id=123,
            importance=0.65,
            place_rank=16,
            address={"city": "Boulder"},
            category="place",
            place_type="city",
        )
        assert r.osm_type == "relation"
        assert r.address["city"] == "Boulder"

    def test_to_text(self):
        r = GeocodeResult(
            lat=40.0, lon=-105.0, display_name="Boulder", bbox=[-105.3, 39.9, -105.2, 40.1]
        )
        text = r.to_text()
        assert "Boulder" in text
        assert "40.000000" in text

    def test_extra_forbid(self):
        with pytest.raises(ValidationError):
            GeocodeResult(
                lat=40.0,
                lon=-105.0,
                display_name="x",
                bbox=[0, 0, 1, 1],
                unknown="bad",
            )


class TestGeocodeResponse:
    def test_create(self):
        result = GeocodeResult(
            lat=40.0, lon=-105.0, display_name="Boulder", bbox=[-105.3, 39.9, -105.2, 40.1]
        )
        r = GeocodeResponse(query="Boulder", results=[result], count=1, message="Found 1 result(s)")
        assert r.count == 1
        assert len(r.results) == 1

    def test_to_text(self):
        result = GeocodeResult(lat=40.0, lon=-105.0, display_name="Boulder", bbox=[0, 0, 1, 1])
        r = GeocodeResponse(query="Boulder", results=[result], count=1, message="Found 1 result(s)")
        text = r.to_text()
        assert "Found 1 result(s)" in text
        assert "Boulder" in text


class TestReverseGeocodeResponse:
    def test_create(self):
        r = ReverseGeocodeResponse(
            lat=40.0,
            lon=-105.0,
            display_name="Boulder",
            address={"city": "Boulder"},
            bbox=[-105.3, 39.9, -105.2, 40.1],
            message="Reversed",
        )
        assert r.display_name == "Boulder"

    def test_to_text(self):
        r = ReverseGeocodeResponse(
            lat=40.0,
            lon=-105.0,
            display_name="Boulder",
            address={"city": "Boulder", "state": "Colorado"},
            bbox=[0, 0, 1, 1],
            message="Reversed",
        )
        text = r.to_text()
        assert "Boulder" in text
        assert "city: Boulder" in text


class TestBboxResponse:
    def test_create(self):
        r = BboxResponse(
            place_name="Boulder",
            bbox=[-105.3, 39.9, -105.2, 40.1],
            center=[-105.25, 40.0],
            area_km2=120.5,
            message="Bbox found",
        )
        assert len(r.bbox) == 4
        assert r.area_km2 == 120.5

    def test_to_text(self):
        r = BboxResponse(
            place_name="Boulder",
            bbox=[-105.3, 39.9, -105.2, 40.1],
            center=[-105.25, 40.0],
            message="Bbox found",
        )
        text = r.to_text()
        assert "Boulder" in text
        assert "Bbox" in text


class TestNearbyPlace:
    def test_create(self):
        p = NearbyPlace(display_name="Place", lat=40.0, lon=-105.0)
        assert p.distance_m is None

    def test_to_text_with_distance(self):
        p = NearbyPlace(display_name="Place", lat=40.0, lon=-105.0, distance_m=500.0)
        assert "500m" in p.to_text()


class TestNearbyPlacesResponse:
    def test_create(self):
        place = NearbyPlace(display_name="Place", lat=40.0, lon=-105.0)
        r = NearbyPlacesResponse(lat=40.0, lon=-105.0, places=[place], count=1, message="Found 1")
        assert r.count == 1


class TestAdminBoundaryResponse:
    def test_create(self):
        level = AdminBoundaryLevel(level="country", name="United States")
        r = AdminBoundaryResponse(
            lat=40.0,
            lon=-105.0,
            boundaries=[level],
            display_name="Boulder",
            message="Admin boundaries",
        )
        assert len(r.boundaries) == 1

    def test_to_text(self):
        level = AdminBoundaryLevel(level="country", name="United States")
        r = AdminBoundaryResponse(
            lat=40.0,
            lon=-105.0,
            boundaries=[level],
            display_name="Boulder",
            message="Admin boundaries",
        )
        text = r.to_text()
        assert "country: United States" in text


class TestStatusResponse:
    def test_create(self):
        r = StatusResponse(
            nominatim_url="https://nominatim.openstreetmap.org",
            tool_count=7,
            message="Status",
        )
        assert r.server == "chuk-mcp-geocoder"
        assert r.tool_count == 7


class TestCapabilitiesResponse:
    def test_create(self):
        r = CapabilitiesResponse(
            server="chuk-mcp-geocoder",
            version="0.1.0",
            geocoding_tools=["geocode"],
            discovery_tools=["nearby_places"],
            tool_count=2,
            nominatim_url="https://nominatim.openstreetmap.org",
            llm_guidance="Use geocode",
            message="Capabilities",
        )
        assert r.tool_count == 2


class TestFormatResponse:
    def test_json_mode(self):
        r = ErrorResponse(error="test")
        result = format_response(r, "json")
        data = json.loads(result)
        assert data["error"] == "test"

    def test_text_mode(self):
        r = ErrorResponse(error="test")
        result = format_response(r, "text")
        assert result == "Error: test"

    def test_default_is_json(self):
        r = ErrorResponse(error="test")
        result = format_response(r)
        data = json.loads(result)
        assert "error" in data


# --- Batch & Routing response model tests ---


class TestBatchGeocodeItem:
    def test_create_success(self):
        result = GeocodeResult(
            lat=40.0, lon=-105.0, display_name="Boulder", bbox=[-105.3, 39.9, -105.2, 40.1]
        )
        item = BatchGeocodeItem(query="Boulder", results=[result])
        assert item.query == "Boulder"
        assert item.results is not None
        assert item.error is None

    def test_create_error(self):
        item = BatchGeocodeItem(query="bad", error="No results found")
        assert item.error == "No results found"
        assert item.results is None

    def test_extra_forbid(self):
        with pytest.raises(ValidationError):
            BatchGeocodeItem(query="test", extra_field="bad")


class TestBatchGeocodeResponse:
    def test_create(self):
        item = BatchGeocodeItem(query="Boulder", error="No results")
        r = BatchGeocodeResponse(
            queries=["Boulder"],
            results=[item],
            total=1,
            succeeded=0,
            failed=1,
            message="Batch geocoded 0/1",
        )
        assert r.total == 1
        assert r.failed == 1

    def test_to_text_error(self):
        item = BatchGeocodeItem(query="bad", error="No results")
        r = BatchGeocodeResponse(
            queries=["bad"],
            results=[item],
            total=1,
            succeeded=0,
            failed=1,
            message="Batch geocoded 0/1",
        )
        text = r.to_text()
        assert "ERROR" in text

    def test_to_text_success(self):
        result = GeocodeResult(lat=40.0, lon=-105.0, display_name="Boulder", bbox=[0, 0, 1, 1])
        item = BatchGeocodeItem(query="Boulder", results=[result])
        r = BatchGeocodeResponse(
            queries=["Boulder"],
            results=[item],
            total=1,
            succeeded=1,
            failed=0,
            message="Batch geocoded 1/1",
        )
        text = r.to_text()
        assert "Boulder" in text
        assert "40.000000" in text


class TestRouteWaypoint:
    def test_create(self):
        wp = RouteWaypoint(name="Boulder", lat=40.0, lon=-105.0, bbox=[-105.3, 39.9, -105.2, 40.1])
        assert wp.name == "Boulder"
        assert len(wp.bbox) == 4

    def test_extra_forbid(self):
        with pytest.raises(ValidationError):
            RouteWaypoint(name="x", lat=0, lon=0, bbox=[0, 0, 1, 1], extra="bad")


class TestRouteLeg:
    def test_create(self):
        leg = RouteLeg(from_name="A", to_name="B", distance_m=1000.0)
        assert leg.distance_m == 1000.0


class TestRouteResponse:
    def test_create(self):
        wp = RouteWaypoint(name="A", lat=40.0, lon=-105.0, bbox=[0, 0, 1, 1])
        leg = RouteLeg(from_name="A", to_name="B", distance_m=5000.0)
        r = RouteResponse(
            waypoints=[wp, wp],
            legs=[leg],
            total_distance_m=5000.0,
            bbox=[-105.0, 39.0, -104.0, 40.0],
            waypoint_count=2,
            message="Route with 2 waypoints",
        )
        assert r.waypoint_count == 2
        assert r.total_distance_m == 5000.0

    def test_to_text(self):
        wp1 = RouteWaypoint(name="Boulder", lat=40.0, lon=-105.0, bbox=[0, 0, 1, 1])
        wp2 = RouteWaypoint(name="Denver", lat=39.7, lon=-104.9, bbox=[0, 0, 1, 1])
        leg = RouteLeg(from_name="Boulder", to_name="Denver", distance_m=40000.0)
        r = RouteResponse(
            waypoints=[wp1, wp2],
            legs=[leg],
            total_distance_m=40000.0,
            bbox=[-105.0, 39.7, -104.9, 40.0],
            waypoint_count=2,
            message="Route with 2 waypoints",
        )
        text = r.to_text()
        assert "Boulder" in text
        assert "Denver" in text
        assert "40000" in text


class TestDistanceMatrixPoint:
    def test_create(self):
        p = DistanceMatrixPoint(name="Boulder", lat=40.0, lon=-105.0)
        assert p.name == "Boulder"


class TestDistanceMatrixResponse:
    def test_create(self):
        p1 = DistanceMatrixPoint(name="A", lat=40.0, lon=-105.0)
        p2 = DistanceMatrixPoint(name="B", lat=39.7, lon=-104.9)
        r = DistanceMatrixResponse(
            points=[p1, p2],
            distances=[[0.0, 5000.0], [5000.0, 0.0]],
            count=2,
            message="Distance matrix for 2 points",
        )
        assert r.count == 2
        assert r.distances[0][1] == 5000.0

    def test_to_text(self):
        p1 = DistanceMatrixPoint(name="A", lat=0, lon=0)
        p2 = DistanceMatrixPoint(name="B", lat=1, lon=1)
        r = DistanceMatrixResponse(
            points=[p1, p2],
            distances=[[0.0, 157000.0], [157000.0, 0.0]],
            count=2,
            message="Matrix",
        )
        text = r.to_text()
        assert "A" in text
        assert "B" in text
