# chuk-mcp-geocoder — Specification

## Purpose

Geocoding & Place Discovery MCP Server powered by Nominatim/OpenStreetMap. Provides forward/reverse geocoding, bounding box extraction, nearby place discovery, and administrative boundary lookup — designed as the location resolution layer for the chuk MCP geospatial stack (DEM, STAC, etc.).

## Design Principles

1. **Composable** — bbox and coordinate outputs are shaped for direct consumption by DEM/STAC servers
2. **Respectful** — enforces Nominatim rate limits (1 req/s public API), caches aggressively
3. **5-layer architecture** — follows chuk-mcp-dem pattern: client → manager → models → constants → tools
4. **Zero API keys** — works out of the box with public Nominatim; supports private instances via env var
5. **LLM-friendly** — every response includes `to_text()` for clean token-efficient summaries

## Architecture

```
┌─────────────────────────────────────────────┐
│                MCP Transport                │
│            (stdio / HTTP / SSE)             │
├─────────────────────────────────────────────┤
│              tools/*/api.py                 │
│         @mcp.tool() registrations           │
├─────────────────────────────────────────────┤
│            core/geocoder.py                 │
│    Async manager — validation, shaping      │
├─────────────────────────────────────────────┤
│           core/nominatim.py                 │
│  Async HTTP client — rate limit, LRU cache  │
├─────────────────────────────────────────────┤
│          models/responses.py                │
│   Pydantic v2 (extra="forbid", to_text())   │
├─────────────────────────────────────────────┤
│            constants.py                     │
│    Config, messages, metadata, defaults      │
└─────────────────────────────────────────────┘
```

## Tools

### geocode

Forward geocode a place name to coordinates.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | yes | Place name or address |
| `limit` | int | no | Max results (default: 1, max: 10) |
| `country_codes` | string | no | Comma-separated ISO 3166-1 codes to restrict search |
| `language` | string | no | Preferred response language (e.g., "en") |

**Returns:** `GeocodeResult` — lat, lon, display_name, bbox, osm_type, osm_id, importance, address_components

**Example:**
```
geocode("Mersea Island, Essex")
→ lat: 51.7805, lon: 0.9255, bbox: [0.8918, 51.7608, 0.9592, 51.8002]
```

### reverse_geocode

Coordinates to place name and address components.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `lat` | float | yes | Latitude (-90 to 90) |
| `lon` | float | yes | Longitude (-180 to 180) |
| `zoom` | int | no | Detail level: 3=country, 10=city, 18=building (default: 18) |

**Returns:** `ReverseGeocodeResult` — display_name, address_components, osm_type, osm_id, bbox

### bbox_from_place

Resolve a place name to a `[west, south, east, north]` bounding box — the bridge tool between geocoder and DEM/STAC servers.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | yes | Place name or address |
| `padding` | float | no | Fractional padding to expand bbox (default: 0.0, e.g., 0.1 = 10%) |

**Returns:** `BboxResult` — bbox array, center lat/lon, area_km2, place_name

**Example:**
```
bbox_from_place("Strood causeway, Mersea Island", padding=0.05)
→ bbox: [0.8950, 51.7780, 0.9180, 51.7920], area_km2: ~2.3
```

### nearby_places

Discover places near a coordinate, searching at multiple radius scales.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `lat` | float | yes | Center latitude |
| `lon` | float | yes | Center longitude |
| `radius_km` | float | no | Search radius in km (default: 1.0) |
| `limit` | int | no | Max results per category (default: 5) |
| `categories` | list[string] | no | OSM categories to include (default: all) |

**Returns:** `NearbyResult` — list of places with name, distance_m, category, lat, lon

**Categories:** amenity, tourism, natural, historic, leisure, shop, transport

### admin_boundaries

Resolve full administrative hierarchy for a location.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `lat` | float | yes | Latitude |
| `lon` | float | yes | Longitude |

**Returns:** `AdminResult` — country, country_code, state, county, city, town, village, suburb, postcode

### geocoder_status

Server health, cache statistics, and rate limit state.

**Parameters:** None

**Returns:** `StatusResult` — uptime, cache_size, cache_hits, cache_misses, hit_rate, requests_total, rate_limit_state

### geocoder_capabilities

Full capabilities listing with parameter schemas and LLM guidance text.

**Parameters:** None

**Returns:** `CapabilitiesResult` — tool list with descriptions, parameter schemas, usage tips, and cross-server integration guidance

## Response Models

All responses are Pydantic v2 with `model_config = ConfigDict(extra="forbid")`.

Every model implements `to_text() -> str` returning a clean, token-efficient summary suitable for LLM consumption.

```python
class GeocodeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lat: float
    lon: float
    display_name: str
    bbox: list[float]  # [west, south, east, north]
    osm_type: str
    osm_id: int
    importance: float
    address: AddressComponents

    def to_text(self) -> str: ...
```

## Core Client — `NominatimClient`

```python
class NominatimClient:
    """Async Nominatim HTTP client with rate limiting and caching."""

    def __init__(
        self,
        email: str | None = None,
        base_url: str = NOMINATIM_BASE_URL,
        cache_ttl: int = 3600,        # 1 hour
        cache_maxsize: int = 1024,
        rate_limit: float = 1.0,       # seconds between requests
    ): ...

    async def search(self, query: str, **kwargs) -> list[dict]: ...
    async def reverse(self, lat: float, lon: float, **kwargs) -> dict: ...
    async def lookup(self, osm_ids: list[str], **kwargs) -> list[dict]: ...

    @property
    def cache_stats(self) -> CacheStats: ...
```

**Rate limiting:** Token bucket, 1 request/second for public Nominatim. Configurable for private instances.

**Caching:** In-memory LRU with TTL. Cache key = normalized query + params hash.

## Configuration

All configuration via `constants.py` and environment variables:

```python
# constants.py
NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"
NOMINATIM_EMAIL = None          # set via env
RATE_LIMIT_SECONDS = 1.0
CACHE_TTL = 3600
CACHE_MAXSIZE = 1024
DEFAULT_LANGUAGE = "en"
MAX_RESULTS = 10

# Zoom level mapping for reverse geocoding
ZOOM_LEVELS = {
    "country": 3,
    "state": 5,
    "county": 8,
    "city": 10,
    "suburb": 14,
    "street": 16,
    "building": 18,
}
```

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `NOMINATIM_EMAIL` | Contact email for API (recommended) | None |
| `NOMINATIM_BASE_URL` | Custom Nominatim instance | `https://nominatim.openstreetmap.org` |
| `GEOCODER_CACHE_TTL` | Cache TTL in seconds | 3600 |
| `GEOCODER_CACHE_SIZE` | Max cache entries | 1024 |
| `MCP_STDIO` | Force stdio transport | auto-detect |

## Cross-Server Integration

The geocoder is designed as the entry point for geospatial workflows:

```
User: "Show me the elevation of Mersea Island"

1. geocoder: bbox_from_place("Mersea Island") → bbox
2. dem:      get_elevation_data(bbox) → elevation grid
3. stac:     search_imagery(bbox) → satellite imagery
```

**bbox_from_place** output format matches DEM/STAC input format exactly — no transformation needed.

## File Structure

```
chuk-mcp-geocoder/
├── pyproject.toml
├── README.md
├── SPEC.md
├── ARCHITECTURE.md
├── ROADMAP.md
├── src/
│   └── chuk_mcp_geocoder/
│       ├── __init__.py
│       ├── server.py              # CLI entry point + transport selection
│       ├── async_server.py        # MCP server setup + tool registration
│       ├── constants.py           # All config, messages, metadata
│       ├── core/
│       │   ├── __init__.py
│       │   ├── nominatim.py       # Async HTTP client
│       │   └── geocoder.py        # Async manager + validation
│       ├── models/
│       │   ├── __init__.py
│       │   └── responses.py       # Pydantic v2 response models
│       └── tools/
│           ├── __init__.py
│           ├── geocoding/
│           │   ├── __init__.py
│           │   └── api.py         # geocode, reverse_geocode, bbox_from_place
│           └── discovery/
│               ├── __init__.py
│               └── api.py         # nearby_places, admin_boundaries, status, capabilities
├── tests/
│   ├── conftest.py
│   ├── test_constants.py
│   ├── test_nominatim.py
│   ├── test_geocoder.py
│   ├── test_models.py
│   ├── test_geocoding_tools.py
│   ├── test_discovery_tools.py
│   └── test_server.py
├── examples/
│   └── tool_runner.py
└── .github/
    └── workflows/
        ├── test.yml
        ├── publish.yml
        └── release.yml
```

## Testing

```bash
# Unit tests (mocked Nominatim)
uv run pytest tests/ -v

# Integration tests (live API — rate limited)
uv run pytest tests/ -v -m integration

# Cache behavior
uv run pytest tests/test_nominatim.py -k cache
```

## Data Attribution

All data from [OpenStreetMap](https://www.openstreetmap.org/) via [Nominatim](https://nominatim.org/).
- License: [ODbL 1.0](https://opendatacommons.org/licenses/odbl/)
- Nominatim Usage Policy: [https://operations.osmfoundation.org/policies/nominatim/](https://operations.osmfoundation.org/policies/nominatim/)
