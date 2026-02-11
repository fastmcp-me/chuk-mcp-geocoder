"""Shared test fixtures for chuk-mcp-geocoder."""

import pytest
from unittest.mock import AsyncMock, MagicMock


# Sample Nominatim API responses
SAMPLE_SEARCH_RESPONSE = [
    {
        "place_id": 123456,
        "osm_type": "relation",
        "osm_id": 9876543,
        "lat": "40.0149856",
        "lon": "-105.2705456",
        "display_name": "Boulder, Boulder County, Colorado, United States",
        "boundingbox": ["39.9138", "40.0940", "-105.3014", "-105.1731"],
        "importance": 0.65,
        "place_rank": 16,
        "address": {
            "city": "Boulder",
            "county": "Boulder County",
            "state": "Colorado",
            "country": "United States",
            "country_code": "us",
        },
        "category": "place",
        "type": "city",
    }
]

SAMPLE_SEARCH_MULTI = [
    SAMPLE_SEARCH_RESPONSE[0],
    {
        "place_id": 789012,
        "osm_type": "node",
        "osm_id": 1111111,
        "lat": "39.9994",
        "lon": "-105.2094",
        "display_name": "Boulder, Weld County, Colorado, United States",
        "boundingbox": ["39.9800", "40.0200", "-105.2400", "-105.1800"],
        "importance": 0.35,
        "place_rank": 18,
        "address": {
            "town": "Boulder",
            "county": "Weld County",
            "state": "Colorado",
            "country": "United States",
            "country_code": "us",
        },
        "category": "place",
        "type": "town",
    },
]

SAMPLE_REVERSE_RESPONSE = {
    "place_id": 654321,
    "osm_type": "node",
    "osm_id": 1234567,
    "lat": "40.0149856",
    "lon": "-105.2705456",
    "display_name": "Boulder, Boulder County, Colorado, United States",
    "boundingbox": ["39.9138", "40.0940", "-105.3014", "-105.1731"],
    "address": {
        "city": "Boulder",
        "county": "Boulder County",
        "state": "Colorado",
        "country": "United States",
        "country_code": "us",
    },
    "place_rank": 16,
    "importance": 0.65,
    "type": "city",
}


@pytest.fixture
def mock_nominatim_client():
    """Mock NominatimClient with canned responses."""
    client = AsyncMock()
    client.search = AsyncMock(return_value=SAMPLE_SEARCH_RESPONSE)
    client.reverse = AsyncMock(return_value=SAMPLE_REVERSE_RESPONSE)
    client.lookup = AsyncMock(return_value=[])
    client._base_url = "https://nominatim.openstreetmap.org"
    client._cache = {}
    return client


@pytest.fixture
def mock_geocoder(mock_nominatim_client):
    """Geocoder with mocked NominatimClient."""
    from chuk_mcp_geocoder.core.geocoder import Geocoder

    geocoder = Geocoder(client=mock_nominatim_client)
    return geocoder


@pytest.fixture
def mock_mcp():
    """Mock ChukMCPServer."""
    mcp = MagicMock()
    mcp.tool = MagicMock(return_value=lambda fn: fn)
    return mcp
