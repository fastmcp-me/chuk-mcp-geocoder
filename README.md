# chuk-mcp-geocoder

Geocoding & Place Discovery MCP Server via Nominatim/OpenStreetMap.

Provides forward/reverse geocoding, bounding box extraction, nearby places discovery, and administrative boundary lookup — designed to work alongside other MCP geospatial servers (DEM, STAC, etc.).

## Tools

| Tool | Description |
|------|-------------|
| `geocode` | Place name to coordinates (lat, lon, bbox, address) |
| `reverse_geocode` | Coordinates to place name and address |
| `bbox_from_place` | Place name to `[west, south, east, north]` bbox for DEM/STAC tools |
| `nearby_places` | Find places near a coordinate at multiple scales |
| `admin_boundaries` | Administrative hierarchy (country, state, county, city, suburb) |
| `geocoder_status` | Server status and cache statistics |
| `geocoder_capabilities` | Full capabilities listing with LLM guidance |

## Quick Start

```bash
# Install
uv sync

# Run tests
uv run pytest

# Run server (stdio mode for MCP CLI)
uv run chuk-mcp-geocoder stdio

# Run server (HTTP mode)
uv run chuk-mcp-geocoder http --port 8010
```

## Usage with MCP CLI

```bash
uv run mcp-cli --server geocoder,dem,stac
```

Then ask:

> "Get the elevation profile for the Strood causeway connecting Mersea Island to the mainland"

The LLM will use `bbox_from_place` or `geocode` to resolve the location, then pass coordinates to the DEM server.

## Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `NOMINATIM_EMAIL` | Contact email for Nominatim API | (none) |
| `NOMINATIM_BASE_URL` | Custom Nominatim instance URL | `https://nominatim.openstreetmap.org` |
| `MCP_STDIO` | Force stdio transport mode | (auto-detect) |

## Architecture

Follows the same 5-layer pattern as chuk-mcp-dem:

1. **core/nominatim.py** — Async HTTP client with rate limiting and LRU cache
2. **core/geocoder.py** — Async manager with validation and typed dataclass results
3. **models/responses.py** — Pydantic v2 response models (`extra="forbid"`, `to_text()`)
4. **constants.py** — All configuration, messages, and metadata
5. **tools/*/api.py** — MCP tool registration with `@mcp.tool()` decorators

## Data Source

All geocoding data comes from [OpenStreetMap](https://www.openstreetmap.org/) via the [Nominatim](https://nominatim.org/) API.

- Data license: [ODbL 1.0](https://opendatacommons.org/licenses/odbl/)
- API rate limit: 1 request/second (public API)
- Results are cached in-memory (1 hour TTL)

## License

Apache-2.0
