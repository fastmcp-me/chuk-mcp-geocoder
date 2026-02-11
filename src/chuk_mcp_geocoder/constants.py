"""
Constants for chuk-mcp-geocoder server.

All magic strings, API metadata, and configuration values live here.
"""


class ServerConfig:
    NAME = "chuk-mcp-geocoder"
    VERSION = "0.1.0"
    DESCRIPTION = "Geocoding & Place Discovery MCP Server via Nominatim/OpenStreetMap"


class NominatimConfig:
    BASE_URL = "https://nominatim.openstreetmap.org"
    USER_AGENT = "chuk-mcp-geocoder/0.1.0"
    RATE_LIMIT_SECONDS = 1.0
    DEFAULT_FORMAT = "jsonv2"
    DEFAULT_LIMIT = 5
    MAX_LIMIT = 50
    CACHE_TTL_SECONDS = 3600  # 1 hour
    CACHE_MAX_SIZE = 1000
    DEFAULT_ZOOM = 18
    TIMEOUT_SECONDS = 30.0
    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 2.0  # seconds, doubles each attempt
    RETRYABLE_STATUS_CODES = (429, 503)


class EnvVar:
    MCP_STDIO = "MCP_STDIO"
    NOMINATIM_EMAIL = "NOMINATIM_EMAIL"
    NOMINATIM_BASE_URL = "NOMINATIM_BASE_URL"


class ZoomLevel:
    """Nominatim zoom levels for reverse geocoding detail."""

    COUNTRY = 3
    STATE = 5
    COUNTY = 8
    CITY = 10
    SUBURB = 14
    STREET = 16
    BUILDING = 18


# Place rank to bbox buffer mapping (degrees).
# When Nominatim returns no boundingbox, compute one from lat/lon + buffer.
PLACE_RANK_BUFFERS: dict[tuple[int, int], float] = {
    (0, 4): 10.0,  # country
    (5, 8): 2.0,  # state
    (9, 12): 0.5,  # county
    (13, 16): 0.1,  # city
    (17, 20): 0.01,  # suburb
    (21, 26): 0.005,  # street
    (27, 30): 0.001,  # building/address
}

DEFAULT_BBOX_BUFFER = 0.01  # ~1.1 km fallback

# Batch limits
BATCH_MAX_QUERIES = 50

# Tool lists
GEOCODING_TOOLS = ["geocode", "reverse_geocode", "bbox_from_place"]
DISCOVERY_TOOLS = ["nearby_places", "admin_boundaries", "geocoder_status", "geocoder_capabilities"]
BATCH_TOOLS = ["batch_geocode", "route_waypoints", "distance_matrix"]
ALL_TOOLS = GEOCODING_TOOLS + DISCOVERY_TOOLS + BATCH_TOOLS

# Nearby place category constants
NEARBY_CATEGORIES = [
    "amenity",
    "tourism",
    "natural",
    "historic",
    "leisure",
    "shop",
    "transport",
]

# Admin boundary address keys in hierarchy order
ADMIN_LEVEL_KEYS = [
    ("country", "country"),
    ("state", "state"),
    ("county", "county"),
    ("city", "city"),
    ("town", "town"),
    ("village", "village"),
    ("suburb", "suburb"),
    ("neighbourhood", "neighbourhood"),
]


class ErrorMessages:
    NO_RESULTS = "No results found for query '{}'"
    INVALID_COORDINATES = "Invalid coordinates: lat must be -90..90, lon must be -180..180"
    INVALID_LAT = "Invalid latitude {}: must be between -90 and 90"
    INVALID_LON = "Invalid longitude {}: must be between -180 and 180"
    RATE_LIMITED = "Nominatim rate limit exceeded. Please wait and retry."
    API_ERROR = "Nominatim API error (HTTP {}): {}"
    NETWORK_ERROR = "Network error contacting Nominatim: {}"
    INVALID_LIMIT = "limit must be between 1 and {}, got {}"
    INVALID_ZOOM = "zoom must be between 0 and 18, got {}"
    EMPTY_QUERY = "Query string cannot be empty"
    INVALID_JSON = "Invalid JSON: {}"
    BATCH_EMPTY = "Queries list cannot be empty"
    BATCH_TOO_LARGE = "Batch size {} exceeds maximum of {}"
    WAYPOINTS_MIN = "Route requires at least 2 waypoints"
    POINTS_MIN = "Distance matrix requires at least 2 points"


class SuccessMessages:
    GEOCODE_FOUND = "Found {} result(s) for '{}'"
    REVERSE_FOUND = "Reverse geocoded ({}, {}) to: {}"
    BBOX_EXTRACTED = "Bounding box for '{}': [{:.6f}, {:.6f}, {:.6f}, {:.6f}]"
    NEARBY_FOUND = "Found {} place(s) near ({}, {})"
    ADMIN_BOUNDARIES = "Administrative boundaries for ({}, {})"
    STATUS = "Geocoder MCP Server v{}"
    CAPABILITIES = "{} v{} capabilities"
    BATCH_GEOCODE = "Batch geocoded {}/{} queries successfully"
    ROUTE_WAYPOINTS = "Route with {} waypoints, {:.1f} km total"
    DISTANCE_MATRIX = "Distance matrix for {} points"
