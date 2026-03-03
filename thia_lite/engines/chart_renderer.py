"""
Thia-Lite Chart Renderer
===========================
Generates SVG natal/transit chart wheels for display in CLI, TUI, and Desktop.

Features:
- SVG natal chart wheel with planets, signs, houses, aspects
- Live sky chart (current transits)
- Synastry overlay charts
- Chart export as SVG/PNG

Designed for embedding in Tauri desktop and rich terminal output.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

SIGN_SYMBOLS = {
    "Aries": "♈", "Taurus": "♉", "Gemini": "♊", "Cancer": "♋",
    "Leo": "♌", "Virgo": "♍", "Libra": "♎", "Scorpio": "♏",
    "Sagittarius": "♐", "Capricorn": "♑", "Aquarius": "♒", "Pisces": "♓",
}

PLANET_SYMBOLS = {
    "Sun": "☉", "Moon": "☽", "Mercury": "☿", "Venus": "♀",
    "Mars": "♂", "Jupiter": "♃", "Saturn": "♄", "Uranus": "♅",
    "Neptune": "♆", "Pluto": "♇", "North Node": "☊", "South Node": "☋",
    "Chiron": "⚷",
}

SIGN_COLORS = {
    "Aries": "#FF4444", "Taurus": "#44BB44", "Gemini": "#FFBB33",
    "Cancer": "#4488CC", "Leo": "#FF8833", "Virgo": "#88AA44",
    "Libra": "#CC44AA", "Scorpio": "#AA3333", "Sagittarius": "#BB44FF",
    "Capricorn": "#556677", "Aquarius": "#33BBFF", "Pisces": "#7744BB",
}

ASPECT_STYLES = {
    "conjunction": {"color": "#FFD700", "dash": "", "label": "☌"},
    "sextile":     {"color": "#33CCFF", "dash": "5,5", "label": "⚹"},
    "square":      {"color": "#FF4444", "dash": "8,4", "label": "□"},
    "trine":       {"color": "#33FF33", "dash": "", "label": "△"},
    "opposition":  {"color": "#FF3333", "dash": "12,4", "label": "☍"},
    "quincunx":    {"color": "#AAAAAA", "dash": "3,3", "label": "⚻"},
}


# ─── SVG Chart Generator ─────────────────────────────────────────────────────

def generate_chart_svg(
    planets: Dict[str, Dict],
    houses: Optional[List[float]] = None,
    aspects: Optional[List[Dict]] = None,
    title: str = "Natal Chart",
    size: int = 600,
    asc_degree: float = 0.0,
    style: str = "dark",
) -> str:
    """
    Generate an SVG natal chart wheel.
    
    Args:
        planets: Dict of planet_name -> {"longitude": float, "sign": str, ...}
        houses: List of 12 house cusp longitudes (optional)
        aspects: List of aspect dicts (optional)
        title: Chart title
        size: SVG size in pixels
        asc_degree: Ascendant degree (rotates chart)
        style: "dark" or "light"
    """
    cx, cy = size / 2, size / 2
    outer_r = size * 0.42
    inner_r = size * 0.32
    planet_r = size * 0.26
    aspect_r = size * 0.20
    
    bg = "#1a1a2e" if style == "dark" else "#fafafa"
    fg = "#e0e0e0" if style == "dark" else "#333333"
    ring_stroke = "#333355" if style == "dark" else "#cccccc"
    
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">',
        f'<rect width="{size}" height="{size}" fill="{bg}" rx="12"/>',
        # Title
        f'<text x="{cx}" y="24" text-anchor="middle" fill="{fg}" font-family="Inter, sans-serif" font-size="14" font-weight="600">{title}</text>',
    ]
    
    # Outer ring (zodiac wheel)
    svg_parts.append(f'<circle cx="{cx}" cy="{cy}" r="{outer_r}" fill="none" stroke="{ring_stroke}" stroke-width="1.5"/>')
    svg_parts.append(f'<circle cx="{cx}" cy="{cy}" r="{inner_r}" fill="none" stroke="{ring_stroke}" stroke-width="1"/>')
    
    # Draw zodiac sign segments
    for i in range(12):
        angle_start = (i * 30 - asc_degree - 90) * math.pi / 180
        angle_mid = ((i * 30 + 15) - asc_degree - 90) * math.pi / 180
        angle_end = ((i + 1) * 30 - asc_degree - 90) * math.pi / 180
        
        # Divider line
        x1 = cx + inner_r * math.cos(angle_start)
        y1 = cy + inner_r * math.sin(angle_start)
        x2 = cx + outer_r * math.cos(angle_start)
        y2 = cy + outer_r * math.sin(angle_start)
        svg_parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{ring_stroke}" stroke-width="0.5"/>')
        
        # Sign symbol
        sign_names = list(SIGN_SYMBOLS.keys())
        sign = sign_names[i]
        symbol = SIGN_SYMBOLS[sign]
        color = SIGN_COLORS[sign]
        mid_r = (outer_r + inner_r) / 2
        sx = cx + mid_r * math.cos(angle_mid) - 6
        sy = cy + mid_r * math.sin(angle_mid) + 6
        svg_parts.append(f'<text x="{sx:.1f}" y="{sy:.1f}" fill="{color}" font-size="16" font-family="serif">{symbol}</text>')
    
    # Draw house cusps (if provided)
    if houses and len(houses) >= 12:
        for i, cusp in enumerate(houses):
            angle = (cusp - asc_degree - 90) * math.pi / 180
            x1 = cx + aspect_r * 0.5 * math.cos(angle)
            y1 = cy + aspect_r * 0.5 * math.sin(angle)
            x2 = cx + inner_r * math.cos(angle)
            y2 = cy + inner_r * math.sin(angle)
            dash = "" if i in (0, 3, 6, 9) else "4,4"
            width = "1.5" if i in (0, 3, 6, 9) else "0.5"
            svg_parts.append(
                f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="#5566AA" stroke-width="{width}" stroke-dasharray="{dash}"/>'
            )
            # House number
            label_r = aspect_r * 0.7
            mid_cusp = (cusp + (houses[(i + 1) % 12] if i < 11 else houses[0] + 360)) / 2
            la = (mid_cusp - asc_degree - 90) * math.pi / 180
            lx = cx + label_r * math.cos(la)
            ly = cy + label_r * math.sin(la) + 4
            svg_parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" fill="#5566AA" font-size="10" font-family="sans-serif">{i+1}</text>')
    
    # Draw aspects
    if aspects:
        for asp in aspects:
            p1_lon = asp.get("planet1_lon", 0)
            p2_lon = asp.get("planet2_lon", 0)
            asp_type = asp.get("aspect", "conjunction")
            style_info = ASPECT_STYLES.get(asp_type, ASPECT_STYLES["conjunction"])
            
            a1 = (p1_lon - asc_degree - 90) * math.pi / 180
            a2 = (p2_lon - asc_degree - 90) * math.pi / 180
            x1 = cx + aspect_r * math.cos(a1)
            y1 = cy + aspect_r * math.sin(a1)
            x2 = cx + aspect_r * math.cos(a2)
            y2 = cy + aspect_r * math.sin(a2)
            
            dash_attr = f' stroke-dasharray="{style_info["dash"]}"' if style_info["dash"] else ""
            svg_parts.append(
                f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="{style_info["color"]}" stroke-width="0.8" opacity="0.6"{dash_attr}/>'
            )
    
    # Draw planets
    placed_angles = []
    for name, data in planets.items():
        lon = data.get("longitude", 0)
        symbol = PLANET_SYMBOLS.get(name, name[0])
        
        angle = (lon - asc_degree - 90) * math.pi / 180
        
        # Anti-collision: nudge if too close to another planet
        for pa in placed_angles:
            if abs(angle - pa) < 0.15:
                angle += 0.15
        placed_angles.append(angle)
        
        px = cx + planet_r * math.cos(angle)
        py = cy + planet_r * math.sin(angle)
        
        # Planet dot
        sign = data.get("sign", "Aries")
        color = SIGN_COLORS.get(sign, "#FFFFFF")
        svg_parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="10" fill="{bg}" stroke="{color}" stroke-width="1.5"/>')
        svg_parts.append(f'<text x="{px:.1f}" y="{py + 5:.1f}" text-anchor="middle" fill="{color}" font-size="13" font-family="serif">{symbol}</text>')
        
        # Retrograde indicator
        if data.get("retrograde"):
            svg_parts.append(f'<text x="{px + 10:.1f}" y="{py - 5:.1f}" fill="#FF6666" font-size="8" font-family="sans-serif">℞</text>')
        
        # Degree line to wheel
        wx = cx + inner_r * math.cos(angle)
        wy = cy + inner_r * math.sin(angle)
        svg_parts.append(f'<line x1="{px:.1f}" y1="{py:.1f}" x2="{wx:.1f}" y2="{wy:.1f}" stroke="{color}" stroke-width="0.3" opacity="0.4"/>')
    
    # Center dot
    svg_parts.append(f'<circle cx="{cx}" cy="{cy}" r="3" fill="{fg}"/>')
    
    # Timestamp
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    svg_parts.append(f'<text x="{cx}" y="{size - 10}" text-anchor="middle" fill="{fg}" font-size="10" font-family="sans-serif" opacity="0.6">{now}</text>')
    
    svg_parts.append('</svg>')
    return "\n".join(svg_parts)


def generate_live_sky_svg(size: int = 600) -> str:
    """Generate a chart of the current sky (live transits)."""
    try:
        from thia_lite.llm.tool_executor import _tool_handlers
        if "get_current_transits" not in _tool_handlers:
            return _error_svg("Astrology tools not loaded", size)
        
        result = _tool_handlers["get_current_transits"]("get_current_transits", {})
        if not isinstance(result, dict):
            return _error_svg("Could not get transits", size)
        
        planets = {}
        raw_planets = result.get("planets", {})
        sign_map = [
            "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
            "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
        ]
        
        for name, data in raw_planets.items():
            if isinstance(data, dict):
                lon = data.get("longitude", 0)
                planets[name] = {
                    "longitude": lon,
                    "sign": sign_map[int(lon / 30) % 12],
                    "retrograde": data.get("retrograde", False),
                }
        
        aspects = result.get("aspects", [])
        
        return generate_chart_svg(
            planets=planets,
            aspects=aspects,
            title="Live Sky — Current Transits",
            size=size,
        )
    except Exception as e:
        return _error_svg(f"Error: {e}", size)


def _error_svg(message: str, size: int = 600) -> str:
    """Generate an error SVG."""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">
        <rect width="{size}" height="{size}" fill="#1a1a2e" rx="12"/>
        <text x="{size//2}" y="{size//2}" text-anchor="middle" fill="#FF6666" font-size="14">{message}</text>
    </svg>'''


def generate_synastry_svg(
    person1_planets: Dict[str, Dict],
    person2_planets: Dict[str, Dict],
    inter_aspects: Optional[List[Dict]] = None,
    title: str = "Synastry Chart",
    size: int = 700,
    name1: str = "Person 1",
    name2: str = "Person 2",
    style: str = "dark",
) -> str:
    """
    Generate a synastry bi-wheel SVG. Outer ring = person 1, inner ring = person 2.
    Inter-aspects drawn in the center.
    """
    cx, cy = size / 2, size / 2
    outer_r = size * 0.42
    zodiac_inner_r = size * 0.36
    p1_r = size * 0.30  # Person 1 planets
    p2_r = size * 0.20  # Person 2 planets
    aspect_r = size * 0.14

    bg = "#1a1a2e" if style == "dark" else "#fafafa"
    fg = "#e0e0e0" if style == "dark" else "#333333"
    ring_stroke = "#333355" if style == "dark" else "#cccccc"

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">',
        f'<rect width="{size}" height="{size}" fill="{bg}" rx="12"/>',
        f'<text x="{cx}" y="24" text-anchor="middle" fill="{fg}" font-size="14" font-weight="600">{title}</text>',
        # Rings
        f'<circle cx="{cx}" cy="{cy}" r="{outer_r}" fill="none" stroke="{ring_stroke}" stroke-width="1.5"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{zodiac_inner_r}" fill="none" stroke="{ring_stroke}" stroke-width="1"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{p1_r}" fill="none" stroke="#554488" stroke-width="0.5" stroke-dasharray="4,4"/>',
    ]

    # Zodiac signs on outer ring
    sign_names = list(SIGN_SYMBOLS.keys())
    for i in range(12):
        angle_start = (i * 30 - 90) * math.pi / 180
        angle_mid = (i * 30 + 15 - 90) * math.pi / 180
        x1, y1 = cx + zodiac_inner_r * math.cos(angle_start), cy + zodiac_inner_r * math.sin(angle_start)
        x2, y2 = cx + outer_r * math.cos(angle_start), cy + outer_r * math.sin(angle_start)
        svg.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{ring_stroke}" stroke-width="0.5"/>')
        mid_r = (outer_r + zodiac_inner_r) / 2
        sx = cx + mid_r * math.cos(angle_mid) - 6
        sy = cy + mid_r * math.sin(angle_mid) + 6
        svg.append(f'<text x="{sx:.1f}" y="{sy:.1f}" fill="{SIGN_COLORS[sign_names[i]]}" font-size="14">{SIGN_SYMBOLS[sign_names[i]]}</text>')

    # Person 1 planets (outer)
    for name, data in person1_planets.items():
        lon = data.get("longitude", 0)
        symbol = PLANET_SYMBOLS.get(name, name[0])
        a = (lon - 90) * math.pi / 180
        px, py = cx + p1_r * math.cos(a), cy + p1_r * math.sin(a)
        color = SIGN_COLORS.get(data.get("sign", "Aries"), "#88BBFF")
        svg.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="9" fill="{bg}" stroke="{color}" stroke-width="1.5"/>')
        svg.append(f'<text x="{px:.1f}" y="{py+4:.1f}" text-anchor="middle" fill="{color}" font-size="12">{symbol}</text>')

    # Person 2 planets (inner, different color scheme)
    for name, data in person2_planets.items():
        lon = data.get("longitude", 0)
        symbol = PLANET_SYMBOLS.get(name, name[0])
        a = (lon - 90) * math.pi / 180
        px, py = cx + p2_r * math.cos(a), cy + p2_r * math.sin(a)
        svg.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="8" fill="{bg}" stroke="#FFAA44" stroke-width="1.5"/>')
        svg.append(f'<text x="{px:.1f}" y="{py+4:.1f}" text-anchor="middle" fill="#FFAA44" font-size="11">{symbol}</text>')

    # Inter-aspects
    if inter_aspects:
        for asp in inter_aspects:
            a1 = (asp.get("planet1_lon", 0) - 90) * math.pi / 180
            a2 = (asp.get("planet2_lon", 0) - 90) * math.pi / 180
            x1, y1 = cx + aspect_r * math.cos(a1), cy + aspect_r * math.sin(a1)
            x2, y2 = cx + aspect_r * math.cos(a2), cy + aspect_r * math.sin(a2)
            si = ASPECT_STYLES.get(asp.get("aspect", "conjunction"), ASPECT_STYLES["conjunction"])
            dash = f' stroke-dasharray="{si["dash"]}"' if si["dash"] else ""
            svg.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{si["color"]}" stroke-width="0.8" opacity="0.5"{dash}/>')

    # Legend
    svg.append(f'<text x="12" y="{size-24}" fill="#88BBFF" font-size="10">{name1} (outer)</text>')
    svg.append(f'<text x="12" y="{size-10}" fill="#FFAA44" font-size="10">{name2} (inner)</text>')
    svg.append('</svg>')
    return "\n".join(svg)


# ─── Tool Registration ───────────────────────────────────────────────────────

def register_chart_tools():
    """Register chart rendering tools."""
    from thia_lite.llm.tool_executor import register_tool

    def chart_dispatch(tool_name: str, args: Dict[str, Any]) -> Any:
        if tool_name == "render_live_sky":
            svg = generate_live_sky_svg(size=args.get("size", 600))
            return {"svg": svg, "type": "live_sky"}

        elif tool_name == "render_synastry_chart":
            # Expects pre-calculated planet dicts
            svg = generate_synastry_svg(
                person1_planets=args.get("person1_planets", {}),
                person2_planets=args.get("person2_planets", {}),
                inter_aspects=args.get("inter_aspects"),
                title=args.get("title", "Synastry"),
                name1=args.get("name1", "Person 1"),
                name2=args.get("name2", "Person 2"),
            )
            return {"svg": svg, "type": "synastry"}

        elif tool_name == "render_natal_chart":
            # Use astrology tools to calculate, then render
            from thia_lite.llm.tool_executor import _tool_handlers
            if "calculate_natal_chart" not in _tool_handlers:
                return {"error": "Natal chart tool not available"}
            
            chart_data = _tool_handlers["calculate_natal_chart"](
                "calculate_natal_chart", {
                    "date": args["date"],
                    "time": args.get("time", "12:00"),
                    "latitude": args["latitude"],
                    "longitude": args["longitude"],
                }
            )
            
            if isinstance(chart_data, dict) and "error" not in chart_data:
                planets = {}
                for name, data in chart_data.get("planets", {}).items():
                    if isinstance(data, dict):
                        planets[name] = data
                
                svg = generate_chart_svg(
                    planets=planets,
                    houses=chart_data.get("houses", []),
                    aspects=chart_data.get("aspects", []),
                    title=args.get("title", "Natal Chart"),
                    size=args.get("size", 600),
                    asc_degree=chart_data.get("asc_degree", 0),
                )
                return {"svg": svg, "type": "natal", "data": chart_data}
            return chart_data
        
        return {"error": f"Unknown chart tool: {tool_name}"}
    
    register_tool("render_live_sky",
        "Render an SVG chart of the current sky showing all planetary positions and aspects. Returns SVG that can be displayed in the UI.",
        {"type": "object", "properties": {
            "size": {"type": "integer", "description": "Chart size in pixels (default: 600)"},
        }},
        chart_dispatch)
    
    register_tool("render_natal_chart",
        "Calculate and render an SVG natal chart wheel for a given birth date, time, and location.",
        {"type": "object", "properties": {
            "date": {"type": "string", "description": "Birth date (YYYY-MM-DD)"},
            "time": {"type": "string", "description": "Birth time (HH:MM)"},
            "latitude": {"type": "number"},
            "longitude": {"type": "number"},
            "title": {"type": "string", "description": "Chart title"},
            "size": {"type": "integer"},
        }, "required": ["date", "latitude", "longitude"]},
        chart_dispatch)

    register_tool("render_synastry_chart",
        "Render a bi-wheel synastry chart comparing two people's planetary positions with inter-aspects.",
        {"type": "object", "properties": {
            "person1_planets": {"type": "object", "description": "Person 1 planet data (name → {longitude, sign})"},
            "person2_planets": {"type": "object", "description": "Person 2 planet data"},
            "inter_aspects": {"type": "array", "description": "List of inter-aspects"},
            "title": {"type": "string"}, "name1": {"type": "string"}, "name2": {"type": "string"},
        }, "required": ["person1_planets", "person2_planets"]},
        chart_dispatch)

    logger.info("Registered chart rendering tools (natal, live sky, synastry)")
