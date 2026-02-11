# chuk-mcp-geocoder — Roadmap

## Phase 1: Core Foundation ✅

Minimum viable geocoding server with clean architecture.

- [x] Project scaffolding (pyproject.toml, src layout, uv)
- [x] `constants.py` — all config, messages, metadata
- [x] `core/nominatim.py` — async HTTP client with rate limiting (1 req/s)
- [x] In-memory LRU cache with TTL (1 hour default)
- [x] `core/geocoder.py` — async manager with input validation
- [x] `models/responses.py` — Pydantic v2 models with `extra="forbid"` and `to_text()`
- [x] `geocode` tool — forward geocoding
- [x] `reverse_geocode` tool — coordinates to place name
- [x] `bbox_from_place` tool — place name to `[west, south, east, north]`
- [x] `nearby_places` tool — multi-radius place discovery
- [x] `admin_boundaries` tool — full administrative hierarchy lookup
- [x] `geocoder_status` tool — health and cache stats
- [x] `geocoder_capabilities` tool — full schema + LLM guidance text
- [x] Area calculation (km²) in bbox results
- [x] Distance calculation from center point (haversine)
- [x] Zoom level mapping for reverse geocode detail control
- [x] Country code filtering for forward geocode
- [x] Structured address component parsing
- [x] MCP server setup with stdio and HTTP transport
- [x] Unit tests (183 tests, 94%+ coverage)
- [x] README.md, SPEC.md, ARCHITECTURE.md, ROADMAP.md
- [x] GitHub Actions (test, publish, release)
- [x] Dockerfile, Makefile

## Phase 2: Geospatial Stack Integration ✅

Bridge tools that make geocoder the entry point for DEM/STAC workflows.

- [x] Configurable bbox padding (fractional expansion) in `bbox_from_place`
- [x] Language preference support (`Accept-Language` parameter)
- [x] Cross-server bbox format validation tests
- [x] `server.json` for MCP CLI config

## Phase 3: Discovery & Context ✅

Richer location intelligence beyond simple geocoding.

- [x] OSM category filtering for `nearby_places`
- [x] Retry with exponential backoff on Nominatim 429/503
- [x] Cache key normalization (case, whitespace folding)

## Phase 4: Batch & Routing ✅

Multi-location workflows and route-aware geocoding.

- [x] `batch_geocode` tool — multiple place names in one call (JSON array input)
- [x] Batch rate limit management (sequential with 1 req/s pacing, per-query error handling)
- [x] `route_waypoints` tool — ordered geocode for A → B → C routes with leg distances
- [x] Midpoint calculation between two coordinates
- [x] `distance_matrix` tool — haversine distances between multiple points (NxN matrix)
- [x] Bounding box union (merge multiple place bboxes)
- [x] Updated capabilities guidance text for batch tools

## Phase 5: Enhanced Data Sources

Beyond basic Nominatim — richer place data.

- [ ] OSM Overpass API integration for complex spatial queries
- [ ] POI density heatmap data within a bbox
- [ ] Elevation-aware nearby (integrate with DEM server)
- [ ] Timezone lookup from coordinates
- [ ] What3Words-style grid reference support
- [ ] Custom Nominatim instance support (docker-compose for local)
- [ ] Photon geocoder as alternative backend
- [ ] Provider abstraction layer (swap Nominatim/Photon/custom)

## Phase 6: Intelligence Layer

LLM-optimized features for smarter geospatial reasoning.

- [ ] Fuzzy place name matching with confidence scores
- [ ] Disambiguation tool — "Springfield" → ranked list with context
- [ ] Place type inference from natural language ("the river near Oxford")
- [ ] Coordinate format detection and normalization (DMS, UTM, MGRS)
- [ ] Semantic place descriptions for LLM context ("coastal island connected by tidal causeway")
- [ ] Query intent classification (geocode vs discover vs navigate)
- [ ] Suggested next tools based on result type (bbox → DEM, POI → nearby)

## Phase 7: Observability & Ops

Production monitoring and operational tooling.

- [ ] OpenTelemetry trace spans per tool call
- [ ] Prometheus metrics (request count, latency, cache hit rate)
- [ ] Rate limit headroom reporting
- [ ] API usage dashboard data
- [ ] Cache warming for frequently queried regions
- [ ] Health check endpoint for container orchestration
- [ ] Configurable log levels per component

## Non-Goals

Things explicitly out of scope for this server:

- **Routing / directions** — use a dedicated routing MCP server (OSRM/Valhalla)
- **Map tile serving** — rendering is a separate concern
- **Persistent storage** — cache is ephemeral by design
- **Paid geocoding APIs** — this server is OSM/Nominatim only; a separate provider-abstraction server could wrap Google/Mapbox
- **Indoor mapping** — OSM indoor data is too sparse to be reliable
