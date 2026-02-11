"""Tests for the Geocoder manager class."""

import pytest
from unittest.mock import AsyncMock

from chuk_mcp_geocoder.core.geocoder import (
    BatchItem,
    BboxResult,
    GeocodeItem,
    Geocoder,
    ReverseResult,
    RouteLegItem,
    RouteResult,
    RouteWaypointItem,
)

from .conftest import SAMPLE_SEARCH_MULTI


class TestValidation:
    def test_valid_coordinates(self):
        Geocoder._validate_coordinates(0.0, 0.0)
        Geocoder._validate_coordinates(-90.0, -180.0)
        Geocoder._validate_coordinates(90.0, 180.0)

    def test_invalid_lat_too_high(self):
        with pytest.raises(ValueError, match="latitude"):
            Geocoder._validate_coordinates(91.0, 0.0)

    def test_invalid_lat_too_low(self):
        with pytest.raises(ValueError, match="latitude"):
            Geocoder._validate_coordinates(-91.0, 0.0)

    def test_invalid_lon_too_high(self):
        with pytest.raises(ValueError, match="longitude"):
            Geocoder._validate_coordinates(0.0, 181.0)

    def test_invalid_lon_too_low(self):
        with pytest.raises(ValueError, match="longitude"):
            Geocoder._validate_coordinates(0.0, -181.0)

    def test_valid_query(self):
        Geocoder._validate_query("Boulder, Colorado")

    def test_empty_query(self):
        with pytest.raises(ValueError, match="empty"):
            Geocoder._validate_query("")

    def test_whitespace_query(self):
        with pytest.raises(ValueError, match="empty"):
            Geocoder._validate_query("   ")


class TestGeocode:
    async def test_geocode_returns_items(self, mock_geocoder):
        results = await mock_geocoder.geocode("Boulder, Colorado")
        assert len(results) == 1
        assert isinstance(results[0], GeocodeItem)

    async def test_geocode_parses_fields(self, mock_geocoder):
        results = await mock_geocoder.geocode("Boulder")
        item = results[0]
        assert item.lat == pytest.approx(40.0149856)
        assert item.lon == pytest.approx(-105.2705456)
        assert "Boulder" in item.display_name
        assert item.osm_type == "relation"
        assert item.osm_id == 9876543
        assert item.importance == pytest.approx(0.65)
        assert item.place_rank == 16

    async def test_geocode_bbox_converted(self, mock_geocoder):
        results = await mock_geocoder.geocode("Boulder")
        bbox = results[0].bbox
        # [west, south, east, north] = [min_lon, min_lat, max_lon, max_lat]
        assert bbox[0] == pytest.approx(-105.3014)  # west
        assert bbox[1] == pytest.approx(39.9138)  # south
        assert bbox[2] == pytest.approx(-105.1731)  # east
        assert bbox[3] == pytest.approx(40.0940)  # north

    async def test_geocode_address(self, mock_geocoder):
        results = await mock_geocoder.geocode("Boulder")
        assert results[0].address["city"] == "Boulder"
        assert results[0].address["country"] == "United States"

    async def test_geocode_no_results_raises(self, mock_nominatim_client):
        mock_nominatim_client.search = AsyncMock(return_value=[])
        geocoder = Geocoder(client=mock_nominatim_client)
        with pytest.raises(ValueError, match="No results"):
            await geocoder.geocode("nonexistent place xyz123")

    async def test_geocode_empty_query_raises(self, mock_geocoder):
        with pytest.raises(ValueError, match="empty"):
            await mock_geocoder.geocode("")

    async def test_geocode_multiple_results(self, mock_nominatim_client):
        mock_nominatim_client.search = AsyncMock(return_value=SAMPLE_SEARCH_MULTI)
        geocoder = Geocoder(client=mock_nominatim_client)
        results = await geocoder.geocode("Boulder", limit=2)
        assert len(results) == 2

    async def test_geocode_passes_countrycodes(self, mock_geocoder):
        await mock_geocoder.geocode("Boulder", countrycodes="us")
        mock_geocoder._client.search.assert_called_once_with(
            "Boulder", limit=5, countrycodes="us", language=None
        )


class TestReverseGeocode:
    async def test_reverse_returns_result(self, mock_geocoder):
        result = await mock_geocoder.reverse_geocode(40.0, -105.0)
        assert isinstance(result, ReverseResult)

    async def test_reverse_parses_fields(self, mock_geocoder):
        result = await mock_geocoder.reverse_geocode(40.0, -105.0)
        assert result.lat == pytest.approx(40.0149856)
        assert "Boulder" in result.display_name
        assert result.address["city"] == "Boulder"

    async def test_reverse_bbox_converted(self, mock_geocoder):
        result = await mock_geocoder.reverse_geocode(40.0, -105.0)
        assert len(result.bbox) == 4
        assert result.bbox[0] == pytest.approx(-105.3014)

    async def test_reverse_invalid_lat(self, mock_geocoder):
        with pytest.raises(ValueError, match="latitude"):
            await mock_geocoder.reverse_geocode(100.0, 0.0)

    async def test_reverse_invalid_lon(self, mock_geocoder):
        with pytest.raises(ValueError, match="longitude"):
            await mock_geocoder.reverse_geocode(0.0, 200.0)

    async def test_reverse_passes_zoom(self, mock_geocoder):
        await mock_geocoder.reverse_geocode(40.0, -105.0, zoom=10)
        mock_geocoder._client.reverse.assert_called_once_with(40.0, -105.0, zoom=10, language=None)


class TestBboxFromPlace:
    async def test_bbox_returns_result(self, mock_geocoder):
        result = await mock_geocoder.bbox_from_place("Boulder")
        assert isinstance(result, BboxResult)

    async def test_bbox_fields(self, mock_geocoder):
        result = await mock_geocoder.bbox_from_place("Boulder")
        assert "Boulder" in result.place_name
        assert len(result.bbox) == 4
        assert len(result.center) == 2
        assert result.area_km2 is not None
        assert result.area_km2 > 0

    async def test_bbox_center_is_lon_lat(self, mock_geocoder):
        result = await mock_geocoder.bbox_from_place("Boulder")
        # center should be [lon, lat]
        assert result.center[0] == pytest.approx(-105.2705456)
        assert result.center[1] == pytest.approx(40.0149856)

    async def test_bbox_no_results_raises(self, mock_nominatim_client):
        mock_nominatim_client.search = AsyncMock(return_value=[])
        geocoder = Geocoder(client=mock_nominatim_client)
        with pytest.raises(ValueError, match="No results"):
            await geocoder.bbox_from_place("nonexistent")

    async def test_bbox_empty_query_raises(self, mock_geocoder):
        with pytest.raises(ValueError, match="empty"):
            await mock_geocoder.bbox_from_place("")


class TestBboxPadding:
    async def test_padding_zero_unchanged(self, mock_geocoder):
        r0 = await mock_geocoder.bbox_from_place("Boulder", padding=0.0)
        r_default = await mock_geocoder.bbox_from_place("Boulder")
        assert r0.bbox == r_default.bbox

    async def test_padding_expands_bbox(self, mock_geocoder):
        r0 = await mock_geocoder.bbox_from_place("Boulder", padding=0.0)
        r1 = await mock_geocoder.bbox_from_place("Boulder", padding=0.1)
        # Padded bbox should be larger: west smaller, south smaller, east larger, north larger
        assert r1.bbox[0] < r0.bbox[0]  # west
        assert r1.bbox[1] < r0.bbox[1]  # south
        assert r1.bbox[2] > r0.bbox[2]  # east
        assert r1.bbox[3] > r0.bbox[3]  # north

    async def test_padding_area_increases(self, mock_geocoder):
        r0 = await mock_geocoder.bbox_from_place("Boulder", padding=0.0)
        r1 = await mock_geocoder.bbox_from_place("Boulder", padding=0.2)
        assert r1.area_km2 > r0.area_km2

    async def test_negative_padding_no_change(self, mock_geocoder):
        r0 = await mock_geocoder.bbox_from_place("Boulder", padding=0.0)
        r_neg = await mock_geocoder.bbox_from_place("Boulder", padding=-0.1)
        assert r0.bbox == r_neg.bbox


class TestGeocodeLanguage:
    async def test_language_passed_to_client(self, mock_geocoder):
        await mock_geocoder.geocode("Boulder", language="de")
        mock_geocoder._client.search.assert_called_once_with(
            "Boulder", limit=5, countrycodes=None, language="de"
        )

    async def test_language_none_by_default(self, mock_geocoder):
        await mock_geocoder.geocode("Boulder")
        mock_geocoder._client.search.assert_called_once_with(
            "Boulder", limit=5, countrycodes=None, language=None
        )


class TestReverseGeocodeLanguage:
    async def test_language_passed_to_client(self, mock_geocoder):
        await mock_geocoder.reverse_geocode(40.0, -105.0, language="fr")
        mock_geocoder._client.reverse.assert_called_once_with(40.0, -105.0, zoom=18, language="fr")


class TestNearbyCategories:
    async def test_no_filter_returns_all(self, mock_geocoder):
        results = await mock_geocoder.nearby_places(40.0, -105.0)
        assert len(results) > 0

    async def test_filter_by_category(self, mock_nominatim_client):
        """Filtering by category should exclude non-matching place_type."""
        mock_nominatim_client.reverse = AsyncMock(
            side_effect=[
                {
                    "display_name": "River A",
                    "lat": "40.0",
                    "lon": "-105.0",
                    "type": "river",
                    "importance": 0.5,
                },
                {
                    "display_name": "City B",
                    "lat": "40.01",
                    "lon": "-105.01",
                    "type": "city",
                    "importance": 0.6,
                },
                {
                    "display_name": "Park C",
                    "lat": "40.02",
                    "lon": "-105.02",
                    "type": "park",
                    "importance": 0.4,
                },
                {
                    "display_name": "Museum D",
                    "lat": "40.03",
                    "lon": "-105.03",
                    "type": "museum",
                    "importance": 0.3,
                },
            ]
        )
        mock_nominatim_client.search = AsyncMock(return_value=[])
        geocoder = Geocoder(client=mock_nominatim_client)
        results = await geocoder.nearby_places(40.0, -105.0, categories=["city"])
        for r in results:
            assert r.place_type == "city"


class TestBboxFallback:
    """Test bbox computation when Nominatim omits boundingbox."""

    async def test_no_boundingbox_uses_buffer(self, mock_nominatim_client):
        response_no_bbox = [
            {
                "place_id": 1,
                "osm_type": "node",
                "osm_id": 1,
                "lat": "40.0",
                "lon": "-105.0",
                "display_name": "Test Place",
                "importance": 0.5,
                "place_rank": 16,
                "address": {},
                "category": "place",
                "type": "city",
            }
        ]
        mock_nominatim_client.search = AsyncMock(return_value=response_no_bbox)
        geocoder = Geocoder(client=mock_nominatim_client)
        results = await geocoder.geocode("Test Place")
        bbox = results[0].bbox
        # City rank (16) should use 0.1 degree buffer
        assert bbox[0] == pytest.approx(-105.1)  # west
        assert bbox[1] == pytest.approx(39.9)  # south
        assert bbox[2] == pytest.approx(-104.9)  # east
        assert bbox[3] == pytest.approx(40.1)  # north


class TestNearbyPlaces:
    async def test_returns_list(self, mock_geocoder):
        results = await mock_geocoder.nearby_places(40.0, -105.0)
        assert isinstance(results, list)

    async def test_deduplicates(self, mock_geocoder):
        # The mock returns the same display_name for all zoom levels
        results = await mock_geocoder.nearby_places(40.0, -105.0)
        names = [r.display_name for r in results]
        assert len(names) == len(set(names))

    async def test_invalid_coordinates_raises(self, mock_geocoder):
        with pytest.raises(ValueError, match="latitude"):
            await mock_geocoder.nearby_places(100.0, 0.0)


class TestAdminBoundaries:
    async def test_returns_tuple(self, mock_geocoder):
        display_name, boundaries = await mock_geocoder.admin_boundaries(40.0, -105.0)
        assert isinstance(display_name, str)
        assert isinstance(boundaries, list)

    async def test_extracts_hierarchy(self, mock_geocoder):
        _, boundaries = await mock_geocoder.admin_boundaries(40.0, -105.0)
        levels = [b.level for b in boundaries]
        assert "country" in levels
        assert "state" in levels

    async def test_country_name(self, mock_geocoder):
        _, boundaries = await mock_geocoder.admin_boundaries(40.0, -105.0)
        country = next(b for b in boundaries if b.level == "country")
        assert country.name == "United States"

    async def test_invalid_coordinates_raises(self, mock_geocoder):
        with pytest.raises(ValueError, match="latitude"):
            await mock_geocoder.admin_boundaries(100.0, 0.0)


class TestBatchGeocode:
    async def test_batch_returns_list(self, mock_geocoder):
        results = await mock_geocoder.batch_geocode(["Boulder", "Denver"])
        assert isinstance(results, list)
        assert len(results) == 2

    async def test_batch_items_have_query(self, mock_geocoder):
        results = await mock_geocoder.batch_geocode(["Boulder"])
        assert results[0].query == "Boulder"
        assert isinstance(results[0], BatchItem)

    async def test_batch_success_has_results(self, mock_geocoder):
        results = await mock_geocoder.batch_geocode(["Boulder"])
        assert results[0].results is not None
        assert len(results[0].results) > 0
        assert results[0].error is None

    async def test_batch_failure_has_error(self, mock_nominatim_client):
        mock_nominatim_client.search = AsyncMock(return_value=[])
        geocoder = Geocoder(client=mock_nominatim_client)
        results = await geocoder.batch_geocode(["nonexistent xyz"])
        assert results[0].error is not None
        assert results[0].results is None

    async def test_batch_empty_raises(self, mock_geocoder):
        with pytest.raises(ValueError, match="empty"):
            await mock_geocoder.batch_geocode([])

    async def test_batch_too_large_raises(self, mock_geocoder):
        queries = [f"place_{i}" for i in range(51)]
        with pytest.raises(ValueError, match="exceeds"):
            await mock_geocoder.batch_geocode(queries)

    async def test_batch_mixed_results(self, mock_nominatim_client):
        """First query succeeds, second fails."""
        mock_nominatim_client.search = AsyncMock(
            side_effect=[
                SAMPLE_SEARCH_MULTI[:1],  # success
                [],  # no results -> raises ValueError in geocode()
            ]
        )
        geocoder = Geocoder(client=mock_nominatim_client)
        results = await geocoder.batch_geocode(["Boulder", "nonexistent"])
        assert results[0].results is not None
        assert results[1].error is not None


class TestRouteWaypoints:
    async def test_route_returns_result(self, mock_geocoder):
        result = await mock_geocoder.route_waypoints(["Boulder", "Denver"])
        assert isinstance(result, RouteResult)

    async def test_route_waypoints_count(self, mock_geocoder):
        result = await mock_geocoder.route_waypoints(["Boulder", "Denver"])
        assert len(result.waypoints) == 2
        assert isinstance(result.waypoints[0], RouteWaypointItem)

    async def test_route_legs_count(self, mock_geocoder):
        result = await mock_geocoder.route_waypoints(["Boulder", "Denver"])
        assert len(result.legs) == 1
        assert isinstance(result.legs[0], RouteLegItem)

    async def test_route_total_distance(self, mock_geocoder):
        result = await mock_geocoder.route_waypoints(["Boulder", "Denver"])
        assert result.total_distance_m >= 0

    async def test_route_bbox(self, mock_geocoder):
        result = await mock_geocoder.route_waypoints(["Boulder", "Denver"])
        assert len(result.bbox) == 4

    async def test_route_too_few_waypoints(self, mock_geocoder):
        with pytest.raises(ValueError, match="at least 2"):
            await mock_geocoder.route_waypoints(["Boulder"])

    async def test_route_three_waypoints(self, mock_geocoder):
        result = await mock_geocoder.route_waypoints(["A", "B", "C"])
        assert len(result.waypoints) == 3
        assert len(result.legs) == 2


class TestCacheEntries:
    def test_cache_entries_starts_zero(self, mock_geocoder):
        assert mock_geocoder.cache_entries == 0
