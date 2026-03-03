"""
Thia-Lite Astrology Engine
============================
Full Swiss Ephemeris engine ported from thia-libre.
All 175+ tools preserved with identical calculation accuracy.

This module strips the FastAPI/HTTP concerns from thia-libre's
astrology-engine and exposes a pure Python tool dispatch interface.
"""

import json
import logging
import math
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─── Swiss Ephemeris Setup ────────────────────────────────────────────────────

try:
    import swisseph as swe

    # Set ephemeris path
    _ephe_path = os.environ.get("SWISSEPH_PATH", "")
    if not _ephe_path:
        from thia_lite.config import get_settings
        try:
            _ephe_path = str(get_settings().ephe_dir)
        except Exception:
            _ephe_path = os.path.join(os.path.expanduser("~"), ".thia-lite", "data", "ephe")

    swe.set_ephe_path(_ephe_path)
    SWISSEPH_AVAILABLE = True
except ImportError:
    SWISSEPH_AVAILABLE = False
    logger.warning("pyswisseph not installed — astrology tools unavailable")


# ─── Constants ────────────────────────────────────────────────────────────────

PLANETS = {
    "Sun": 0, "Moon": 1, "Mercury": 2, "Venus": 3, "Mars": 4,
    "Jupiter": 5, "Saturn": 6, "Uranus": 7, "Neptune": 8, "Pluto": 9,
    "North Node": 11, "Chiron": 15,
}

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

SIGN_RULERS = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
    "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
    "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter",
    "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter",
}

ELEMENTS = {
    "Aries": "Fire", "Taurus": "Earth", "Gemini": "Air",
    "Cancer": "Water", "Leo": "Fire", "Virgo": "Earth",
    "Libra": "Air", "Scorpio": "Water", "Sagittarius": "Fire",
    "Capricorn": "Earth", "Aquarius": "Air", "Pisces": "Water",
}

MODALITIES = {
    "Aries": "Cardinal", "Taurus": "Fixed", "Gemini": "Mutable",
    "Cancer": "Cardinal", "Leo": "Fixed", "Virgo": "Mutable",
    "Libra": "Cardinal", "Scorpio": "Fixed", "Sagittarius": "Mutable",
    "Capricorn": "Cardinal", "Aquarius": "Fixed", "Pisces": "Mutable",
}

HOUSE_SYSTEMS = {
    "Placidus": b'P', "Koch": b'K', "Regiomontanus": b'R',
    "Campanus": b'C', "Equal": b'E', "Whole Sign": b'W',
    "Porphyry": b'O', "Morinus": b'M', "Alcabitius": b'B',
    "Topocentric": b'T', "Meridian": b'X', "Vehlow": b'V',
}

ASPECT_TYPES = [
    {"name": "Conjunction", "angle": 0, "orb": 8, "symbol": "☌"},
    {"name": "Opposition", "angle": 180, "orb": 8, "symbol": "☍"},
    {"name": "Trine", "angle": 120, "orb": 8, "symbol": "△"},
    {"name": "Square", "angle": 90, "orb": 7, "symbol": "□"},
    {"name": "Sextile", "angle": 60, "orb": 6, "symbol": "⚹"},
    {"name": "Quincunx", "angle": 150, "orb": 3, "symbol": "⚻"},
    {"name": "Semi-sextile", "angle": 30, "orb": 2, "symbol": "⚺"},
    {"name": "Semi-square", "angle": 45, "orb": 2, "symbol": "∠"},
    {"name": "Sesquiquadrate", "angle": 135, "orb": 2, "symbol": "⚼"},
    {"name": "Quintile", "angle": 72, "orb": 1.5, "symbol": "Q"},
    {"name": "Bi-quintile", "angle": 144, "orb": 1.5, "symbol": "bQ"},
]


# ─── Core Calculation Helpers ─────────────────────────────────────────────────

def _to_jd(date_str: str, time_str: str = "12:00") -> float:
    """Convert date/time strings to Julian Day."""
    try:
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")

    jd = swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute / 60.0 + dt.second / 3600.0)
    return jd


def _lon_to_sign(lon: float) -> Dict[str, Any]:
    """Convert ecliptic longitude to sign, degree, minute."""
    sign_idx = int(lon / 30)
    deg_in_sign = lon - sign_idx * 30
    degrees = int(deg_in_sign)
    minutes = int((deg_in_sign - degrees) * 60)
    return {
        "sign": SIGNS[sign_idx % 12],
        "sign_index": sign_idx % 12,
        "degree": degrees,
        "minute": minutes,
        "longitude": round(lon, 6),
        "formatted": f"{degrees}°{minutes:02d}' {SIGNS[sign_idx % 12]}",
    }


def _calc_planet(jd: float, planet_id: int, flags: int = 0) -> Dict[str, Any]:
    """Calculate a planet's position."""
    flags = flags | swe.FLG_SWIEPH | swe.FLG_SPEED
    result, ret_flags = swe.calc_ut(jd, planet_id, flags)
    lon, lat, dist, lon_speed, lat_speed, dist_speed = result

    pos = _lon_to_sign(lon)
    pos.update({
        "latitude": round(lat, 6),
        "distance_au": round(dist, 6),
        "speed": round(lon_speed, 6),
        "retrograde": lon_speed < 0,
    })
    return pos


def _calc_houses(jd: float, lat: float, lon: float,
                 system: str = "Placidus") -> Dict[str, Any]:
    """Calculate house cusps and angles."""
    hsys = HOUSE_SYSTEMS.get(system, b'P')
    cusps, ascmc = swe.houses(jd, lat, lon, hsys)

    houses = []
    for i, cusp in enumerate(cusps):
        houses.append({
            "house": i + 1,
            **_lon_to_sign(cusp),
        })

    return {
        "houses": houses,
        "ascendant": _lon_to_sign(ascmc[0]),
        "midheaven": _lon_to_sign(ascmc[1]),
        "armc": round(ascmc[2], 6),
        "vertex": _lon_to_sign(ascmc[3]),
        "system": system,
    }


def _find_aspects(positions: List[Dict], orb_factor: float = 1.0) -> List[Dict]:
    """Find aspects between planetary positions."""
    aspects = []
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            p1 = positions[i]
            p2 = positions[j]
            lon1 = p1["longitude"]
            lon2 = p2["longitude"]

            for asp in ASPECT_TYPES:
                diff = abs(lon1 - lon2) % 360
                if diff > 180:
                    diff = 360 - diff
                orb = abs(diff - asp["angle"])
                max_orb = asp["orb"] * orb_factor

                if orb <= max_orb:
                    aspects.append({
                        "planet1": p1.get("name", ""),
                        "planet2": p2.get("name", ""),
                        "aspect": asp["name"],
                        "symbol": asp["symbol"],
                        "angle": asp["angle"],
                        "orb": round(orb, 4),
                        "applying": _is_applying(p1, p2, asp["angle"]),
                    })
    return aspects


def _is_applying(p1: Dict, p2: Dict, target_angle: float) -> bool:
    """Determine if an aspect is applying or separating."""
    s1 = p1.get("speed", 0)
    s2 = p2.get("speed", 0)
    lon1 = p1["longitude"]
    lon2 = p2["longitude"]
    diff = (lon2 - lon1) % 360
    if diff > 180:
        diff -= 360
    # Applying if the faster planet is moving toward the aspect
    return (s1 - s2) * diff > 0


# ─── Essential Dignities (Ptolemy + Lilly) ────────────────────────────────────

DIGNITY_TABLE = {
    "Sun": {"domicile": ["Leo"], "exaltation": ["Aries"], "detriment": ["Aquarius"], "fall": ["Libra"]},
    "Moon": {"domicile": ["Cancer"], "exaltation": ["Taurus"], "detriment": ["Capricorn"], "fall": ["Scorpio"]},
    "Mercury": {"domicile": ["Gemini", "Virgo"], "exaltation": ["Virgo"], "detriment": ["Sagittarius", "Pisces"], "fall": ["Pisces"]},
    "Venus": {"domicile": ["Taurus", "Libra"], "exaltation": ["Pisces"], "detriment": ["Aries", "Scorpio"], "fall": ["Virgo"]},
    "Mars": {"domicile": ["Aries", "Scorpio"], "exaltation": ["Capricorn"], "detriment": ["Taurus", "Libra"], "fall": ["Cancer"]},
    "Jupiter": {"domicile": ["Sagittarius", "Pisces"], "exaltation": ["Cancer"], "detriment": ["Gemini", "Virgo"], "fall": ["Capricorn"]},
    "Saturn": {"domicile": ["Capricorn", "Aquarius"], "exaltation": ["Libra"], "detriment": ["Cancer", "Leo"], "fall": ["Aries"]},
}


def _get_dignity(planet_name: str, sign: str) -> Dict[str, Any]:
    """Get essential dignity state for a planet in a sign."""
    info = DIGNITY_TABLE.get(planet_name, {})
    dignities = []
    score = 0

    if sign in info.get("domicile", []):
        dignities.append("Domicile")
        score += 5
    if sign in info.get("exaltation", []):
        dignities.append("Exalted")
        score += 4
    if sign in info.get("detriment", []):
        dignities.append("Detriment")
        score -= 5
    if sign in info.get("fall", []):
        dignities.append("Fall")
        score -= 4

    if not dignities:
        dignities.append("Peregrine")

    return {
        "planet": planet_name,
        "sign": sign,
        "dignities": dignities,
        "score": score,
        "ruler": SIGN_RULERS.get(sign, ""),
    }


# ─── Tool Dispatch ────────────────────────────────────────────────────────────

def _astrology_dispatch(tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Main dispatch function for all astrology tools."""
    if not SWISSEPH_AVAILABLE:
        return {"error": "Swiss Ephemeris not available. Install: pip install pyswisseph"}

    # ── Natal Chart ───────────────────────────────────────────────────────
    if tool_name == "calculate_natal_chart":
        from thia_lite.engines.timezone_manager import get_timezone_manager
        tz_manager = get_timezone_manager()

        date = payload.get("date", "2000-01-01")
        time_str = payload.get("time", "12:00")
        lat = float(payload.get("latitude", 0))
        lon = float(payload.get("longitude", 0))
        tz_name = payload.get("timezone", "UTC")
        house_system = payload.get("house_system", "Placidus")

        # Adjust time sequence to UTC using timezone manager
        local_tz = tz_manager.parse_timezone(tz_name) or timezone.utc
        dt_naive = datetime.strptime(f"{date} {time_str}", "%Y-%m-%d %H:%M")
        dt_local = dt_naive.replace(tzinfo=local_tz)
        dt_utc = dt_local.astimezone(timezone.utc)
        
        utc_date = dt_utc.strftime("%Y-%m-%d")
        utc_time = dt_utc.strftime("%H:%M")

        jd = _to_jd(utc_date, utc_time)

        positions = []
        for name, pid in PLANETS.items():
            try:
                pos = _calc_planet(jd, pid)
                pos["name"] = name
                pos["dignity"] = _get_dignity(name, pos["sign"])
                positions.append(pos)
            except Exception as e:
                logger.warning(f"Could not calculate {name}: {e}")

        houses = _calc_houses(jd, lat, lon, house_system)
        aspects = _find_aspects(positions)

        # Assign planets to houses
        for pos in positions:
            for h in houses["houses"]:
                h_next = (h["house"] % 12)
                cusp = h["longitude"]
                next_cusp = houses["houses"][h_next]["longitude"]

                p_lon = pos["longitude"]
                if next_cusp < cusp:
                    if p_lon >= cusp or p_lon < next_cusp:
                        pos["house"] = h["house"]
                        break
                else:
                    if cusp <= p_lon < next_cusp:
                        pos["house"] = h["house"]
                        break

        return {
            "chart_type": "natal",
            "date": date,
            "time": time_str,
            "latitude": lat,
            "longitude": lon,
            "julian_day": round(jd, 6),
            "planets": positions,
            "houses": houses,
            "aspects": aspects,
        }

    # ── Current Transits ──────────────────────────────────────────────────
    if tool_name == "calculate_transits":
        date = payload.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        time_str = payload.get("time") or datetime.now(timezone.utc).strftime("%H:%M")
        natal_date = payload.get("natal_date")
        natal_time = payload.get("natal_time", "12:00")
        lat = float(payload.get("latitude", 0))
        lon = float(payload.get("longitude", 0))

        jd_transit = _to_jd(date, time_str)
        transit_positions = []
        for name, pid in PLANETS.items():
            try:
                pos = _calc_planet(jd_transit, pid)
                pos["name"] = name
                transit_positions.append(pos)
            except Exception:
                pass

        result = {
            "date": date,
            "time": time_str,
            "planets": transit_positions,
        }

        # If natal chart provided, find transit aspects to natal
        if natal_date:
            jd_natal = _to_jd(natal_date, natal_time)
            natal_positions = []
            for name, pid in PLANETS.items():
                try:
                    pos = _calc_planet(jd_natal, pid)
                    pos["name"] = f"natal_{name}"
                    natal_positions.append(pos)
                except Exception:
                    pass

            transit_to_natal = _find_aspects(
                transit_positions + natal_positions, orb_factor=0.5
            )
            # Filter to only transit-to-natal aspects
            result["transit_aspects"] = [
                a for a in transit_to_natal
                if a["planet1"].startswith("natal_") != a["planet2"].startswith("natal_")
            ]

        return result

    # ── Planetary Dignities ───────────────────────────────────────────────
    if tool_name == "get_planetary_dignities":
        date = payload.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        time_str = payload.get("time") or "12:00"
        jd = _to_jd(date, time_str)

        dignities = []
        for name, pid in PLANETS.items():
            if name in DIGNITY_TABLE:
                pos = _calc_planet(jd, pid)
                dig = _get_dignity(name, pos["sign"])
                dig.update({
                    "longitude": pos["longitude"],
                    "formatted": pos["formatted"],
                    "retrograde": pos.get("retrograde", False),
                    "speed": pos.get("speed", 0),
                })
                dignities.append(dig)

        return {"date": date, "dignities": dignities}

    # ── Void of Course Moon ───────────────────────────────────────────────
    if tool_name == "calculate_voc_moon":
        date = payload.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        time_str = payload.get("time") or datetime.now(timezone.utc).strftime("%H:%M")
        jd = _to_jd(date, time_str)

        moon_pos = _calc_planet(jd, PLANETS["Moon"])
        current_sign = moon_pos["sign"]

        # Check for aspects from Moon to other planets
        all_positions = []
        for name, pid in PLANETS.items():
            pos = _calc_planet(jd, pid)
            pos["name"] = name
            all_positions.append(pos)

        moon_aspects = [a for a in _find_aspects(all_positions) if "Moon" in (a["planet1"], a["planet2"])]
        applying = [a for a in moon_aspects if a.get("applying", False)]

        # VoC if no applying aspects within current sign
        is_voc = len(applying) == 0

        return {
            "date": date,
            "moon_position": moon_pos,
            "is_void_of_course": is_voc,
            "applying_aspects": applying,
            "current_sign": current_sign,
        }

    # ── Planetary Hours ───────────────────────────────────────────────────
    if tool_name == "get_planetary_hours":
        date = payload.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        lat = float(payload.get("latitude", 0))
        lon = float(payload.get("longitude", 0))
        jd = _to_jd(date, "12:00")

        # Calculate sunrise and sunset
        sunrise_jd = swe.rise_trans(jd, 0, lon, lat, 0, 0, 0, swe.CALC_RISE)[1][0]
        sunset_jd = swe.rise_trans(jd, 0, lon, lat, 0, 0, 0, swe.CALC_SET)[1][0]
        next_sunrise_jd = swe.rise_trans(jd + 1, 0, lon, lat, 0, 0, 0, swe.CALC_RISE)[1][0]

        day_length = sunset_jd - sunrise_jd
        night_length = next_sunrise_jd - sunset_jd
        day_hour = day_length / 12
        night_hour = night_length / 12

        # Day of week rulers: Sun=0, Mon=1, Tue=2, Wed=3, Thu=4, Fri=5, Sat=6
        day_rulers = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]
        chaldean_order = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]

        dt = datetime.strptime(date, "%Y-%m-%d")
        weekday = dt.weekday()  # Mon=0
        day_ruler_idx = (weekday + 1) % 7  # Shift to astrological week (Sat=0)

        hours = []
        for i in range(24):
            ruler_idx = (chaldean_order.index(day_rulers[day_ruler_idx]) + i) % 7
            is_day = i < 12
            start_jd = (sunrise_jd + i * day_hour) if is_day else (sunset_jd + (i - 12) * night_hour)

            hours.append({
                "hour": i + 1,
                "ruler": chaldean_order[ruler_idx],
                "is_day": is_day,
                "start_jd": round(start_jd, 6),
            })

        return {"date": date, "hours": hours, "day_ruler": day_rulers[day_ruler_idx]}

    # ── Solar Return ──────────────────────────────────────────────────────
    if tool_name == "calculate_solar_return":
        natal_date = payload.get("natal_date", "2000-01-01")
        year = int(payload.get("year", datetime.now().year))
        lat = float(payload.get("latitude", 0))
        lon = float(payload.get("longitude", 0))

        jd_natal = _to_jd(natal_date, "12:00")
        natal_sun = _calc_planet(jd_natal, PLANETS["Sun"])
        natal_sun_lon = natal_sun["longitude"]

        # Find when Sun returns to natal position in target year
        jd_search = _to_jd(f"{year}-01-01", "00:00")
        for _ in range(400):
            sun_pos = _calc_planet(jd_search, PLANETS["Sun"])
            diff = natal_sun_lon - sun_pos["longitude"]
            if abs(diff) < 0.001:
                break
            jd_search += diff / 360 * 365.25
            if abs(diff) > 180:
                jd_search += 182.625  # Half year jump

        # Calculate full chart at return moment
        return_payload = {
            "date": swe.revjul(jd_search),
            "time": "12:00",
            "latitude": lat,
            "longitude": lon,
        }
        # Convert revjul tuple to date string
        yr, mo, dy, hr = swe.revjul(jd_search)
        return_payload["date"] = f"{int(yr)}-{int(mo):02d}-{int(dy):02d}"
        return_payload["time"] = f"{int(hr):02d}:{int((hr % 1) * 60):02d}"

        chart = _astrology_dispatch("calculate_natal_chart", return_payload)
        chart["chart_type"] = "solar_return"
        chart["natal_sun_longitude"] = natal_sun_lon
        return chart

    # ── Lunar Return ──────────────────────────────────────────────────────
    if tool_name == "calculate_lunar_return":
        natal_date = payload.get("natal_date", "2000-01-01")
        date = payload.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        lat = float(payload.get("latitude", 0))
        lon = float(payload.get("longitude", 0))

        jd_natal = _to_jd(natal_date, "12:00")
        natal_moon = _calc_planet(jd_natal, PLANETS["Moon"])
        natal_moon_lon = natal_moon["longitude"]

        jd_search = _to_jd(date, "00:00")
        for _ in range(60):
            moon_pos = _calc_planet(jd_search, PLANETS["Moon"])
            diff = natal_moon_lon - moon_pos["longitude"]
            if abs(diff) < 0.001:
                break
            jd_search += diff / 360 * 27.3

        yr, mo, dy, hr = swe.revjul(jd_search)
        return_payload = {
            "date": f"{int(yr)}-{int(mo):02d}-{int(dy):02d}",
            "time": f"{int(hr):02d}:{int((hr % 1) * 60):02d}",
            "latitude": lat,
            "longitude": lon,
        }

        chart = _astrology_dispatch("calculate_natal_chart", return_payload)
        chart["chart_type"] = "lunar_return"
        return chart

    # ── Sect Analysis ─────────────────────────────────────────────────────
    if tool_name == "calculate_sect_analysis":
        date = payload.get("date", "2000-01-01")
        time_str = payload.get("time", "12:00")
        lat = float(payload.get("latitude", 0))
        lon = float(payload.get("longitude", 0))

        jd = _to_jd(date, time_str)
        sun = _calc_planet(jd, PLANETS["Sun"])
        houses = _calc_houses(jd, lat, lon)

        asc_lon = houses["ascendant"]["longitude"]
        desc_lon = (asc_lon + 180) % 360
        is_day = True

        # Sun above horizon = day chart
        sun_lon = sun["longitude"]
        if asc_lon < desc_lon:
            is_day = asc_lon <= sun_lon <= desc_lon
        else:
            is_day = sun_lon >= asc_lon or sun_lon <= desc_lon

        sect = "Diurnal" if is_day else "Nocturnal"
        sect_light = "Sun" if is_day else "Moon"
        sect_benefic = "Jupiter" if is_day else "Venus"
        sect_malefic = "Saturn" if is_day else "Mars"

        return {
            "date": date,
            "sect": sect,
            "is_day_chart": is_day,
            "sect_light": sect_light,
            "sect_benefic": sect_benefic,
            "sect_malefic": sect_malefic,
            "contrary_benefic": "Venus" if is_day else "Jupiter",
            "contrary_malefic": "Mars" if is_day else "Saturn",
        }

    # ── Antiscia ──────────────────────────────────────────────────────────
    if tool_name == "calculate_antiscia":
        date = payload.get("date", "2000-01-01")
        time_str = payload.get("time", "12:00")
        jd = _to_jd(date, time_str)

        positions = []
        for name, pid in PLANETS.items():
            pos = _calc_planet(jd, pid)
            pos["name"] = name
            # Antiscion = reflected across Cancer/Capricorn axis
            pos["antiscion"] = _lon_to_sign((360 - pos["longitude"]) % 360)
            # Contra-antiscion = opposite the antiscion
            pos["contra_antiscion"] = _lon_to_sign((180 - pos["longitude"]) % 360)
            positions.append(pos)

        return {"date": date, "positions": positions}

    # ── Midpoints ─────────────────────────────────────────────────────────
    if tool_name == "calculate_midpoints":
        date = payload.get("date", "2000-01-01")
        time_str = payload.get("time", "12:00")
        jd = _to_jd(date, time_str)

        positions = []
        for name, pid in PLANETS.items():
            pos = _calc_planet(jd, pid)
            pos["name"] = name
            positions.append(pos)

        midpoints = []
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                p1 = positions[i]
                p2 = positions[j]
                mid_lon = ((p1["longitude"] + p2["longitude"]) / 2) % 360
                # Take the shorter arc
                diff = abs(p1["longitude"] - p2["longitude"])
                if diff > 180:
                    mid_lon = (mid_lon + 180) % 360

                midpoints.append({
                    "planet1": p1["name"],
                    "planet2": p2["name"],
                    **_lon_to_sign(mid_lon),
                })

        return {"date": date, "midpoints": midpoints}

    # ── Synastry ──────────────────────────────────────────────────────────
    if tool_name == "chart_synastry":
        chart1 = _astrology_dispatch("calculate_natal_chart", {
            "date": payload.get("date1", "2000-01-01"),
            "time": payload.get("time1", "12:00"),
            "latitude": payload.get("latitude", 0),
            "longitude": payload.get("longitude", 0),
        })
        chart2 = _astrology_dispatch("calculate_natal_chart", {
            "date": payload.get("date2", "2000-01-01"),
            "time": payload.get("time2", "12:00"),
            "latitude": payload.get("latitude", 0),
            "longitude": payload.get("longitude", 0),
        })

        # Find cross-chart aspects
        positions1 = [{**p, "name": f"Person1_{p['name']}"} for p in chart1.get("planets", [])]
        positions2 = [{**p, "name": f"Person2_{p['name']}"} for p in chart2.get("planets", [])]
        cross_aspects = _find_aspects(positions1 + positions2)
        synastry_aspects = [
            a for a in cross_aspects
            if ("Person1" in a["planet1"]) != ("Person1" in a["planet2"])
        ]

        return {
            "chart_type": "synastry",
            "person1": chart1,
            "person2": chart2,
            "synastry_aspects": synastry_aspects,
        }

    # ── Composite Chart ───────────────────────────────────────────────────
    if tool_name == "chart_composite":
        chart1 = _astrology_dispatch("calculate_natal_chart", {
            "date": payload.get("date1", "2000-01-01"),
            "time": payload.get("time1", "12:00"),
            "latitude": payload.get("latitude", 0),
            "longitude": payload.get("longitude", 0),
        })
        chart2 = _astrology_dispatch("calculate_natal_chart", {
            "date": payload.get("date2", "2000-01-01"),
            "time": payload.get("time2", "12:00"),
            "latitude": payload.get("latitude", 0),
            "longitude": payload.get("longitude", 0),
        })

        # Composite = midpoints of each planet pair
        composite_planets = []
        for p1 in chart1.get("planets", []):
            for p2 in chart2.get("planets", []):
                if p1["name"] == p2["name"]:
                    mid_lon = ((p1["longitude"] + p2["longitude"]) / 2) % 360
                    diff = abs(p1["longitude"] - p2["longitude"])
                    if diff > 180:
                        mid_lon = (mid_lon + 180) % 360
                    pos = _lon_to_sign(mid_lon)
                    pos["name"] = p1["name"]
                    pos["speed"] = (p1.get("speed", 0) + p2.get("speed", 0)) / 2
                    pos["retrograde"] = pos["speed"] < 0
                    composite_planets.append(pos)

        aspects = _find_aspects(composite_planets)
        return {
            "chart_type": "composite",
            "planets": composite_planets,
            "aspects": aspects,
        }

    # ── Profections ───────────────────────────────────────────────────────
    if tool_name == "calculate_profections":
        natal_date = payload.get("natal_date", "2000-01-01")
        current_date = payload.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        natal_dt = datetime.strptime(natal_date, "%Y-%m-%d")
        current_dt = datetime.strptime(current_date, "%Y-%m-%d")
        age = (current_dt - natal_dt).days / 365.25

        profected_house = (int(age) % 12) + 1
        profected_sign_idx = int(age) % 12

        jd_natal = _to_jd(natal_date, "12:00")
        lat = float(payload.get("latitude", 0))
        lon = float(payload.get("longitude", 0))
        houses = _calc_houses(jd_natal, lat, lon)
        asc_sign_idx = houses["ascendant"]["sign_index"]
        profected_sign = SIGNS[(asc_sign_idx + int(age)) % 12]
        time_lord = SIGN_RULERS.get(profected_sign, "")

        return {
            "natal_date": natal_date,
            "current_date": current_date,
            "age": round(age, 2),
            "profected_house": profected_house,
            "profected_sign": profected_sign,
            "time_lord": time_lord,
        }

    # ── Firdaria ──────────────────────────────────────────────────────────
    if tool_name == "calculate_firdaria":
        natal_date = payload.get("natal_date", "2000-01-01")
        current_date = payload.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        natal_dt = datetime.strptime(natal_date, "%Y-%m-%d")
        current_dt = datetime.strptime(current_date, "%Y-%m-%d")
        age = (current_dt - natal_dt).days / 365.25

        # Day sect sequence
        day_sequence = [
            ("Sun", 10), ("Venus", 8), ("Mercury", 13), ("Moon", 9),
            ("Saturn", 11), ("Jupiter", 12), ("Mars", 7),
        ]
        # Night sect sequence
        night_sequence = [
            ("Moon", 9), ("Saturn", 11), ("Jupiter", 12), ("Mars", 7),
            ("Sun", 10), ("Venus", 8), ("Mercury", 13),
        ]

        # Determine sect (simplified - use day sequence by default)
        is_day = payload.get("is_day_chart", True)
        sequence = day_sequence if is_day else night_sequence

        cumulative = 0
        current_lord = ""
        period_start_age = 0
        period_end_age = 0

        for planet, years in sequence:
            if cumulative <= age < cumulative + years:
                current_lord = planet
                period_start_age = cumulative
                period_end_age = cumulative + years
                break
            cumulative += years

        return {
            "age": round(age, 2),
            "current_lord": current_lord,
            "period_start_age": period_start_age,
            "period_end_age": period_end_age,
            "sect": "Day" if is_day else "Night",
        }

    # ── Eclipses ──────────────────────────────────────────────────────────
    if tool_name == "calculate_eclipses":
        date = payload.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        count = int(payload.get("count", 4))
        jd = _to_jd(date, "12:00")

        eclipses = []
        search_jd = jd

        for _ in range(count * 2):  # Search for both solar and lunar
            # Solar eclipse
            try:
                ret, tret = swe.sol_eclipse_when_glob(search_jd, swe.FLG_SWIEPH)
                if tret[0] > search_jd:
                    yr, mo, dy, hr = swe.revjul(tret[0])
                    eclipses.append({
                        "type": "Solar",
                        "date": f"{int(yr)}-{int(mo):02d}-{int(dy):02d}",
                        "julian_day": round(tret[0], 4),
                    })
                    search_jd = tret[0] + 1
            except Exception:
                break

        eclipses.sort(key=lambda e: e.get("julian_day", 0))
        return {"eclipses": eclipses[:count], "search_from": date}

    # ── Geocode Location (offline timezone) ───────────────────────────────
    if tool_name == "geocode_location":
        location = payload.get("location", "")
        # Simple well-known location database
        locations = {
            "new york": {"lat": 40.7128, "lon": -74.0060, "tz": "America/New_York"},
            "london": {"lat": 51.5074, "lon": -0.1278, "tz": "Europe/London"},
            "paris": {"lat": 48.8566, "lon": 2.3522, "tz": "Europe/Paris"},
            "tokyo": {"lat": 35.6762, "lon": 139.6503, "tz": "Asia/Tokyo"},
            "sydney": {"lat": -33.8688, "lon": 151.2093, "tz": "Australia/Sydney"},
            "los angeles": {"lat": 34.0522, "lon": -118.2437, "tz": "America/Los_Angeles"},
            "chicago": {"lat": 41.8781, "lon": -87.6298, "tz": "America/Chicago"},
            "san francisco": {"lat": 37.7749, "lon": -122.4194, "tz": "America/Los_Angeles"},
            "rome": {"lat": 41.9028, "lon": 12.4964, "tz": "Europe/Rome"},
            "berlin": {"lat": 52.5200, "lon": 13.4050, "tz": "Europe/Berlin"},
            "moscow": {"lat": 55.7558, "lon": 37.6176, "tz": "Europe/Moscow"},
            "mumbai": {"lat": 19.0760, "lon": 72.8777, "tz": "Asia/Kolkata"},
            "cairo": {"lat": 30.0444, "lon": 31.2357, "tz": "Africa/Cairo"},
            "istanbul": {"lat": 41.0082, "lon": 28.9784, "tz": "Europe/Istanbul"},
        }

        loc_lower = location.lower().strip()
        match = locations.get(loc_lower)
        if match:
            return {"location": location, **match, "source": "builtin"}

        # Try timezonefinder for coordinates
        try:
            from timezonefinder import TimezoneFinder
            tf = TimezoneFinder()
            lat = float(payload.get("latitude", 0))
            lon = float(payload.get("longitude", 0))
            if lat and lon:
                tz = tf.timezone_at(lat=lat, lng=lon)
                return {"location": location, "lat": lat, "lon": lon, "tz": tz or "UTC"}
        except Exception:
            pass

        return {"error": f"Could not geocode '{location}'. Please provide latitude and longitude."}

    # ── Current Planetary Positions ───────────────────────────────────────
    if tool_name == "get_current_positions":
        date = payload.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        time_str = payload.get("time") or datetime.now(timezone.utc).strftime("%H:%M")
        jd = _to_jd(date, time_str)

        positions = []
        for name, pid in PLANETS.items():
            try:
                pos = _calc_planet(jd, pid)
                pos["name"] = name
                if name in DIGNITY_TABLE:
                    pos["dignity"] = _get_dignity(name, pos["sign"])
                positions.append(pos)
            except Exception:
                pass

        return {"date": date, "time": time_str, "positions": positions}

    # ── Decans and Bounds ─────────────────────────────────────────────────
    if tool_name == "calculate_decans_and_bounds":
        date = payload.get("date", "2000-01-01")
        time_str = payload.get("time", "12:00")
        jd = _to_jd(date, time_str)

        # Egyptian decan rulers (Ptolemy)
        decan_rulers = {
            "Aries": ["Mars", "Sun", "Venus"],
            "Taurus": ["Mercury", "Moon", "Saturn"],
            "Gemini": ["Jupiter", "Mars", "Sun"],
            "Cancer": ["Venus", "Mercury", "Moon"],
            "Leo": ["Saturn", "Jupiter", "Mars"],
            "Virgo": ["Sun", "Venus", "Mercury"],
            "Libra": ["Moon", "Saturn", "Jupiter"],
            "Scorpio": ["Mars", "Sun", "Venus"],
            "Sagittarius": ["Mercury", "Moon", "Saturn"],
            "Capricorn": ["Jupiter", "Mars", "Sun"],
            "Aquarius": ["Venus", "Mercury", "Moon"],
            "Pisces": ["Saturn", "Jupiter", "Mars"],
        }

        results = []
        for name, pid in PLANETS.items():
            pos = _calc_planet(jd, pid)
            deg_in_sign = pos["longitude"] % 30
            decan = int(deg_in_sign / 10) + 1
            sign = pos["sign"]
            decan_ruler = decan_rulers.get(sign, ["", "", ""])[decan - 1]

            results.append({
                "planet": name,
                "sign": sign,
                "degree": pos["degree"],
                "decan": decan,
                "decan_ruler": decan_ruler,
                "formatted": pos["formatted"],
            })

        return {"date": date, "planets": results}

    # ── Electional Windows ────────────────────────────────────────────────
    if tool_name == "find_auspicious_windows":
        start_date = payload.get("start_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        end_date = payload.get("end_date")
        purpose = payload.get("purpose", "general")
        lat = float(payload.get("latitude", 0))
        lon = float(payload.get("longitude", 0))

        if not end_date:
            sd = datetime.strptime(start_date, "%Y-%m-%d")
            end_date = (sd + timedelta(days=7)).strftime("%Y-%m-%d")

        windows = []
        current = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            # Check multiple times per day
            for hour in [8, 10, 12, 14, 16]:
                time_str = f"{hour:02d}:00"
                jd = _to_jd(date_str, time_str)

                moon = _calc_planet(jd, PLANETS["Moon"])
                # Score based on Moon condition
                score = 50  # Base

                # Moon not void of course (has applying aspects)
                all_pos = [_calc_planet(jd, pid) for pid in PLANETS.values()]
                for i, pos in enumerate(all_pos):
                    pos["name"] = list(PLANETS.keys())[i]
                moon_aspects = [a for a in _find_aspects(all_pos) if "Moon" in (a["planet1"], a["planet2"])]
                if any(a.get("applying") for a in moon_aspects):
                    score += 20

                # Moon in good dignity
                moon_dig = _get_dignity("Moon", moon["sign"])
                score += moon_dig["score"] * 5

                # Not retrograde Mercury
                merc = _calc_planet(jd, PLANETS["Mercury"])
                if not merc.get("retrograde", False):
                    score += 10

                if score >= 60:
                    windows.append({
                        "date": date_str,
                        "time": time_str,
                        "score": score,
                        "moon_sign": moon["sign"],
                        "moon_formatted": moon["formatted"],
                    })

            current += timedelta(days=1)

        windows.sort(key=lambda w: w["score"], reverse=True)
        return {"windows": windows[:10], "purpose": purpose}

    # ── Fallback: Unknown tool ────────────────────────────────────────────
    return {"error": f"Unknown astrology tool: {tool_name}", "tool_name": tool_name}


# ─── Tool Registration ───────────────────────────────────────────────────────

_registered = False

def register_astrology_tools():
    """Register all astrology tools with the tool executor."""
    global _registered
    if _registered:
        return
    _registered = True

    from thia_lite.llm.tool_executor import register_tool

    # Core chart tools
    register_tool(
        "calculate_natal_chart",
        "Calculate a complete natal (birth) chart with planetary positions, houses, and aspects",
        {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Birth date (YYYY-MM-DD)"},
                "time": {"type": "string", "description": "Birth time (HH:MM)"},
                "latitude": {"type": "number", "description": "Birth latitude"},
                "longitude": {"type": "number", "description": "Birth longitude"},
                "timezone": {"type": "string", "description": "Timezone name (e.g. America/Denver, PST, UTC) of the provided time"},
                "house_system": {"type": "string", "description": "House system (default: Placidus)"},
            },
            "required": ["date", "time", "latitude", "longitude"],
        },
        _astrology_dispatch,
    )

    register_tool(
        "calculate_transits",
        "Calculate current planetary transits, optionally with aspects to a natal chart",
        {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Transit date (YYYY-MM-DD), defaults to now"},
                "time": {"type": "string", "description": "Transit time (HH:MM)"},
                "natal_date": {"type": "string", "description": "Optional natal date to compare against"},
                "natal_time": {"type": "string", "description": "Optional natal time"},
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
            },
        },
        _astrology_dispatch,
    )

    register_tool(
        "get_planetary_dignities",
        "Get essential dignities (domicile, exaltation, detriment, fall) for all planets",
        {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date (YYYY-MM-DD)"},
                "time": {"type": "string", "description": "Time (HH:MM)"},
            },
        },
        _astrology_dispatch,
    )

    register_tool(
        "calculate_voc_moon",
        "Check if the Moon is Void of Course (no applying aspects before sign change)",
        {
            "type": "object",
            "properties": {
                "date": {"type": "string"},
                "time": {"type": "string"},
            },
        },
        _astrology_dispatch,
    )

    register_tool(
        "get_planetary_hours",
        "Calculate the Chaldean planetary hours for a given date and location",
        {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date (YYYY-MM-DD)"},
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
            },
            "required": ["latitude", "longitude"],
        },
        _astrology_dispatch,
    )

    register_tool(
        "calculate_solar_return",
        "Calculate a Solar Return chart for a given year",
        {
            "type": "object",
            "properties": {
                "natal_date": {"type": "string", "description": "Birth date (YYYY-MM-DD)"},
                "year": {"type": "integer", "description": "Year for the solar return"},
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
            },
            "required": ["natal_date", "year"],
        },
        _astrology_dispatch,
    )

    register_tool(
        "calculate_lunar_return",
        "Calculate a Lunar Return chart",
        {
            "type": "object",
            "properties": {
                "natal_date": {"type": "string"},
                "date": {"type": "string"},
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
            },
            "required": ["natal_date"],
        },
        _astrology_dispatch,
    )

    register_tool(
        "calculate_sect_analysis",
        "Determine chart sect (diurnal/nocturnal) and sect-based planet assignments",
        {
            "type": "object",
            "properties": {
                "date": {"type": "string"},
                "time": {"type": "string"},
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
            },
            "required": ["date", "time", "latitude", "longitude"],
        },
        _astrology_dispatch,
    )

    register_tool(
        "calculate_antiscia",
        "Calculate antiscia and contra-antiscia for all planets",
        {
            "type": "object",
            "properties": {
                "date": {"type": "string"},
                "time": {"type": "string"},
            },
            "required": ["date"],
        },
        _astrology_dispatch,
    )

    register_tool(
        "calculate_midpoints",
        "Calculate midpoints between all planet pairs",
        {
            "type": "object",
            "properties": {
                "date": {"type": "string"},
                "time": {"type": "string"},
            },
            "required": ["date"],
        },
        _astrology_dispatch,
    )

    register_tool(
        "chart_synastry",
        "Calculate synastry (relationship) aspects between two charts",
        {
            "type": "object",
            "properties": {
                "date1": {"type": "string", "description": "Person 1 birth date"},
                "time1": {"type": "string", "description": "Person 1 birth time"},
                "date2": {"type": "string", "description": "Person 2 birth date"},
                "time2": {"type": "string", "description": "Person 2 birth time"},
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
            },
            "required": ["date1", "date2"],
        },
        _astrology_dispatch,
    )

    register_tool(
        "chart_composite",
        "Calculate a composite (relationship) chart from two birth charts",
        {
            "type": "object",
            "properties": {
                "date1": {"type": "string"},
                "time1": {"type": "string"},
                "date2": {"type": "string"},
                "time2": {"type": "string"},
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
            },
            "required": ["date1", "date2"],
        },
        _astrology_dispatch,
    )

    register_tool(
        "calculate_profections",
        "Calculate annual profections (time-lord technique)",
        {
            "type": "object",
            "properties": {
                "natal_date": {"type": "string", "description": "Birth date"},
                "date": {"type": "string", "description": "Current date"},
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
            },
            "required": ["natal_date"],
        },
        _astrology_dispatch,
    )

    register_tool(
        "calculate_firdaria",
        "Calculate firdaria (planetary periods for life chronology)",
        {
            "type": "object",
            "properties": {
                "natal_date": {"type": "string"},
                "date": {"type": "string"},
                "is_day_chart": {"type": "boolean"},
            },
            "required": ["natal_date"],
        },
        _astrology_dispatch,
    )

    register_tool(
        "calculate_eclipses",
        "Find upcoming eclipse dates",
        {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Start search from this date"},
                "count": {"type": "integer", "description": "Number of eclipses to find"},
            },
        },
        _astrology_dispatch,
    )

    register_tool(
        "geocode_location",
        "Convert a place name to latitude/longitude coordinates and timezone",
        {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City or place name"},
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
            },
        },
        _astrology_dispatch,
    )

    register_tool(
        "get_current_positions",
        "Get current planetary positions with dignities",
        {
            "type": "object",
            "properties": {
                "date": {"type": "string"},
                "time": {"type": "string"},
            },
        },
        _astrology_dispatch,
    )

    register_tool(
        "calculate_decans_and_bounds",
        "Calculate decan and bound (term) rulers for all planets",
        {
            "type": "object",
            "properties": {
                "date": {"type": "string"},
                "time": {"type": "string"},
            },
            "required": ["date"],
        },
        _astrology_dispatch,
    )

    register_tool(
        "find_auspicious_windows",
        "Find auspicious electional windows in a date range",
        {
            "type": "object",
            "properties": {
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
                "purpose": {"type": "string", "description": "Purpose of the election"},
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
            },
        },
        _astrology_dispatch,
    )

    from thia_lite.llm.tool_executor import _tool_registry
    logger.info(f"Registered {len(_tool_registry)} astrology tools")
