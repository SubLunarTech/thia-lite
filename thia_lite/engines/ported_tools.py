"""
Tool Registration for Ported Engines
========================================
Registers all ported thia-libre engines as LLM-callable tools.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def register_ported_tools():
    """Register all tools from ported engine modules."""
    from thia_lite.llm.tool_executor import register_tool

    # ─── Fixed Stars ──────────────────────────────────────────────────────

    def fixed_stars_dispatch(tool_name: str, args: Dict[str, Any]) -> Any:
        try:
            from thia_lite.engines import fixed_stars as fs
        except ImportError as e:
            return {"error": f"Fixed stars module not available: {e}"}

        if tool_name == "list_fixed_stars":
            return fs.list_fixed_stars(
                constellation=args.get("constellation"),
                magnitude_limit=args.get("magnitude_limit"),
                limit=args.get("limit", 20),
            )
        elif tool_name == "get_fixed_star":
            return fs.get_fixed_star(args["star_id"])
        elif tool_name == "find_star_conjunctions":
            return fs.find_star_conjunctions(
                natal_timestamp=args["natal_timestamp"],
                latitude=args["latitude"],
                longitude=args["longitude"],
                orb=args.get("orb"),
            )
        elif tool_name == "calculate_star_parans":
            return fs.calculate_star_parans(
                star_name=args["star_name"],
                latitude=args["latitude"],
                longitude=args["longitude"],
                date=args.get("date"),
            )
        return {"error": f"Unknown fixed star tool: {tool_name}"}

    register_tool("list_fixed_stars",
        "List fixed stars from the catalog. Filter by constellation or magnitude.",
        {"type": "object", "properties": {
            "constellation": {"type": "string", "description": "Filter by constellation name"},
            "magnitude_limit": {"type": "number", "description": "Max magnitude (smaller = brighter)"},
            "limit": {"type": "integer", "description": "Max results (default: 20)"},
        }},
        fixed_stars_dispatch)

    register_tool("get_fixed_star",
        "Get details about a specific fixed star by name or ID.",
        {"type": "object", "properties": {
            "star_id": {"type": "string", "description": "Star name or ID (e.g., 'regulus', 'algol', 'spica')"},
        }, "required": ["star_id"]},
        fixed_stars_dispatch)

    register_tool("find_star_conjunctions",
        "Find fixed stars conjunct natal planets. Takes birth data and returns all star-planet conjunctions.",
        {"type": "object", "properties": {
            "natal_timestamp": {"type": "string", "description": "Birth timestamp (ISO 8601)"},
            "latitude": {"type": "number", "description": "Birth latitude"},
            "longitude": {"type": "number", "description": "Birth longitude"},
            "orb": {"type": "number", "description": "Custom orb in degrees"},
        }, "required": ["natal_timestamp", "latitude", "longitude"]},
        fixed_stars_dispatch)

    register_tool("calculate_star_parans",
        "Calculate paranatellonta (rising/setting/culminating times) for a fixed star at a location.",
        {"type": "object", "properties": {
            "star_name": {"type": "string", "description": "Star name"},
            "latitude": {"type": "number", "description": "Observer latitude"},
            "longitude": {"type": "number", "description": "Observer longitude"},
            "date": {"type": "string", "description": "Date (ISO 8601), defaults to today"},
        }, "required": ["star_name", "latitude", "longitude"]},
        fixed_stars_dispatch)

    # ─── Profections ──────────────────────────────────────────────────────

    def profections_dispatch(tool_name: str, args: Dict[str, Any]) -> Any:
        try:
            from thia_lite.engines import profections as pf
        except ImportError as e:
            return {"error": f"Profections module not available: {e}"}

        if tool_name == "calculate_profections":
            return pf.calculate_profections(
                natal_timestamp=args["natal_timestamp"],
                natal_latitude=args["natal_latitude"],
                natal_longitude=args["natal_longitude"],
                target_timestamp=args.get("target_timestamp"),
                profection_type=args.get("profection_type", "annual"),
            )
        elif tool_name == "calculate_profection_timeline":
            return pf.calculate_profection_timeline(
                natal_timestamp=args["natal_timestamp"],
                natal_latitude=args["natal_latitude"],
                natal_longitude=args["natal_longitude"],
                max_years=args.get("max_years", 84),
            )
        elif tool_name == "calculate_unified_timing":
            return pf.calculate_unified_timing(
                natal_timestamp=args["natal_timestamp"],
                natal_latitude=args["natal_latitude"],
                natal_longitude=args["natal_longitude"],
                target_timestamp=args.get("target_timestamp"),
            )
        return {"error": f"Unknown profection tool: {tool_name}"}

    register_tool("calculate_profections",
        "Calculate annual, monthly, or daily profections for predictive astrology. Shows the activated house, sign, and time lord.",
        {"type": "object", "properties": {
            "natal_timestamp": {"type": "string", "description": "Birth timestamp (ISO 8601)"},
            "natal_latitude": {"type": "number", "description": "Birth latitude"},
            "natal_longitude": {"type": "number", "description": "Birth longitude"},
            "target_timestamp": {"type": "string", "description": "Target date (defaults to now)"},
            "profection_type": {"type": "string", "enum": ["annual", "monthly", "daily"]},
        }, "required": ["natal_timestamp", "natal_latitude", "natal_longitude"]},
        profections_dispatch)

    register_tool("calculate_profection_timeline",
        "Calculate the full profection timeline for an entire life (84 years). Shows which house and time lord is active each year.",
        {"type": "object", "properties": {
            "natal_timestamp": {"type": "string", "description": "Birth timestamp"},
            "natal_latitude": {"type": "number"},
            "natal_longitude": {"type": "number"},
            "max_years": {"type": "integer", "description": "Max years (default: 84)"},
        }, "required": ["natal_timestamp", "natal_latitude", "natal_longitude"]},
        profections_dispatch)

    register_tool("calculate_unified_timing",
        "Calculate unified timing combining profections with Firdar and zodiacal releasing time lords.",
        {"type": "object", "properties": {
            "natal_timestamp": {"type": "string"},
            "natal_latitude": {"type": "number"},
            "natal_longitude": {"type": "number"},
            "target_timestamp": {"type": "string"},
        }, "required": ["natal_timestamp", "natal_latitude", "natal_longitude"]},
        profections_dispatch)

    # ─── Financial Astrology ──────────────────────────────────────────────

    def financial_dispatch(tool_name: str, args: Dict[str, Any]) -> Any:
        try:
            from thia_lite.engines import financial_astrology as fa
        except ImportError as e:
            return {"error": f"Financial astrology module not available: {e}"}

        if tool_name == "calculate_square_of_9":
            return fa.calculate_square_of_9(price=args["price"])
        elif tool_name == "calculate_gann_angles":
            return fa.calculate_gann_angles(
                start_price=args["start_price"],
                start_date_str=args["start_date"],
                target_date_str=args["target_date"],
                price_unit_per_day=args.get("price_unit", 1.0),
            )
        elif tool_name == "analyze_gann":
            return fa.analyze_gann(
                price=args["price"],
                planet_lons=args.get("planet_longitudes"),
                pivot_price=args.get("pivot_price"),
                pivot_date=args.get("pivot_date"),
                target_date=args.get("target_date"),
            )
        return {"error": f"Unknown financial tool: {tool_name}"}

    register_tool("calculate_square_of_9",
        "Calculate W.D. Gann's Square of 9 support and resistance levels around a price.",
        {"type": "object", "properties": {
            "price": {"type": "number", "description": "Current price or target price"},
        }, "required": ["price"]},
        financial_dispatch)

    register_tool("calculate_gann_angles",
        "Calculate Gann Angles (1x1, 1x2, 2x1, etc.) from a pivot price/date to a target date.",
        {"type": "object", "properties": {
            "start_price": {"type": "number", "description": "Pivot price"},
            "start_date": {"type": "string", "description": "Pivot date (YYYY-MM-DD)"},
            "target_date": {"type": "string", "description": "Target date (YYYY-MM-DD)"},
            "price_unit": {"type": "number", "description": "Price units per day"},
        }, "required": ["start_price", "start_date", "target_date"]},
        financial_dispatch)

    register_tool("analyze_gann",
        "Full Gann analysis: Square of 9, planetary price lines, and Gann angles combined.",
        {"type": "object", "properties": {
            "price": {"type": "number", "description": "Current price"},
            "planet_longitudes": {"type": "object", "description": "Planet name → longitude mapping"},
            "pivot_price": {"type": "number"}, "pivot_date": {"type": "string"}, "target_date": {"type": "string"},
        }, "required": ["price"]},
        financial_dispatch)

    # ─── Vedic / Sidereal ─────────────────────────────────────────────────

    def vedic_dispatch(tool_name: str, args: Dict[str, Any]) -> Any:
        try:
            from thia_lite.engines import vedic_astrology as va
        except ImportError as e:
            return {"error": f"Vedic astrology module not available: {e}"}

        if tool_name == "calculate_sidereal_positions":
            return va.calculate_sidereal_positions(
                timestamp=args["timestamp"],
                ayanamsa=args.get("ayanamsa", "lahiri"),
            )
        elif tool_name == "get_nakshatra":
            return va.get_nakshatra(
                longitude=args["longitude"],
                ayanamsa=args.get("ayanamsa", "lahiri"),
            )
        return {"error": f"Unknown vedic tool: {tool_name}"}

    register_tool("calculate_sidereal_positions",
        "Calculate sidereal planetary positions using the Lahiri or other ayanamsa.",
        {"type": "object", "properties": {
            "timestamp": {"type": "string", "description": "Timestamp (ISO 8601)"},
            "ayanamsa": {"type": "string", "description": "Ayanamsa system (lahiri, raman, fagan_bradley)"},
        }, "required": ["timestamp"]},
        vedic_dispatch)

    register_tool("get_nakshatra",
        "Get the Nakshatra (lunar mansion) for a given sidereal longitude.",
        {"type": "object", "properties": {
            "longitude": {"type": "number", "description": "Sidereal longitude in degrees"},
            "ayanamsa": {"type": "string"},
        }, "required": ["longitude"]},
        vedic_dispatch)

    # ─── Geocoding / Timezone ─────────────────────────────────────────────

    def geo_dispatch(tool_name: str, args: Dict[str, Any]) -> Any:
        try:
            from thia_lite.engines import timezone_manager as tz
        except ImportError as e:
            return {"error": f"Timezone module not available: {e}"}

        if tool_name == "resolve_timezone":
            return tz.resolve_timezone(
                latitude=args["latitude"],
                longitude=args["longitude"],
                timestamp=args.get("timestamp"),
            )
        return {"error": f"Unknown geo tool: {tool_name}"}

    register_tool("resolve_timezone",
        "Resolve the timezone for given coordinates. Returns timezone name and UTC offset.",
        {"type": "object", "properties": {
            "latitude": {"type": "number"},
            "longitude": {"type": "number"},
            "timestamp": {"type": "string", "description": "For historical timezone data"},
        }, "required": ["latitude", "longitude"]},
        geo_dispatch)

    logger.info("Registered ported engine tools: fixed_stars, profections, financial, vedic, timezone")
