# chuk-mcp-geocoder

Geocoding & Place Discovery MCP Server via Nominatim/OpenStreetMap.

Provides forward/reverse geocoding, bounding box extraction, nearby places discovery, batch geocoding, route waypoints, and administrative boundary lookup — designed to work alongside other MCP geospatial servers (DEM, STAC, etc.).

> This is a demonstration project provided as-is for learning and testing purposes.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## Tools

| Tool | Description |
|------|-------------|
| `geocode` | Place name to coordinates (lat, lon, bbox, address) |
| `reverse_geocode` | Coordinates to place name and address |
| `bbox_from_place` | Place name to `[west, south, east, north]` bbox for DEM/STAC tools |
| `nearby_places` | Find places near a coordinate at multiple scales |
| `admin_boundaries` | Administrative hierarchy (country, state, county, city, suburb) |
| `batch_geocode` | Geocode multiple place names in one call |
| `route_waypoints` | Geocode waypoints in order and compute route distances |
| `distance_matrix` | Compute haversine distance matrix between multiple points |
| `geocoder_status` | Server status and cache statistics |
| `geocoder_capabilities` | Full capabilities listing with LLM guidance |

## Installation

### Using uvx (Recommended - No Installation Required!)

The easiest way to use the server is with `uvx`, which runs it without installing:

```bash
uvx chuk-mcp-geocoder
```

This automatically downloads and runs the latest version. Perfect for Claude Desktop!

### Using uv (Recommended for Development)

```bash
# Install from PyPI
uv pip install chuk-mcp-geocoder

# Or clone and install from source
git clone <repository-url>
cd chuk-mcp-geocoder
uv sync --dev
```

### Using pip (Traditional)

```bash
pip install chuk-mcp-geocoder
```

## Usage

### With Claude Desktop

#### Option 1: Use the Public Server (Easiest)

Connect to the hosted public server at `chuk-mcp-geocoder.fly.dev`:

**MacOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "geocoder": {
      "url": "https://chuk-mcp-geocoder.fly.dev/mcp"
    }
  }
}
```

#### Option 2: Streamable HTTP URL (Local)

Run the server locally and connect via HTTP:

```json
{
  "mcpServers": {
    "geocoder": {
      "url": "http://localhost:8010/mcp"
    }
  }
}
```

Then start the server:

```bash
uvx chuk-mcp-geocoder http
```

#### Option 3: Run Locally with uvx

```json
{
  "mcpServers": {
    "geocoder": {
      "command": "uvx",
      "args": ["chuk-mcp-geocoder"]
    }
  }
}
```

#### Option 4: Run Locally with pip

```json
{
  "mcpServers": {
    "geocoder": {
      "command": "chuk-mcp-geocoder"
    }
  }
}
```

### Standalone

Run the server directly:

```bash
# With uvx (recommended - always latest version)
uvx chuk-mcp-geocoder

# With uvx in HTTP mode
uvx chuk-mcp-geocoder http

# Or if installed locally
chuk-mcp-geocoder
chuk-mcp-geocoder http
```

Or with uv/Python:

```bash
# STDIO mode (default, for MCP clients)
uv run chuk-mcp-geocoder
# or: python -m chuk_mcp_geocoder.server

# HTTP mode (for web access and streamable HTTP)
uv run chuk-mcp-geocoder http
# or: python -m chuk_mcp_geocoder.server http

# HTTP mode with custom host/port
uv run chuk-mcp-geocoder http --host 0.0.0.0 --port 9000
```

**STDIO mode** is for MCP clients like Claude Desktop and mcp-cli.
**HTTP mode** runs a web server on http://localhost:8010 for HTTP-based MCP clients.

### Usage with MCP CLI

```bash
uv run mcp-cli --server geocoder,dem,stac
```

Then ask:

> "Get the elevation profile for Mersea Island"

The LLM will use `bbox_from_place` or `geocode` to resolve the location, then pass coordinates to the DEM server.

## Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `NOMINATIM_EMAIL` | Contact email for Nominatim API | (none) |
| `NOMINATIM_BASE_URL` | Custom Nominatim instance URL | `https://nominatim.openstreetmap.org` |
| `MCP_STDIO` | Force stdio transport mode | (auto-detect) |

## Development

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd chuk-mcp-geocoder

# Install with uv (recommended)
uv sync --dev

# Or with pip
pip install -e ".[dev]"
```

### Running Tests

```bash
make test              # Run tests
make test-cov          # Run tests with coverage
make coverage-report   # Show coverage report
```

### Code Quality

```bash
make lint      # Run linters
make format    # Auto-format code
make typecheck # Run type checking
make security  # Run security checks
make check     # Run all checks
```

### Building

```bash
make build           # Build package
make publish-test    # Upload to TestPyPI for testing
make publish-manual  # Manually upload to PyPI (requires PYPI_TOKEN)
make publish         # Create tag and trigger GitHub Actions release
```

## Architecture

Follows the same 5-layer pattern as chuk-mcp-dem:

1. **core/nominatim.py** — Async HTTP client with rate limiting and LRU cache
2. **core/geocoder.py** — Async manager with validation and typed dataclass results
3. **models/responses.py** — Pydantic v2 response models (`extra="forbid"`, `to_text()`)
4. **constants.py** — All configuration, messages, and metadata
5. **tools/*/api.py** — MCP tool registration with `@mcp.tool()` decorators

## Public Server

A public instance is hosted at **chuk-mcp-geocoder.fly.dev** for easy access:

- **URL**: `https://chuk-mcp-geocoder.fly.dev/mcp`
- **Protocol**: MCP over HTTPS (Streamable HTTP)
- **Free to use**: No API key required
- **Always up-to-date**: Running the latest version

Simply add it to your Claude Desktop config:

```json
{
  "mcpServers": {
    "geocoder": {
      "url": "https://chuk-mcp-geocoder.fly.dev/mcp"
    }
  }
}
```

## Data Source

All geocoding data comes from [OpenStreetMap](https://www.openstreetmap.org/) via the [Nominatim](https://nominatim.org/) API.

- Data license: [ODbL 1.0](https://opendatacommons.org/licenses/odbl/)
- API rate limit: 1 request/second (public API)
- Results are cached in-memory (1 hour TTL)

## License

Apache-2.0
