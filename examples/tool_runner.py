"""
Lightweight MCP tool runner for chuk-mcp-geocoder.

Runs tools directly without MCP transport — useful for testing and demos.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from chuk_mcp_geocoder.core.geocoder import Geocoder
from chuk_mcp_geocoder.tools.batch import register_batch_tools
from chuk_mcp_geocoder.tools.discovery import register_discovery_tools
from chuk_mcp_geocoder.tools.geocoding import register_geocoding_tools


class _MiniMCP:
    """Minimal MCP-like interface for capturing tool registrations."""

    def __init__(self):
        self._tools: dict[str, Any] = {}

    def tool(self):
        def decorator(fn):
            self._tools[fn.__name__] = fn
            return fn

        return decorator

    def get_tool(self, name: str):
        return self._tools[name]


class ToolRunner:
    """Run geocoder MCP tools directly without transport."""

    def __init__(self):
        self._mcp = _MiniMCP()
        self.geocoder = Geocoder()
        register_geocoding_tools(self._mcp, self.geocoder)
        register_discovery_tools(self._mcp, self.geocoder)
        register_batch_tools(self._mcp, self.geocoder)

    @property
    def tool_names(self) -> list[str]:
        return list(self._mcp._tools.keys())

    async def run(self, tool_name: str, **kwargs) -> dict:
        """Run a tool and return parsed JSON result."""
        fn = self._mcp.get_tool(tool_name)
        raw = await fn(**kwargs)
        return json.loads(raw)

    async def run_text(self, tool_name: str, **kwargs) -> str:
        """Run a tool and return text output."""
        fn = self._mcp.get_tool(tool_name)
        return await fn(output_mode="text", **kwargs)


async def main():
    """Demo: exercise all 10 geocoder tools."""
    runner = ToolRunner()

    print(f"Available tools ({len(runner.tool_names)}): {runner.tool_names}\n")

    # ──────────────────────────────────────────────
    # Geocoding tools
    # ──────────────────────────────────────────────

    print("=" * 60)
    print("1. geocode — Forward geocode")
    print("=" * 60)
    result = await runner.run("geocode", query="Boulder, Colorado", limit=2)
    for r in result["results"]:
        print(f"  {r['display_name']}")
        print(f"    lat={r['lat']}, lon={r['lon']}")
        print(f"    bbox={r['bbox']}")
    print()

    print("=" * 60)
    print("2. reverse_geocode — Coordinates to place")
    print("=" * 60)
    result = await runner.run("reverse_geocode", lat=48.8566, lon=2.3522)
    print(f"  {result['display_name']}")
    print(f"  address: {result['address']}")
    print()

    print("=" * 60)
    print("3. bbox_from_place — Bounding box for DEM/STAC")
    print("=" * 60)
    result = await runner.run("bbox_from_place", query="Palm Jumeirah, Dubai", padding=0.1)
    print(f"  place: {result['place_name']}")
    print(f"  bbox: {result['bbox']}")
    print(f"  center: {result['center']}")
    print(f"  area: {result.get('area_km2')} km^2")
    print()

    # ──────────────────────────────────────────────
    # Discovery tools
    # ──────────────────────────────────────────────

    print("=" * 60)
    print("4. nearby_places — Find places near a point")
    print("=" * 60)
    result = await runner.run("nearby_places", lat=51.5074, lon=-0.1278, limit=5)
    for p in result["places"]:
        dist = f" ({p['distance_m']}m)" if p.get("distance_m") else ""
        print(f"  {p['display_name']}{dist}")
    print()

    print("=" * 60)
    print("5. admin_boundaries — Administrative hierarchy")
    print("=" * 60)
    result = await runner.run("admin_boundaries", lat=40.0150, lon=-105.2705)
    print(f"  Location: {result['display_name']}")
    for b in result["boundaries"]:
        print(f"    {b['level']}: {b['name']}")
    print()

    print("=" * 60)
    print("6. geocoder_status — Server status")
    print("=" * 60)
    result = await runner.run("geocoder_status")
    print(f"  server: {result['server']} v{result['version']}")
    print(f"  tools: {result['tool_count']}")
    print(f"  cache: {result['cache_entries']} entries")
    print()

    print("=" * 60)
    print("7. geocoder_capabilities — Full capabilities")
    print("=" * 60)
    result = await runner.run("geocoder_capabilities")
    print(f"  geocoding: {result['geocoding_tools']}")
    print(f"  discovery: {result['discovery_tools']}")
    print(f"  batch: {result['batch_tools']}")
    print(f"  guidance: {result['llm_guidance'][:80]}...")
    print()

    # ──────────────────────────────────────────────
    # Batch & Routing tools
    # ──────────────────────────────────────────────

    print("=" * 60)
    print("8. batch_geocode — Multiple places at once")
    print("=" * 60)
    queries = json.dumps(["Boulder, Colorado", "Denver, Colorado", "Aspen, Colorado"])
    result = await runner.run("batch_geocode", queries=queries, limit=1)
    print(
        f"  total: {result['total']}, succeeded: {result['succeeded']}, failed: {result['failed']}"
    )
    for item in result["results"]:
        if item.get("results"):
            r = item["results"][0]
            print(f"  {item['query']}: {r['lat']:.4f}, {r['lon']:.4f}")
        elif item.get("error"):
            print(f"  {item['query']}: ERROR - {item['error']}")
    print()

    print("=" * 60)
    print("9. route_waypoints — Ordered route with distances")
    print("=" * 60)
    waypoints = json.dumps(["Boulder, Colorado", "Denver, Colorado", "Colorado Springs, Colorado"])
    result = await runner.run("route_waypoints", waypoints=waypoints)
    print(f"  waypoints: {result['waypoint_count']}")
    for wp in result["waypoints"]:
        print(f"    {wp['name'][:50]}: {wp['lat']:.4f}, {wp['lon']:.4f}")
    print("  legs:")
    for leg in result["legs"]:
        print(
            f"    {leg['from_name'][:30]} -> {leg['to_name'][:30]}: {leg['distance_m'] / 1000:.1f} km"
        )
    print(f"  total distance: {result['total_distance_m'] / 1000:.1f} km")
    print(f"  bbox: {result['bbox']}")
    print()

    print("=" * 60)
    print("10. distance_matrix — Pairwise distances")
    print("=" * 60)
    points = json.dumps(
        [
            {"name": "Boulder", "lat": 40.0150, "lon": -105.2705},
            {"name": "Denver", "lat": 39.7392, "lon": -104.9903},
            {"name": "Colorado Springs", "lat": 38.8339, "lon": -104.8214},
        ]
    )
    result = await runner.run("distance_matrix", points=points)
    names = [p["name"] for p in result["points"]]
    print(f"  points: {names}")
    print("  distances (km):")
    for i, row in enumerate(result["distances"]):
        dists = ", ".join(f"{d / 1000:.1f}" for d in row)
        print(f"    {names[i]}: [{dists}]")
    print()

    print("=" * 60)
    print("Done — all 10 tools exercised successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
