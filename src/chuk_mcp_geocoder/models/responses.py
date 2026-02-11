"""
Response models for chuk-mcp-geocoder tools.

All tool responses are Pydantic models for type safety and consistent API.
"""

from pydantic import BaseModel, ConfigDict, Field


def format_response(model: BaseModel, output_mode: str = "json") -> str:
    """Format a response model as JSON or human-readable text.

    Args:
        model: Pydantic response model instance
        output_mode: "json" (default) or "text"

    Returns:
        Formatted string
    """
    if output_mode == "text" and hasattr(model, "to_text"):
        return str(model.to_text())
    return str(model.model_dump_json())


class ErrorResponse(BaseModel):
    """Error response model for tool failures."""

    model_config = ConfigDict(extra="forbid")

    error: str = Field(..., description="Error message describing what went wrong")

    def to_text(self) -> str:
        return f"Error: {self.error}"


class GeocodeResult(BaseModel):
    """Single geocoding result."""

    model_config = ConfigDict(extra="forbid")

    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")
    display_name: str = Field(..., description="Full display name")
    bbox: list[float] = Field(..., description="Bounding box [west, south, east, north]")
    osm_type: str | None = Field(None, description="OSM type (node/way/relation)")
    osm_id: int | None = Field(None, description="OSM ID")
    importance: float | None = Field(None, description="Result importance score (0-1)")
    place_rank: int | None = Field(None, description="Nominatim place rank")
    address: dict[str, str] | None = Field(None, description="Address components")
    category: str | None = Field(None, description="Place category")
    place_type: str | None = Field(None, description="Place type (city, village, etc.)")

    def to_text(self) -> str:
        parts = [f"{self.display_name}"]
        parts.append(f"  Coordinates: {self.lat:.6f}, {self.lon:.6f}")
        bbox_str = ", ".join(f"{b:.6f}" for b in self.bbox)
        parts.append(f"  Bbox: [{bbox_str}]")
        if self.importance is not None:
            parts.append(f"  Importance: {self.importance:.3f}")
        return "\n".join(parts)


class GeocodeResponse(BaseModel):
    """Forward geocoding response."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., description="Original search query")
    results: list[GeocodeResult] = Field(..., description="Geocoding results")
    count: int = Field(..., description="Number of results", ge=0)
    message: str = Field(..., description="Operation result message")

    def to_text(self) -> str:
        lines = [self.message, ""]
        for i, r in enumerate(self.results, 1):
            lines.append(f"{i}. {r.to_text()}")
            lines.append("")
        return "\n".join(lines)


class ReverseGeocodeResponse(BaseModel):
    """Reverse geocoding response."""

    model_config = ConfigDict(extra="forbid")

    lat: float = Field(..., description="Query latitude")
    lon: float = Field(..., description="Query longitude")
    display_name: str = Field(..., description="Full display name of location")
    address: dict[str, str] = Field(..., description="Address components")
    bbox: list[float] = Field(..., description="Bounding box [west, south, east, north]")
    osm_type: str | None = Field(None, description="OSM type (node/way/relation)")
    osm_id: int | None = Field(None, description="OSM ID")
    place_rank: int | None = Field(None, description="Nominatim place rank")
    message: str = Field(..., description="Operation result message")

    def to_text(self) -> str:
        lines = [
            self.message,
            f"Location: {self.display_name}",
            f"Coordinates: {self.lat:.6f}, {self.lon:.6f}",
        ]
        if self.address:
            lines.append("Address:")
            for key, value in self.address.items():
                lines.append(f"  {key}: {value}")
        return "\n".join(lines)


class BboxResponse(BaseModel):
    """Bounding box for a place, formatted for DEM/STAC tools."""

    model_config = ConfigDict(extra="forbid")

    place_name: str = Field(..., description="Resolved place name")
    bbox: list[float] = Field(..., description="Bounding box [west, south, east, north]")
    center: list[float] = Field(..., description="Center point [lon, lat]")
    area_km2: float | None = Field(None, description="Approximate area in km^2")
    message: str = Field(..., description="Operation result message")

    def to_text(self) -> str:
        bbox_str = ", ".join(f"{b:.6f}" for b in self.bbox)
        lines = [
            self.message,
            f"Place: {self.place_name}",
            f"Bbox: [{bbox_str}]",
            f"Center: [{self.center[0]:.6f}, {self.center[1]:.6f}]",
        ]
        if self.area_km2 is not None:
            lines.append(f"Area: {self.area_km2:.2f} km^2")
        return "\n".join(lines)


class NearbyPlace(BaseModel):
    """A single nearby place with distance."""

    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(..., description="Full display name")
    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")
    distance_m: float | None = Field(None, description="Distance from query point in metres")
    place_type: str | None = Field(None, description="Place type")
    osm_type: str | None = Field(None, description="OSM type")
    importance: float | None = Field(None, description="Importance score")

    def to_text(self) -> str:
        dist = f" ({self.distance_m:.0f}m)" if self.distance_m is not None else ""
        return f"{self.display_name}{dist}"


class NearbyPlacesResponse(BaseModel):
    """Response model for nearby places search."""

    model_config = ConfigDict(extra="forbid")

    lat: float = Field(..., description="Query latitude")
    lon: float = Field(..., description="Query longitude")
    places: list[NearbyPlace] = Field(..., description="Nearby places found")
    count: int = Field(..., description="Number of places found", ge=0)
    message: str = Field(..., description="Operation result message")

    def to_text(self) -> str:
        lines = [self.message, ""]
        for i, p in enumerate(self.places, 1):
            lines.append(f"{i}. {p.to_text()}")
        return "\n".join(lines)


class AdminBoundaryLevel(BaseModel):
    """A single administrative boundary level."""

    model_config = ConfigDict(extra="forbid")

    level: str = Field(..., description="Admin level name (country, state, etc.)")
    name: str = Field(..., description="Name of the administrative area")
    osm_type: str | None = Field(None, description="OSM type")
    osm_id: int | None = Field(None, description="OSM ID")


class AdminBoundaryResponse(BaseModel):
    """Response model for administrative boundary lookup."""

    model_config = ConfigDict(extra="forbid")

    lat: float = Field(..., description="Query latitude")
    lon: float = Field(..., description="Query longitude")
    boundaries: list[AdminBoundaryLevel] = Field(
        ..., description="Administrative boundaries from largest to smallest"
    )
    display_name: str = Field(..., description="Full display name")
    message: str = Field(..., description="Operation result message")

    def to_text(self) -> str:
        lines = [self.message, f"Location: {self.display_name}", ""]
        for b in self.boundaries:
            lines.append(f"  {b.level}: {b.name}")
        return "\n".join(lines)


class StatusResponse(BaseModel):
    """Response model for server status queries."""

    model_config = ConfigDict(extra="forbid")

    server: str = Field(default="chuk-mcp-geocoder", description="Server name")
    version: str = Field(default="0.1.0", description="Server version")
    nominatim_url: str = Field(..., description="Nominatim API base URL")
    cache_entries: int = Field(default=0, description="Number of cached results", ge=0)
    tool_count: int = Field(..., description="Number of available tools", ge=0)
    message: str = Field(..., description="Operation result message")

    def to_text(self) -> str:
        lines = [
            f"{self.server} v{self.version}",
            f"Nominatim: {self.nominatim_url}",
            f"Cache: {self.cache_entries} entries",
            f"Tools: {self.tool_count}",
        ]
        return "\n".join(lines)


class CapabilitiesResponse(BaseModel):
    """Response model for server capabilities listing."""

    model_config = ConfigDict(extra="forbid")

    server: str = Field(..., description="Server name")
    version: str = Field(..., description="Server version")
    geocoding_tools: list[str] = Field(..., description="Available geocoding tools")
    discovery_tools: list[str] = Field(..., description="Available discovery tools")
    batch_tools: list[str] = Field(default_factory=list, description="Available batch tools")
    tool_count: int = Field(..., description="Total number of tools", ge=0)
    nominatim_url: str = Field(..., description="Nominatim API base URL")
    llm_guidance: str = Field(..., description="LLM-friendly usage guidance")
    message: str = Field(..., description="Operation result message")

    def to_text(self) -> str:
        lines = [
            f"{self.server} v{self.version}",
            f"Tools: {self.tool_count}",
            f"Geocoding: {', '.join(self.geocoding_tools)}",
            f"Discovery: {', '.join(self.discovery_tools)}",
            f"Batch: {', '.join(self.batch_tools)}",
            f"Nominatim: {self.nominatim_url}",
            f"Guidance: {self.llm_guidance}",
        ]
        return "\n".join(lines)


# --- Batch & Routing response models ---


class BatchGeocodeItem(BaseModel):
    """Result for a single query in a batch geocode."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., description="Original query string")
    results: list[GeocodeResult] | None = Field(None, description="Geocoding results")
    error: str | None = Field(None, description="Error message if query failed")


class BatchGeocodeResponse(BaseModel):
    """Response for batch geocoding multiple places."""

    model_config = ConfigDict(extra="forbid")

    queries: list[str] = Field(..., description="Original query list")
    results: list[BatchGeocodeItem] = Field(..., description="Per-query results")
    total: int = Field(..., description="Total queries", ge=0)
    succeeded: int = Field(..., description="Queries that succeeded", ge=0)
    failed: int = Field(..., description="Queries that failed", ge=0)
    message: str = Field(..., description="Operation result message")

    def to_text(self) -> str:
        lines = [self.message, ""]
        for item in self.results:
            if item.error:
                lines.append(f"  {item.query}: ERROR - {item.error}")
            elif item.results:
                top = item.results[0]
                lines.append(f"  {item.query}: {top.lat:.6f}, {top.lon:.6f} ({top.display_name})")
            else:
                lines.append(f"  {item.query}: no results")
        return "\n".join(lines)


class RouteWaypoint(BaseModel):
    """A resolved waypoint in a route."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Resolved place name")
    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")
    bbox: list[float] = Field(..., description="Bounding box [west, south, east, north]")


class RouteLeg(BaseModel):
    """A leg between two consecutive waypoints."""

    model_config = ConfigDict(extra="forbid")

    from_name: str = Field(..., description="Start waypoint name")
    to_name: str = Field(..., description="End waypoint name")
    distance_m: float = Field(..., description="Haversine distance in metres")


class RouteResponse(BaseModel):
    """Response for route waypoint resolution."""

    model_config = ConfigDict(extra="forbid")

    waypoints: list[RouteWaypoint] = Field(..., description="Resolved waypoints in order")
    legs: list[RouteLeg] = Field(..., description="Legs between consecutive waypoints")
    total_distance_m: float = Field(..., description="Total route distance in metres")
    bbox: list[float] = Field(..., description="Bounding box encompassing all waypoints")
    waypoint_count: int = Field(..., description="Number of waypoints", ge=0)
    message: str = Field(..., description="Operation result message")

    def to_text(self) -> str:
        lines = [self.message, ""]
        lines.append("Waypoints:")
        for i, wp in enumerate(self.waypoints, 1):
            lines.append(f"  {i}. {wp.name} ({wp.lat:.6f}, {wp.lon:.6f})")
        lines.append("")
        lines.append("Legs:")
        for leg in self.legs:
            lines.append(f"  {leg.from_name} → {leg.to_name}: {leg.distance_m:.0f}m")
        lines.append("")
        lines.append(f"Total: {self.total_distance_m:.0f}m")
        return "\n".join(lines)


class DistanceMatrixPoint(BaseModel):
    """A point in a distance matrix."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Point name or label")
    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")


class DistanceMatrixResponse(BaseModel):
    """Response for distance matrix computation."""

    model_config = ConfigDict(extra="forbid")

    points: list[DistanceMatrixPoint] = Field(..., description="Points in the matrix")
    distances: list[list[float]] = Field(..., description="NxN distance matrix in metres")
    count: int = Field(..., description="Number of points", ge=0)
    message: str = Field(..., description="Operation result message")

    def to_text(self) -> str:
        lines = [self.message, ""]
        names = [p.name for p in self.points]
        # Header
        header = "".ljust(20) + "  ".join(n[:10].ljust(10) for n in names)
        lines.append(header)
        for i, row in enumerate(self.distances):
            cols = "  ".join(f"{d:>10.0f}" for d in row)
            lines.append(f"{names[i][:20].ljust(20)}{cols}")
        return "\n".join(lines)
