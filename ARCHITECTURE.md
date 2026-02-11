# Architecture

This document describes the design principles, module structure, and key patterns
used in chuk-mcp-geocoder.

## Design Principles

### 1. Async-First

All tool entry points are `async`. The Nominatim HTTP client uses `httpx.AsyncClient`
for non-blocking I/O. Rate limiting is handled via `asyncio.Lock` so the event loop
is never blocked by sleep calls.

### 2. Single Responsibility — Tools Never Touch HTTP

Tool functions validate inputs, call `Geocoder`, and format JSON responses.
They never make HTTP requests directly. `Geocoder` owns the orchestration layer
(validation, shaping, multi-zoom discovery), while `NominatimClient` owns the
full HTTP pipeline: rate limiting, caching, request construction, and error handling.

### 3. Pydantic v2 Native — No Dict Goop

All responses use Pydantic models with `model_config = ConfigDict(extra="forbid")`.
This catches typos at serialisation time rather than silently passing unknown fields.

### 4. No Magic Strings

Every repeated string lives in `constants.py` as a class attribute or
module-level constant. Server config, Nominatim settings, error messages,
success messages, zoom levels, and tool lists are all constants — never inline strings.

### 5. Respectful API Usage

The public Nominatim API has a strict usage policy: maximum 1 request per second,
meaningful User-Agent, and optional email contact. This server enforces rate
limiting via `asyncio.Lock` + monotonic time, caches aggressively (1-hour TTL,
1000-entry LRU), and identifies itself with a descriptive User-Agent header.

### 6. Composable Outputs — The DEM/STAC Bridge

Bounding boxes are always `[west, south, east, north]` floats — the exact format
expected by DEM and STAC servers. `bbox_from_place` is the key bridge tool that
lets an LLM resolve "Mersea Island" into a bbox and pass it directly to
`dem_fetch` or `stac_search` without any transformation.

### 7. Test Coverage >90% per File

183 tests across 8 test files. Overall project coverage is 94%+.
Tests mock at the `Geocoder` level for tool tests, and use `respx` (httpx mock
library) for HTTP-level unit tests of `NominatimClient`.

### 8. Graceful Degradation

Errors return structured JSON (`{"error": "..."}`) — never unhandled exceptions
or stack traces. Invalid coordinates, empty queries, and API failures all produce
clear error messages via `ErrorResponse`.

---

## Module Dependency Graph

```
server.py                         # CLI entry point (sync)
  └── async_server.py             # Async server setup, tool registration
       ├── tools/geocoding/api.py       # geocode, reverse_geocode, bbox_from_place
       ├── tools/discovery/api.py       # nearby_places, admin_boundaries, status, capabilities
       └── core/geocoder.py             # Async manager — validation, parsing, orchestration
            └── core/nominatim.py       # Async HTTP client — rate limit, LRU cache

models/responses.py               # Pydantic response models (extra="forbid")
constants.py                      # Config, messages, metadata, zoom levels
```

---

## Component Responsibilities

### `server.py`

Synchronous entry point. Parses command-line arguments (stdio/http mode),
loads environment variables from `.env`, and delegates to the async server.
This is the only file that touches `sys.argv` or `os.environ` directly.

Supports auto-detection: if `MCP_STDIO` is set or `stdin` is not a TTY,
defaults to stdio mode. Otherwise starts HTTP on port 8010.

### `async_server.py`

Creates the `ChukMCPServer("chuk-mcp-geocoder")` MCP instance, instantiates
`Geocoder`, and registers all tool modules. Each tool module receives the MCP
instance and the shared `Geocoder`. No artifact store is needed — geocoding
returns small text responses, not binary data.

### `core/nominatim.py`

Low-level async HTTP client for the Nominatim API. Manages:

- **Lazy httpx client**: Created on first request, reused across calls
- **Rate limiting**: `asyncio.Lock` + `time.monotonic()` enforces minimum 1-second
  gap between requests to comply with Nominatim usage policy
- **LRU cache**: `OrderedDict`-based with TTL (1 hour) and max size (1000 entries).
  Cache key is MD5 hash of endpoint + sorted params JSON. On hit, entry moves to
  end (most recently used). On overflow, oldest entry is evicted.
- **Methods**: `search()`, `reverse()`, `lookup()`, `close()`
- **Error handling**: Raises `RuntimeError` for 429 (rate limit) and non-200
  responses. Raises `ConnectionError` for network/timeout failures.

Standalone helper functions (independently testable):
- `convert_bbox()` — Nominatim `[min_lat, max_lat, min_lon, max_lon]` strings →
  standard `[west, south, east, north]` floats
- `bbox_buffer_for_rank()` — Place rank → buffer degrees for synthetic bboxes
- `compute_area_km2()` — Approximate bbox area using latitude-corrected degrees
- `haversine_distance()` — Great-circle distance between two points in metres

### `core/geocoder.py`

Async manager/orchestrator. Wraps `NominatimClient` with input validation,
result parsing, and typed dataclass returns. This layer exists to:

1. **Validate** — Check coordinates, query strings before any API call
2. **Parse** — Convert raw Nominatim JSON into typed dataclasses
3. **Orchestrate** — Multi-step operations (nearby uses multiple zoom levels + viewbox search)
4. **Shape** — Ensure consistent output format (bbox conversion, area calculation)

Result dataclasses: `GeocodeItem`, `ReverseResult`, `BboxResult`, `NearbyItem`,
`AdminBoundaryItem`.

Methods:
- `geocode()` — Forward geocode with result parsing
- `reverse_geocode()` — Reverse geocode with result parsing
- `bbox_from_place()` — Single-result geocode → bbox + area
- `nearby_places()` — Multi-zoom reverse + viewbox search, deduped and sorted by distance
- `admin_boundaries()` — Reverse geocode → address component hierarchy

### `models/responses.py`

Pydantic v2 response models for every tool. All use `extra="forbid"` to catch
serialisation errors early. Includes `ErrorResponse`, `GeocodeResult`,
`GeocodeResponse`, `ReverseGeocodeResponse`, `BboxResponse`, `NearbyPlace`,
`NearbyPlacesResponse`, `AdminBoundaryLevel`, `AdminBoundaryResponse`,
`StatusResponse`, `CapabilitiesResponse`.

Every response model implements `to_text()` for human-readable output mode.
The `format_response(model, output_mode)` helper dispatches between JSON
(default) and text modes.

### `constants.py`

All magic strings, API metadata, and configuration values. Includes:
- `ServerConfig` — server name and version
- `NominatimConfig` — base URL, user agent, rate limit, cache settings, timeouts
- `EnvVar` — environment variable names
- `ZoomLevel` — Nominatim reverse geocode detail levels (COUNTRY=3 through BUILDING=18)
- `PLACE_RANK_BUFFERS` — rank-range-to-degrees mapping for synthetic bboxes
- `ADMIN_LEVEL_KEYS` — address key hierarchy (country → neighbourhood)
- `GEOCODING_TOOLS`, `DISCOVERY_TOOLS`, `ALL_TOOLS` — tool name lists
- `ErrorMessages` — format-string error templates
- `SuccessMessages` — format-string success templates

---

## Data Flows

### Forward Geocode

```
1. geocode(query="Boulder", limit=5)
   └── tools/geocoding/api.py
       └── geocoder.geocode(query, limit)
           ├── _validate_query(query)
           └── nominatim.search(query, limit)
               ├── _cache_key("search", params)
               ├── _cache_get(key) → hit? return cached
               ├── _rate_limit() → asyncio.sleep if < 1s since last request
               └── httpx.get("/search", params) → parse JSON → _cache_put()
```

### Reverse Geocode

```
2. reverse_geocode(lat=40.0, lon=-105.0, zoom=18)
   └── tools/geocoding/api.py
       └── geocoder.reverse_geocode(lat, lon, zoom)
           ├── _validate_coordinates(lat, lon)
           └── nominatim.reverse(lat, lon, zoom)
               └── (same cache + rate limit pipeline as search)
```

### Bbox from Place (DEM/STAC Bridge)

```
3. bbox_from_place(query="Mersea Island")
   └── tools/geocoding/api.py
       └── geocoder.bbox_from_place(query)
           ├── _validate_query(query)
           ├── nominatim.search(query, limit=1)
           ├── _parse_search_result(raw) → GeocodeItem
           │     └── convert_bbox(boundingbox) or fallback from place_rank
           ├── compute_area_km2(bbox)
           └── BboxResult(place_name, bbox, center, area_km2)
```

### Nearby Places (Multi-Strategy Discovery)

```
4. nearby_places(lat=40.0, lon=-105.0, limit=10)
   └── tools/discovery/api.py
       └── geocoder.nearby_places(lat, lon, limit)
           ├── _validate_coordinates(lat, lon)
           ├── for zoom in [BUILDING, STREET, SUBURB, CITY]:
           │     └── nominatim.reverse(lat, lon, zoom)
           │         └── deduplicate by display_name
           │         └── haversine_distance() for each result
           ├── nominatim.search(viewbox=±0.01°, bounded=True)
           │     └── deduplicate + haversine_distance()
           └── sort by distance → return items[:limit]
```

### Admin Boundaries

```
5. admin_boundaries(lat=40.0, lon=-105.0)
   └── tools/discovery/api.py
       └── geocoder.admin_boundaries(lat, lon)
           ├── _validate_coordinates(lat, lon)
           ├── nominatim.reverse(lat, lon, zoom=BUILDING)
           └── for (addr_key, level_name) in ADMIN_LEVEL_KEYS:
                 └── if addr_key in address → AdminBoundaryItem(level, name)
```

### Status / Capabilities (No API Calls)

```
6. geocoder_status() / geocoder_capabilities()
   └── tools/discovery/api.py
       └── Read from constants + geocoder.cache_entries
```

---

## Key Patterns

### Rate Limiting

Nominatim's usage policy requires maximum 1 request per second for the public API.
The rate limiter uses `asyncio.Lock` to serialise requests and `time.monotonic()`
to track elapsed time:

```python
async with self._rate_lock:
    elapsed = time.monotonic() - self._last_request_time
    if elapsed < RATE_LIMIT_SECONDS:
        await asyncio.sleep(RATE_LIMIT_SECONDS - elapsed)
    self._last_request_time = time.monotonic()
```

This guarantees compliance even under concurrent tool calls. For private
Nominatim instances, the rate limit can be adjusted.

### LRU Cache with TTL

`NominatimClient._cache` is an `OrderedDict[str, CacheEntry]` where each entry
stores the response data and a creation timestamp:

- **Cache key**: MD5 hash of `"{endpoint}:{sorted_params_json}"`
- **TTL**: 1 hour (3600 seconds). Expired entries are evicted on access.
- **Max size**: 1000 entries. When full, the oldest (first) entry is evicted.
- **LRU**: On cache hit, the entry is moved to the end via `move_to_end()`.

### Bbox Format Conversion

Nominatim returns bounding boxes as `[min_lat, max_lat, min_lon, max_lon]` strings.
Standard geospatial format (and what DEM/STAC servers expect) is
`[west, south, east, north]` = `[min_lon, min_lat, max_lon, max_lat]` floats.

The `convert_bbox()` function handles this counterintuitive reordering:

```python
min_lat, max_lat, min_lon, max_lon = [float(x) for x in nominatim_bbox]
return [min_lon, min_lat, max_lon, max_lat]  # [west, south, east, north]
```

### Fallback Bbox from Place Rank

When Nominatim omits the `boundingbox` field (rare but possible), a synthetic
bbox is computed from the result's latitude/longitude + a buffer based on
`place_rank`. Country-level results get a 10° buffer; building-level results
get 0.001° (~111m). This ensures `bbox_from_place` always returns a usable bbox.

### Nearby Places — Multi-Strategy Discovery

`nearby_places` combines two strategies to discover places at different scales:

1. **Multi-zoom reverse geocoding** — Reverse geocode at zoom levels 18 (building),
   16 (street), 14 (suburb), and 10 (city) to discover places at increasing radii
2. **Viewbox search** — Search within a ±0.01° box (~1.1 km) around the point
   for additional named places

Results are deduplicated by `display_name`, enriched with haversine distance
from the query point, sorted by distance, and truncated to the requested limit.

### Tool Registration Pattern

Each tool module exports a `register_*_tools(mcp, geocoder)` function that
uses the `@mcp.tool()` decorator pattern:

```python
def register_geocoding_tools(mcp, geocoder):
    @mcp.tool()
    async def geocode(query: str, limit: int = 5, output_mode: str = "json") -> str:
        try:
            items = await geocoder.geocode(query, limit=limit)
            response = GeocodeResponse(...)
            return format_response(response, output_mode)
        except ValueError as e:
            return format_response(ErrorResponse(error=str(e)))
```

Every tool follows this pattern: try/except → ErrorResponse on failure,
`format_response(model, output_mode)` for JSON or text output.

### Haversine Distance

Distance calculations use the haversine formula for great-circle distance on
a sphere (R = 6,371,000 m). Used by `nearby_places` to sort results by distance
from the query point.

### Area Calculation

`compute_area_km2()` approximates bbox area by treating longitude degrees as
narrower at higher latitudes:

```python
width_km = (east - west) * 111.32 * cos(radians(mid_lat))
height_km = (north - south) * 111.32
area = abs(width_km * height_km)
```

This is accurate enough for geocoding purposes (the bbox is approximate anyway).

---

## Cross-Server Integration

The geocoder is designed as the entry point for the chuk MCP geospatial stack:

```
User: "Show me the terrain of Mersea Island"

1. geocoder → bbox_from_place("Mersea Island")
   → bbox: [0.8918, 51.7608, 0.9592, 51.8002], area_km2: 28.5

2. dem → dem_fetch(bbox=[0.8918, 51.7608, 0.9592, 51.8002], source="cop30")
   → elevation GeoTIFF + hillshade preview

3. stac → stac_search(bbox=[0.8918, 51.7608, 0.9592, 51.8002])
   → satellite imagery catalog
```

The bbox format is identical across all three servers — no transformation needed.
