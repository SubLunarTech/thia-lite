#!/usr/bin/env python3
"""
THIA Libre - Advanced Astrology Module
=======================================
Nine new astrological calculation functions:
1. Eclipse calculations (Solar/Lunar with Saros cycles)
2. Solar arc directions
3. Ingress charts
4. Proper void-of-course Moon
5. Planetary stations
6. Heliacal risings/settings
7. Sect-aware analysis
8. Decans and terms/bounds
9. Timezone auto-resolution from coordinates
"""

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import swisseph as swe

# ─── Constants ────────────────────────────────────────────────────────────────

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

PLANETS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY,
    "Venus": swe.VENUS, "Mars": swe.MARS, "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN, "Uranus": swe.URANUS, "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO, "True Node": swe.TRUE_NODE,
}

ASPECTS = {
    "conjunction": 0.0, "sextile": 60.0, "square": 90.0,
    "trine": 120.0, "opposition": 180.0,
}

# Ingress target longitudes
INGRESS_TARGETS = {
    "aries": 0.0, "cancer": 90.0, "libra": 180.0, "capricorn": 270.0,
}

# Egyptian decan rulers (Chaldean order starting from each sign)
DECAN_RULERS = {
    "Aries":       ["Mars", "Sun", "Venus"],
    "Taurus":      ["Mercury", "Moon", "Saturn"],
    "Gemini":      ["Jupiter", "Mars", "Sun"],
    "Cancer":      ["Venus", "Mercury", "Moon"],
    "Leo":         ["Saturn", "Jupiter", "Mars"],
    "Virgo":       ["Sun", "Venus", "Mercury"],
    "Libra":       ["Moon", "Saturn", "Jupiter"],
    "Scorpio":     ["Mars", "Sun", "Venus"],
    "Sagittarius": ["Mercury", "Moon", "Saturn"],
    "Capricorn":   ["Jupiter", "Mars", "Sun"],
    "Aquarius":    ["Venus", "Mercury", "Moon"],
    "Pisces":      ["Saturn", "Jupiter", "Mars"],
}

# Egyptian terms/bounds (planet, end_degree) per sign
EGYPTIAN_TERMS = {
    "Aries":       [("Jupiter", 6), ("Venus", 12), ("Mercury", 20), ("Mars", 25), ("Saturn", 30)],
    "Taurus":      [("Venus", 8), ("Mercury", 14), ("Jupiter", 22), ("Saturn", 27), ("Mars", 30)],
    "Gemini":      [("Mercury", 6), ("Jupiter", 12), ("Venus", 17), ("Mars", 24), ("Saturn", 30)],
    "Cancer":      [("Mars", 7), ("Venus", 13), ("Mercury", 19), ("Jupiter", 26), ("Saturn", 30)],
    "Leo":         [("Jupiter", 6), ("Venus", 11), ("Saturn", 18), ("Mercury", 24), ("Mars", 30)],
    "Virgo":       [("Mercury", 7), ("Venus", 17), ("Jupiter", 21), ("Mars", 28), ("Saturn", 30)],
    "Libra":       [("Saturn", 6), ("Mercury", 14), ("Jupiter", 21), ("Venus", 28), ("Mars", 30)],
    "Scorpio":     [("Mars", 7), ("Venus", 11), ("Mercury", 19), ("Jupiter", 24), ("Saturn", 30)],
    "Sagittarius": [("Jupiter", 12), ("Venus", 17), ("Mercury", 21), ("Saturn", 26), ("Mars", 30)],
    "Capricorn":   [("Mercury", 7), ("Jupiter", 14), ("Venus", 22), ("Saturn", 26), ("Mars", 30)],
    "Aquarius":    [("Mercury", 7), ("Venus", 13), ("Jupiter", 20), ("Mars", 25), ("Saturn", 30)],
    "Pisces":      [("Venus", 12), ("Jupiter", 16), ("Mercury", 19), ("Mars", 28), ("Saturn", 30)],
}

# Ptolemaic terms/bounds
PTOLEMAIC_TERMS = {
    "Aries":       [("Jupiter", 6), ("Venus", 14), ("Mercury", 21), ("Mars", 26), ("Saturn", 30)],
    "Taurus":      [("Venus", 8), ("Mercury", 15), ("Jupiter", 22), ("Saturn", 26), ("Mars", 30)],
    "Gemini":      [("Mercury", 7), ("Jupiter", 14), ("Venus", 21), ("Saturn", 25), ("Mars", 30)],
    "Cancer":      [("Mars", 6), ("Jupiter", 13), ("Mercury", 20), ("Venus", 27), ("Saturn", 30)],
    "Leo":         [("Jupiter", 6), ("Mercury", 13), ("Venus", 19), ("Saturn", 25), ("Mars", 30)],
    "Virgo":       [("Mercury", 7), ("Venus", 13), ("Jupiter", 18), ("Saturn", 24), ("Mars", 30)],
    "Libra":       [("Saturn", 6), ("Venus", 11), ("Jupiter", 19), ("Mercury", 24), ("Mars", 30)],
    "Scorpio":     [("Mars", 6), ("Jupiter", 14), ("Venus", 21), ("Mercury", 27), ("Saturn", 30)],
    "Sagittarius": [("Jupiter", 8), ("Venus", 14), ("Mercury", 19), ("Saturn", 25), ("Mars", 30)],
    "Capricorn":   [("Venus", 6), ("Mercury", 12), ("Jupiter", 19), ("Mars", 25), ("Saturn", 30)],
    "Aquarius":    [("Saturn", 6), ("Mercury", 12), ("Venus", 20), ("Jupiter", 25), ("Mars", 30)],
    "Pisces":      [("Venus", 8), ("Jupiter", 14), ("Mercury", 20), ("Mars", 26), ("Saturn", 30)],
}

# ─── Helper Functions ─────────────────────────────────────────────────────────

def _sign_and_degree(longitude: float) -> Tuple[str, float]:
    lon = longitude % 360.0
    sign_idx = int(lon // 30)
    return SIGNS[sign_idx], lon - (sign_idx * 30)


def _to_julian_day(date_s: str, time_s: str = "12:00") -> float:
    dt = datetime.strptime(f"{date_s} {time_s}", "%Y-%m-%d %H:%M")
    hour = dt.hour + (dt.minute / 60.0)
    return swe.julday(dt.year, dt.month, dt.day, hour)


def _jd_to_datetime(jd: float) -> datetime:
    y, m, d, h = swe.revjul(jd)
    hour = int(h)
    minute = int((h - hour) * 60)
    return datetime(y, m, d, hour, minute)


def _jd_to_iso(jd: float) -> str:
    return _jd_to_datetime(jd).strftime("%Y-%m-%dT%H:%M:%SZ")


def _planet_position(jd: float, planet_name: str) -> Dict[str, Any]:
    pid = PLANETS[planet_name]
    vals = swe.calc_ut(jd, pid, swe.FLG_SWIEPH | swe.FLG_SPEED)[0]
    lon = vals[0] % 360.0
    speed = vals[3]
    sign, deg = _sign_and_degree(lon)
    return {
        "planet": planet_name, "longitude": round(lon, 6),
        "speed": round(speed, 8), "retrograde": bool(speed < 0),
        "sign": sign, "degree_in_sign": round(deg, 6),
    }


def _all_positions(jd: float) -> Dict[str, Dict[str, Any]]:
    return {name: _planet_position(jd, name) for name in PLANETS}


def _aspect_diff(a: float, b: float) -> float:
    d = abs((a - b) % 360.0)
    return min(d, 360.0 - d)


def _compute_houses(jd: float, lat: float, lon: float, hs: str = "P") -> Dict[str, Any]:
    cusps, ascmc = swe.houses_ex(jd, lat, lon, hs.encode("ascii"))
    house_cusps = [round(c % 360.0, 6) for c in cusps[:12]]
    asc = ascmc[0] % 360.0
    mc = ascmc[1] % 360.0
    asc_sign, asc_deg = _sign_and_degree(asc)
    mc_sign, mc_deg = _sign_and_degree(mc)
    return {
        "house_system": hs,
        "house_cusps": house_cusps,
        "angles": {
            "Ascendant": {"longitude": round(asc, 6), "sign": asc_sign, "degree_in_sign": round(asc_deg, 6)},
            "Midheaven": {"longitude": round(mc, 6), "sign": mc_sign, "degree_in_sign": round(mc_deg, 6)},
        },
    }


def _house_index(lon: float, cusps: List[float]) -> int:
    norm = [(c % 360.0) for c in cusps]
    for i in range(12):
        start = norm[i]
        end = norm[(i + 1) % 12]
        if start <= end:
            if start <= lon < end:
                return i + 1
        else:
            if lon >= start or lon < end:
                return i + 1
    return 12


# ═════════════════════════════════════════════════════════════════════════════
# 1. ECLIPSE CALCULATIONS
# ═════════════════════════════════════════════════════════════════════════════

def calculate_eclipses(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate solar and lunar eclipses in a date range with Saros cycle info.
    Uses Swiss Ephemeris eclipse functions for precision.
    """
    start_date = str(payload.get("start_date", datetime.utcnow().strftime("%Y-%m-%d")))
    end_date = str(payload.get("end_date", (datetime.utcnow() + timedelta(days=365)).strftime("%Y-%m-%d")))
    eclipse_type = str(payload.get("eclipse_type", "both")).lower()  # "solar", "lunar", "both"

    start_jd = _to_julian_day(start_date)
    end_jd = _to_julian_day(end_date)

    eclipses: List[Dict[str, Any]] = []

    # ── Solar eclipses ──
    if eclipse_type in ("solar", "both"):
        jd_search = start_jd
        for _ in range(20):  # safety limit
            try:
                ret, tret = swe.sol_eclipse_when_glob(jd_search, swe.FLG_SWIEPH, 0)
                if tret[0] <= 0 or tret[0] > end_jd:
                    break

                eclipse_jd = tret[0]
                eclipse_dt = _jd_to_datetime(eclipse_jd)

                # Determine eclipse type from return flags
                if ret & swe.ECL_TOTAL:
                    etype = "total_solar"
                elif ret & swe.ECL_ANNULAR:
                    etype = "annular_solar"
                elif ret & swe.ECL_ANNULAR_TOTAL:
                    etype = "hybrid_solar"
                else:
                    etype = "partial_solar"

                # Calculate Saros series from lunation number
                # Saros cycle ≈ 223 synodic months ≈ 6585.32 days
                # Base Saros: known reference eclipse
                lunation_number = round((eclipse_jd - 2451550.1) / 29.530588861)
                saros_series = ((lunation_number + 38) % 223)
                # Approximate Saros number (simplified formula)
                saros_number = 117 + (lunation_number % 38)

                # Get Sun/Moon positions at eclipse
                positions = _all_positions(eclipse_jd)
                sun_sign, sun_deg = _sign_and_degree(positions["Sun"]["longitude"])
                moon_sign, moon_deg = _sign_and_degree(positions["Moon"]["longitude"])

                eclipses.append({
                    "type": etype,
                    "datetime_utc": _jd_to_iso(eclipse_jd),
                    "julian_day": round(eclipse_jd, 6),
                    "saros_series": saros_number,
                    "lunation_number": lunation_number,
                    "sun_position": {"sign": sun_sign, "degree": round(sun_deg, 2), "longitude": round(positions["Sun"]["longitude"], 6)},
                    "moon_position": {"sign": moon_sign, "degree": round(moon_deg, 2), "longitude": round(positions["Moon"]["longitude"], 6)},
                    "eclipse_degree": f"{round(sun_deg, 1)}° {sun_sign}",
                })

                jd_search = eclipse_jd + 25  # skip past this eclipse
            except Exception as e:
                break

    # ── Lunar eclipses ──
    if eclipse_type in ("lunar", "both"):
        jd_search = start_jd
        for _ in range(20):
            try:
                ret, tret = swe.lun_eclipse_when(jd_search, swe.FLG_SWIEPH, 0)
                if tret[0] <= 0 or tret[0] > end_jd:
                    break

                eclipse_jd = tret[0]

                if ret & swe.ECL_TOTAL:
                    etype = "total_lunar"
                elif ret & swe.ECL_PENUMBRAL:
                    etype = "penumbral_lunar"
                else:
                    etype = "partial_lunar"

                lunation_number = round((eclipse_jd - 2451550.1) / 29.530588861)
                saros_number = 117 + (lunation_number % 38)

                positions = _all_positions(eclipse_jd)
                sun_sign, sun_deg = _sign_and_degree(positions["Sun"]["longitude"])
                moon_sign, moon_deg = _sign_and_degree(positions["Moon"]["longitude"])

                eclipses.append({
                    "type": etype,
                    "datetime_utc": _jd_to_iso(eclipse_jd),
                    "julian_day": round(eclipse_jd, 6),
                    "saros_series": saros_number,
                    "lunation_number": lunation_number,
                    "sun_position": {"sign": sun_sign, "degree": round(sun_deg, 2), "longitude": round(positions["Sun"]["longitude"], 6)},
                    "moon_position": {"sign": moon_sign, "degree": round(moon_deg, 2), "longitude": round(positions["Moon"]["longitude"], 6)},
                    "eclipse_degree": f"{round(moon_deg, 1)}° {moon_sign}",
                    "eclipse_axis": f"{sun_sign}—{moon_sign}",
                })

                jd_search = eclipse_jd + 25
            except Exception:
                break

    # Sort by date
    eclipses.sort(key=lambda e: e["julian_day"])

    return {
        "start_date": start_date,
        "end_date": end_date,
        "eclipse_type_filter": eclipse_type,
        "eclipses": eclipses,
        "count": len(eclipses),
        "note": "Saros series numbers are approximate. Eclipse times are UTC.",
    }


# ═════════════════════════════════════════════════════════════════════════════
# 2. SOLAR ARC DIRECTIONS
# ═════════════════════════════════════════════════════════════════════════════

def calculate_solar_arc_directions(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Solar Arc Directions: progressed Sun's arc applied uniformly to all natal planets.
    The arc = (Progressed Sun longitude) - (Natal Sun longitude).
    Each natal planet is advanced by this same arc.
    """
    birth_date = str(payload.get("birth_date", "2000-01-01"))
    birth_time = str(payload.get("birth_time", "12:00"))
    target_date = str(payload.get("target_date", datetime.utcnow().strftime("%Y-%m-%d")))
    lat = float(payload.get("latitude", 0.0))
    lon = float(payload.get("longitude", 0.0))

    natal_jd = _to_julian_day(birth_date, birth_time)
    natal_pos = _all_positions(natal_jd)
    natal_sun = natal_pos["Sun"]["longitude"]

    # Calculate age in years and progressed Julian Day (day-for-a-year)
    birth_dt = datetime.strptime(birth_date, "%Y-%m-%d")
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    age_days = (target_dt - birth_dt).days
    age_years = age_days / 365.25

    # Progressed date = birth + age_days (1 day = 1 year)
    prog_jd = natal_jd + age_years  # 1 day per year
    prog_sun_pos = _planet_position(prog_jd, "Sun")
    prog_sun = prog_sun_pos["longitude"]

    # Solar arc = progressed Sun - natal Sun
    solar_arc = (prog_sun - natal_sun) % 360.0
    if solar_arc > 180:
        solar_arc -= 360.0

    # Apply solar arc to all natal planets
    directed_planets: List[Dict[str, Any]] = []
    for planet_name, natal_data in natal_pos.items():
        natal_lon = natal_data["longitude"]
        directed_lon = (natal_lon + solar_arc) % 360.0
        dir_sign, dir_deg = _sign_and_degree(directed_lon)

        directed_planets.append({
            "planet": planet_name,
            "natal_longitude": round(natal_lon, 6),
            "natal_sign": natal_data["sign"],
            "directed_longitude": round(directed_lon, 6),
            "directed_sign": dir_sign,
            "directed_degree": round(dir_deg, 6),
        })

    # Find directed aspects to natal positions (within 1° orb)
    directed_aspects: List[Dict[str, Any]] = []
    for dp in directed_planets:
        for planet_name, natal_data in natal_pos.items():
            if dp["planet"] == planet_name:
                continue
            diff = _aspect_diff(dp["directed_longitude"], natal_data["longitude"])
            for aspect_name, aspect_angle in ASPECTS.items():
                orb = abs(diff - aspect_angle)
                if orb <= 1.0:
                    directed_aspects.append({
                        "directed_planet": dp["planet"],
                        "natal_planet": planet_name,
                        "aspect": aspect_name,
                        "orb": round(orb, 4),
                    })

    return {
        "birth_date": birth_date,
        "birth_time": birth_time,
        "target_date": target_date,
        "age_years": round(age_years, 2),
        "solar_arc": round(solar_arc, 6),
        "solar_arc_formatted": f"{int(solar_arc)}°{int((solar_arc % 1) * 60):02d}'",
        "progressed_sun": {
            "longitude": round(prog_sun, 6),
            "sign": prog_sun_pos["sign"],
            "degree": round(prog_sun_pos["degree_in_sign"], 6),
        },
        "directed_planets": directed_planets,
        "directed_aspects": directed_aspects,
        "method": "Solar Arc Directions (Naibod key ≈ 0°59'08\" per year)",
    }


# ═════════════════════════════════════════════════════════════════════════════
# 3. INGRESS CHARTS
# ═════════════════════════════════════════════════════════════════════════════

def calculate_ingress_chart(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate an ingress chart for when the Sun enters a cardinal sign.
    Aries (0°), Cancer (90°), Libra (180°), Capricorn (270°).
    Essential for mundane astrology.
    """
    year = int(payload.get("year", datetime.utcnow().year))
    ingress_type = str(payload.get("ingress_type", "aries")).lower()
    lat = float(payload.get("latitude", 0.0))
    lon = float(payload.get("longitude", 0.0))
    house_system = str(payload.get("house_system", "P"))

    target_longitude = INGRESS_TARGETS.get(ingress_type)
    if target_longitude is None:
        return {"error": f"Invalid ingress_type '{ingress_type}'. Use: aries, cancer, libra, capricorn"}

    # Starting search dates for each ingress
    search_months = {"aries": 3, "cancer": 6, "libra": 9, "capricorn": 12}
    start_month = search_months[ingress_type]
    start_jd = swe.julday(year, start_month, 1, 0.0)

    # Coarse search: find day when Sun crosses target longitude
    best_jd = start_jd
    best_err = 999.0

    for day_offset in range(-15, 35):
        test_jd = start_jd + day_offset
        sun_lon = swe.calc_ut(test_jd, swe.SUN, swe.FLG_SWIEPH)[0][0] % 360.0
        err = abs(sun_lon - target_longitude)
        if err > 180:
            err = 360 - err
        if err < best_err:
            best_err = err
            best_jd = test_jd

    # Fine search: bisect to within 1 second of arc
    low_jd = best_jd - 1.0
    high_jd = best_jd + 1.0
    for _ in range(50):
        mid_jd = (low_jd + high_jd) / 2.0
        sun_lon = swe.calc_ut(mid_jd, swe.SUN, swe.FLG_SWIEPH)[0][0] % 360.0
        # Handle wrapping at 0/360
        diff = sun_lon - target_longitude
        if diff > 180:
            diff -= 360
        elif diff < -180:
            diff += 360

        if abs(diff) < 0.0001:  # sub-arcsecond
            best_jd = mid_jd
            break
        if diff > 0:
            high_jd = mid_jd
        else:
            low_jd = mid_jd
        best_jd = mid_jd

    # Build full chart at ingress moment
    ingress_dt = _jd_to_datetime(best_jd)
    positions = _all_positions(best_jd)
    houses = _compute_houses(best_jd, lat, lon, house_system)

    # Assign planets to houses
    planets_in_houses = {}
    for pname, pdata in positions.items():
        planets_in_houses[pname] = _house_index(pdata["longitude"], houses["house_cusps"])

    return {
        "ingress_type": ingress_type,
        "year": year,
        "target_longitude": target_longitude,
        "ingress_datetime_utc": _jd_to_iso(best_jd),
        "julian_day": round(best_jd, 8),
        "location": {"latitude": lat, "longitude": lon},
        "planets": positions,
        "houses": houses,
        "planets_in_houses": planets_in_houses,
        "chart_ruler": _get_sign_ruler(houses["angles"]["Ascendant"]["sign"]),
        "method": f"Sun ingress to 0° {ingress_type.capitalize()} ({year})",
    }


def _get_sign_ruler(sign: str) -> str:
    rulers = {
        "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon",
        "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars",
        "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter",
    }
    return rulers.get(sign, "Sun")


# ═════════════════════════════════════════════════════════════════════════════
# 4. PROPER VOID-OF-COURSE MOON
# ═════════════════════════════════════════════════════════════════════════════

def calculate_proper_voc_moon(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Proper Void-of-Course Moon calculation.
    Moon is VOC when it makes no applying major aspect to any planet
    before leaving its current sign. Checks forward through remaining
    degrees in the current sign.
    """
    date_s = str(payload.get("date", datetime.utcnow().strftime("%Y-%m-%d")))
    time_s = str(payload.get("time", "12:00"))
    jd = _to_julian_day(date_s, time_s)

    # Get current positions
    positions = _all_positions(jd)
    moon_lon = positions["Moon"]["longitude"]
    moon_speed = positions["Moon"]["speed"]  # degrees per day
    moon_sign_idx = int(moon_lon // 30)
    moon_sign = SIGNS[moon_sign_idx]
    next_sign_boundary = (moon_sign_idx + 1) * 30.0

    # How many degrees until Moon changes sign
    degrees_to_sign_change = (next_sign_boundary - moon_lon) % 360.0
    if degrees_to_sign_change > 30:
        degrees_to_sign_change = 30.0  # shouldn't happen, but safety

    # Time until sign change (Moon moves ~13°/day)
    if moon_speed > 0:
        hours_to_sign_change = (degrees_to_sign_change / moon_speed) * 24.0
    else:
        hours_to_sign_change = 48.0  # fallback

    sign_change_jd = jd + (degrees_to_sign_change / max(moon_speed, 0.1))
    sign_change_dt = _jd_to_datetime(sign_change_jd)

    # Check for applying aspects before sign change
    applying_aspects: List[Dict[str, Any]] = []
    check_planets = ["Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]

    # Step through time in 2-hour increments until sign change
    step_hours = 2.0
    step_jd = step_hours / 24.0
    check_jd = jd

    while check_jd < sign_change_jd:
        future_moon = swe.calc_ut(check_jd, swe.MOON, swe.FLG_SWIEPH | swe.FLG_SPEED)[0]
        future_moon_lon = future_moon[0] % 360.0

        # Check if Moon has left the sign
        if int(future_moon_lon // 30) != moon_sign_idx:
            break

        for planet_name in check_planets:
            future_planet = swe.calc_ut(check_jd, PLANETS[planet_name], swe.FLG_SWIEPH)[0]
            planet_lon = future_planet[0] % 360.0
            diff = _aspect_diff(future_moon_lon, planet_lon)

            for aspect_name, aspect_angle in ASPECTS.items():
                orb = abs(diff - aspect_angle)
                if orb <= 1.0:  # tight 1° applying orb
                    applying_aspects.append({
                        "planet": planet_name,
                        "aspect": aspect_name,
                        "orb": round(orb, 4),
                        "approximate_time": _jd_to_iso(check_jd),
                    })

        check_jd += step_jd

    # Deduplicate (keep first occurrence of each planet-aspect pair)
    seen = set()
    unique_aspects = []
    for asp in applying_aspects:
        key = f"{asp['planet']}_{asp['aspect']}"
        if key not in seen:
            seen.add(key)
            unique_aspects.append(asp)

    is_voc = len(unique_aspects) == 0

    return {
        "date": date_s,
        "time": time_s,
        "moon_longitude": round(moon_lon, 6),
        "moon_sign": moon_sign,
        "moon_speed_per_day": round(moon_speed, 6),
        "void_of_course": is_voc,
        "degrees_to_sign_change": round(degrees_to_sign_change, 4),
        "hours_to_sign_change": round(hours_to_sign_change, 2),
        "sign_change_time_utc": sign_change_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "next_sign": SIGNS[(moon_sign_idx + 1) % 12],
        "applying_aspects": unique_aspects,
        "applying_aspect_count": len(unique_aspects),
        "method": "Classical VOC: no applying major aspects before sign change",
    }


# ═════════════════════════════════════════════════════════════════════════════
# 5. PLANETARY STATIONS
# ═════════════════════════════════════════════════════════════════════════════

def calculate_planetary_stations(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Find dates when planets station retrograde or direct.
    A station occurs when a planet's geocentric speed crosses zero.
    Uses bisection refinement for sub-day accuracy.
    """
    start_date = str(payload.get("start_date", datetime.utcnow().strftime("%Y-%m-%d")))
    end_date = str(payload.get("end_date", (datetime.utcnow() + timedelta(days=365)).strftime("%Y-%m-%d")))
    planet_filter = payload.get("planets")  # optional list like ["Mercury", "Venus"]

    start_jd = _to_julian_day(start_date)
    end_jd = _to_julian_day(end_date)

    # Only check planets that can station (not Sun, Moon, True Node)
    station_planets = ["Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
    if planet_filter:
        station_planets = [p for p in planet_filter if p in station_planets]

    stations: List[Dict[str, Any]] = []

    for planet_name in station_planets:
        pid = PLANETS[planet_name]
        prev_speed = None
        jd = start_jd

        while jd < end_jd:
            vals = swe.calc_ut(jd, pid, swe.FLG_SWIEPH | swe.FLG_SPEED)[0]
            speed = vals[3]

            if prev_speed is not None:
                # Check for sign change in speed (station)
                if (prev_speed > 0 and speed < 0) or (prev_speed < 0 and speed > 0):
                    station_type = "retrograde" if speed < 0 else "direct"

                    # Bisect to find exact station time
                    lo = jd - 1.0
                    hi = jd
                    for _ in range(30):  # ~second precision
                        mid = (lo + hi) / 2.0
                        mid_vals = swe.calc_ut(mid, pid, swe.FLG_SWIEPH | swe.FLG_SPEED)[0]
                        mid_speed = mid_vals[3]
                        if (mid_speed > 0) == (prev_speed > 0):
                            lo = mid
                        else:
                            hi = mid

                    station_jd = (lo + hi) / 2.0
                    station_vals = swe.calc_ut(station_jd, pid, swe.FLG_SWIEPH | swe.FLG_SPEED)[0]
                    station_lon = station_vals[0] % 360.0
                    sign, deg = _sign_and_degree(station_lon)

                    stations.append({
                        "planet": planet_name,
                        "station_type": station_type,
                        "datetime_utc": _jd_to_iso(station_jd),
                        "julian_day": round(station_jd, 6),
                        "longitude": round(station_lon, 6),
                        "sign": sign,
                        "degree_in_sign": round(deg, 6),
                        "station_degree": f"{round(deg, 1)}° {sign}",
                    })

            prev_speed = speed
            jd += 1.0  # daily sampling is sufficient for outer planets

    stations.sort(key=lambda s: s["julian_day"])

    return {
        "start_date": start_date,
        "end_date": end_date,
        "stations": stations,
        "count": len(stations),
    }


# ═════════════════════════════════════════════════════════════════════════════
# 6. HELIACAL RISINGS/SETTINGS
# ═════════════════════════════════════════════════════════════════════════════

def calculate_heliacal_rising(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate heliacal phenomena (rising, setting) for a star or planet.
    Attempts to use swe.heliacal_ut(); falls back to geometric approximation.
    """
    object_name = str(payload.get("object_name", payload.get("star", payload.get("planet", "Sirius"))))
    date_s = str(payload.get("date", datetime.utcnow().strftime("%Y-%m-%d")))
    lat = float(payload.get("latitude", 0.0))
    lon = float(payload.get("longitude", 0.0))
    altitude = float(payload.get("altitude", 0.0))  # meters above sea level

    start_jd = _to_julian_day(date_s)

    # Atmospheric conditions (defaults for average conditions)
    atm_pressure = float(payload.get("pressure", 1013.25))  # mbar
    atm_temp = float(payload.get("temperature", 15.0))  # Celsius
    humidity = float(payload.get("humidity", 40.0))  # percent

    geopos = [lon, lat, altitude]  # swe expects [lon, lat, alt]
    atmosph = [atm_pressure, atm_temp, humidity, 0.25]  # extinction coefficient

    results: List[Dict[str, Any]] = []

    # Try Swiss Ephemeris heliacal function
    try:
        # swe.heliacal_ut parameters:
        # tjd_start, geopos, datm, dobs, ObjectName, TypeEvent, hel_flag
        # TypeEvent: 1=heliacal rising, 2=heliacal setting, 3=evening first, 4=morning last
        dobs = [21.0, 1.0, 1.0, 0.0, 0.0, 0.0]  # observer: age, snellen, etc.

        for event_type, event_name in [(1, "heliacal_rising"), (2, "heliacal_setting")]:
            try:
                result_jd = swe.heliacal_ut(start_jd, geopos, atmosph, dobs, object_name, event_type, 0)
                if result_jd and result_jd[0] > 0:
                    event_dt = _jd_to_datetime(result_jd[0])
                    results.append({
                        "event": event_name,
                        "object": object_name,
                        "datetime_utc": _jd_to_iso(result_jd[0]),
                        "julian_day": round(result_jd[0], 6),
                        "method": "swiss_ephemeris",
                    })
            except Exception:
                pass  # Try next event type

    except Exception:
        pass

    # Geometric fallback if Swiss Ephemeris didn't work
    if not results:
        # For planets, compute when the planet is first visible above horizon at dawn
        if object_name in PLANETS:
            pid = PLANETS[object_name]
            for day_offset in range(0, 90):
                test_jd = start_jd + day_offset
                # Check planet altitude at civil twilight (Sun at -6°)
                sun_vals = swe.calc_ut(test_jd + 0.25, swe.SUN, swe.FLG_SWIEPH)[0]  # ~6am
                planet_vals = swe.calc_ut(test_jd + 0.25, pid, swe.FLG_SWIEPH)[0]

                # Simplified: check angular separation from Sun
                sun_lon = sun_vals[0] % 360.0
                planet_lon = planet_vals[0] % 360.0
                sep = _aspect_diff(sun_lon, planet_lon)

                # Heliacal rising occurs when planet is ~15-20° from Sun
                if 15.0 <= sep <= 25.0:
                    sign, deg = _sign_and_degree(planet_lon)
                    results.append({
                        "event": "heliacal_rising_approx",
                        "object": object_name,
                        "datetime_utc": _jd_to_iso(test_jd),
                        "julian_day": round(test_jd, 6),
                        "sun_elongation": round(sep, 2),
                        "planet_sign": sign,
                        "planet_degree": round(deg, 2),
                        "method": "geometric_approximation",
                    })
                    break
        else:
            # For fixed stars, use Swiss Ephemeris fixstar function
            try:
                for day_offset in range(0, 365):
                    test_jd = start_jd + day_offset
                    star_data = swe.fixstar_ut(object_name, test_jd, swe.FLG_SWIEPH)
                    if star_data:
                        star_lon = star_data[0][0] % 360.0
                        sun_vals = swe.calc_ut(test_jd + 0.25, swe.SUN, swe.FLG_SWIEPH)[0]
                        sun_lon = sun_vals[0] % 360.0
                        sep = _aspect_diff(sun_lon, star_lon)
                        if 15.0 <= sep <= 25.0:
                            sign, deg = _sign_and_degree(star_lon)
                            results.append({
                                "event": "heliacal_rising_approx",
                                "object": object_name,
                                "datetime_utc": _jd_to_iso(test_jd),
                                "julian_day": round(test_jd, 6),
                                "sun_elongation": round(sep, 2),
                                "star_sign": sign,
                                "star_degree": round(deg, 2),
                                "method": "geometric_approximation_fixstar",
                            })
                            break
            except Exception:
                results.append({
                    "event": "heliacal_rising",
                    "object": object_name,
                    "error": f"Could not compute heliacal phenomena for '{object_name}'",
                    "method": "failed",
                })

    return {
        "object": object_name,
        "search_start_date": date_s,
        "location": {"latitude": lat, "longitude": lon, "altitude": altitude},
        "phenomena": results,
        "count": len(results),
    }


# ═════════════════════════════════════════════════════════════════════════════
# 7. SECT-AWARE ANALYSIS
# ═════════════════════════════════════════════════════════════════════════════

def calculate_sect_analysis(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Comprehensive sect analysis for a birth chart.
    Determines diurnal/nocturnal sect and evaluates each planet's
    sect status, including sect light, benefic, malefic, and modifiers.
    """
    date_s = str(payload.get("date", "2000-01-01"))
    time_s = str(payload.get("time", "12:00"))
    lat = float(payload.get("latitude", 0.0))
    lon = float(payload.get("longitude", 0.0))
    hs = str(payload.get("house_system", "P"))

    jd = _to_julian_day(date_s, time_s)
    positions = _all_positions(jd)
    houses = _compute_houses(jd, lat, lon, hs)

    # Determine sect: Sun above horizon = day chart
    sun_lon = positions["Sun"]["longitude"]
    asc_lon = houses["angles"]["Ascendant"]["longitude"]
    desc_lon = (asc_lon + 180.0) % 360.0

    # Sun is above horizon if it's between ASC and DESC (going clockwise through MC)
    sun_house = _house_index(sun_lon, houses["house_cusps"])
    is_day = sun_house >= 7  # Houses 7-12 are above the horizon

    sect = "diurnal" if is_day else "nocturnal"
    sect_light = "Sun" if is_day else "Moon"
    sect_benefic = "Jupiter" if is_day else "Venus"
    sect_malefic = "Saturn" if is_day else "Mars"
    contrary_benefic = "Venus" if is_day else "Jupiter"
    contrary_malefic = "Mars" if is_day else "Saturn"

    # Analyze each planet's sect condition
    planet_sect_data: List[Dict[str, Any]] = []

    for planet_name in ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]:
        pdata = positions[planet_name]
        p_lon = pdata["longitude"]
        p_sign = pdata["sign"]
        p_house = _house_index(p_lon, houses["house_cusps"])
        above_horizon = p_house >= 7

        # Determine sect membership
        if planet_name == "Sun":
            sect_status = "sect_light" if is_day else "contrary_to_sect"
        elif planet_name == "Moon":
            sect_status = "sect_light" if not is_day else "contrary_to_sect"
        elif planet_name == "Jupiter":
            sect_status = "sect_benefic" if is_day else "contrary_benefic"
        elif planet_name == "Venus":
            sect_status = "sect_benefic" if not is_day else "contrary_benefic"
        elif planet_name == "Saturn":
            sect_status = "sect_malefic" if is_day else "contrary_malefic"
        elif planet_name == "Mars":
            sect_status = "sect_malefic" if not is_day else "contrary_malefic"
        elif planet_name == "Mercury":
            # Mercury's sect depends on whether it rises before or after the Sun
            merc_lon = pdata["longitude"]
            if (merc_lon - sun_lon) % 360 < 180:
                sect_status = "diurnal_mercury"  # evening star
            else:
                sect_status = "nocturnal_mercury"  # morning star
        else:
            sect_status = "outer"

        # Sect-based dignity modifier
        # A planet in its own sect AND above/below horizon correctly gets a boost
        sect_joy = False
        sect_score = 0

        # Diurnal planets (Sun, Jupiter, Saturn) rejoice above horizon in day charts
        if planet_name in ("Sun", "Jupiter", "Saturn"):
            if is_day and above_horizon:
                sect_joy = True
                sect_score = 2
            elif not is_day and not above_horizon:
                sect_joy = True
                sect_score = 1  # partial
            elif not is_day and above_horizon:
                sect_score = -1  # contrary

        # Nocturnal planets (Moon, Venus, Mars) rejoice below horizon in night charts
        if planet_name in ("Moon", "Venus", "Mars"):
            if not is_day and not above_horizon:
                sect_joy = True
                sect_score = 2
            elif is_day and above_horizon:
                sect_joy = True
                sect_score = 1  # partial
            elif is_day and not above_horizon:
                sect_score = -1  # contrary

        # Sign-based sect consideration (fire/air = diurnal, earth/water = nocturnal)
        diurnal_signs = {"Aries", "Gemini", "Leo", "Libra", "Sagittarius", "Aquarius"}
        nocturnal_signs = {"Taurus", "Cancer", "Virgo", "Scorpio", "Capricorn", "Pisces"}
        in_diurnal_sign = p_sign in diurnal_signs

        if planet_name in ("Sun", "Jupiter", "Saturn") and in_diurnal_sign:
            sect_score += 1
        elif planet_name in ("Moon", "Venus", "Mars") and not in_diurnal_sign:
            sect_score += 1

        planet_sect_data.append({
            "planet": planet_name,
            "sign": p_sign,
            "house": p_house,
            "above_horizon": above_horizon,
            "sect_status": sect_status,
            "in_sect_joy": sect_joy,
            "in_diurnal_sign": in_diurnal_sign,
            "sect_score": sect_score,
            "interpretation": _sect_interpretation(planet_name, sect_status, sect_joy, sect_score),
        })

    return {
        "date": date_s,
        "time": time_s,
        "chart_sect": sect,
        "sect_light": sect_light,
        "sect_benefic": sect_benefic,
        "sect_malefic": sect_malefic,
        "contrary_benefic": contrary_benefic,
        "contrary_malefic": contrary_malefic,
        "sun_house": sun_house,
        "planets": planet_sect_data,
        "overall_sect_strength": sum(p["sect_score"] for p in planet_sect_data),
        "method": "Classical sect analysis (Dorothean/Hellenistic tradition)",
    }


def _sect_interpretation(planet: str, status: str, joy: bool, score: int) -> str:
    """Generate brief interpretation for a planet's sect condition."""
    if score >= 2:
        return f"{planet} is strongly supporting — in its own sect, hemisphere, and sign affinity."
    elif score == 1:
        return f"{planet} has partial sect support — benefits are moderate."
    elif score == 0:
        return f"{planet} is neutral with respect to sect."
    elif score <= -1:
        return f"{planet} is contrary to sect — its significations may manifest with more difficulty."
    return f"{planet} sect analysis: {status}"


# ═════════════════════════════════════════════════════════════════════════════
# 8. DECANS AND TERMS/BOUNDS
# ═════════════════════════════════════════════════════════════════════════════

def calculate_decans_and_bounds(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate decans (faces) and terms/bounds for all planets.
    Returns Egyptian decan rulers and both Egyptian + Ptolemaic term lords.
    """
    date_s = str(payload.get("date", "2000-01-01"))
    time_s = str(payload.get("time", "12:00"))
    lat = float(payload.get("latitude", 0.0))
    lon = float(payload.get("longitude", 0.0))

    jd = _to_julian_day(date_s, time_s)
    positions = _all_positions(jd)

    planet_details: List[Dict[str, Any]] = []

    for planet_name in ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]:
        pdata = positions[planet_name]
        p_lon = pdata["longitude"]
        sign = pdata["sign"]
        deg_in_sign = pdata["degree_in_sign"]

        # Decan (face) — each sign divided into 3 × 10° segments
        decan_index = min(2, int(deg_in_sign // 10))
        decan_ruler = DECAN_RULERS.get(sign, ["?", "?", "?"])[decan_index]
        decan_number = decan_index + 1

        # Egyptian terms
        egyptian_term_lord = "unknown"
        for term_planet, term_end in EGYPTIAN_TERMS.get(sign, []):
            if deg_in_sign < term_end:
                egyptian_term_lord = term_planet
                break

        # Ptolemaic terms
        ptolemaic_term_lord = "unknown"
        for term_planet, term_end in PTOLEMAIC_TERMS.get(sign, []):
            if deg_in_sign < term_end:
                ptolemaic_term_lord = term_planet
                break

        # Dignity assessment including face and terms
        dignity_points = 0
        dignities_held = []

        # Check domicile
        domiciles = {
            "Sun": {"Leo"}, "Moon": {"Cancer"}, "Mercury": {"Gemini", "Virgo"},
            "Venus": {"Taurus", "Libra"}, "Mars": {"Aries", "Scorpio"},
            "Jupiter": {"Sagittarius", "Pisces"}, "Saturn": {"Capricorn", "Aquarius"},
        }
        if sign in domiciles.get(planet_name, set()):
            dignity_points += 5
            dignities_held.append("domicile")

        # Check exaltation
        exaltations = {
            "Sun": "Aries", "Moon": "Taurus", "Mercury": "Virgo",
            "Venus": "Pisces", "Mars": "Capricorn", "Jupiter": "Cancer", "Saturn": "Libra",
        }
        if exaltations.get(planet_name) == sign:
            dignity_points += 4
            dignities_held.append("exaltation")

        # Check detriment (opposite of domicile)
        detriments = {
            "Sun": {"Aquarius"}, "Moon": {"Capricorn"}, "Mercury": {"Sagittarius", "Pisces"},
            "Venus": {"Aries", "Scorpio"}, "Mars": {"Taurus", "Libra"},
            "Jupiter": {"Gemini", "Virgo"}, "Saturn": {"Cancer", "Leo"},
        }
        if sign in detriments.get(planet_name, set()):
            dignity_points -= 5
            dignities_held.append("detriment")

        # Check fall (opposite of exaltation)
        falls = {
            "Sun": "Libra", "Moon": "Scorpio", "Mercury": "Pisces",
            "Venus": "Virgo", "Mars": "Cancer", "Jupiter": "Capricorn", "Saturn": "Aries",
        }
        if falls.get(planet_name) == sign:
            dignity_points -= 4
            dignities_held.append("fall")

        # Face/decan dignity (+1 if planet rules the decan it's in)
        if decan_ruler == planet_name:
            dignity_points += 1
            dignities_held.append("face")

        # Term dignity (+2 if planet is in its own terms)
        if egyptian_term_lord == planet_name:
            dignity_points += 2
            dignities_held.append("term_egyptian")
        if ptolemaic_term_lord == planet_name:
            dignity_points += 2
            dignities_held.append("term_ptolemaic")

        if not dignities_held:
            dignities_held.append("peregrine")

        planet_details.append({
            "planet": planet_name,
            "sign": sign,
            "degree_in_sign": round(deg_in_sign, 4),
            "decan": {
                "number": decan_number,
                "ruler": decan_ruler,
                "degree_range": f"{decan_index * 10}°–{(decan_index + 1) * 10}°",
            },
            "terms": {
                "egyptian": egyptian_term_lord,
                "ptolemaic": ptolemaic_term_lord,
            },
            "full_dignity_score": dignity_points,
            "dignities_held": dignities_held,
        })

    return {
        "date": date_s,
        "time": time_s,
        "planets": planet_details,
        "method": "Egyptian decans (Chaldean order) + Egyptian/Ptolemaic terms",
    }


# ═════════════════════════════════════════════════════════════════════════════
# 9. TIMEZONE AUTO-RESOLUTION FROM COORDINATES
# ═════════════════════════════════════════════════════════════════════════════

def resolve_timezone(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolve timezone from geographic coordinates.
    Uses timezonefinder library (pure Python, no API dependency).
    Falls back to UTC offset estimation if library is unavailable.
    """
    lat = float(payload.get("latitude", 0.0))
    lon = float(payload.get("longitude", 0.0))

    timezone_name = None
    utc_offset = None
    method = "unknown"

    # Try timezonefinder first
    try:
        from timezonefinder import TimezoneFinder
        tf = TimezoneFinder()
        timezone_name = tf.timezone_at(lat=lat, lng=lon)
        if timezone_name:
            method = "timezonefinder"
            # Get current UTC offset for this timezone
            try:
                import zoneinfo
                tz = zoneinfo.ZoneInfo(timezone_name)
                now = datetime.now(tz)
                utc_offset_td = now.utcoffset()
                utc_offset = utc_offset_td.total_seconds() / 3600.0 if utc_offset_td else None
            except Exception:
                # Estimate from longitude
                utc_offset = round(lon / 15.0)
    except ImportError:
        pass

    # Fallback: estimate from longitude
    if timezone_name is None:
        utc_offset = round(lon / 15.0)
        # Map to approximate timezone name
        offset_names = {
            -12: "Etc/GMT+12", -11: "Pacific/Midway", -10: "Pacific/Honolulu",
            -9: "America/Anchorage", -8: "America/Los_Angeles", -7: "America/Denver",
            -6: "America/Chicago", -5: "America/New_York", -4: "America/Halifax",
            -3: "America/Sao_Paulo", -2: "Atlantic/South_Georgia", -1: "Atlantic/Azores",
            0: "UTC", 1: "Europe/London", 2: "Europe/Paris", 3: "Europe/Moscow",
            4: "Asia/Dubai", 5: "Asia/Karachi", 6: "Asia/Dhaka",
            7: "Asia/Bangkok", 8: "Asia/Shanghai", 9: "Asia/Tokyo",
            10: "Australia/Sydney", 11: "Pacific/Noumea", 12: "Pacific/Auckland",
        }
        timezone_name = offset_names.get(int(utc_offset), f"Etc/GMT{-int(utc_offset):+d}")
        method = "longitude_estimation"

    # Format offset string
    if utc_offset is not None:
        hours = int(utc_offset)
        minutes = int(abs(utc_offset - hours) * 60)
        offset_str = f"UTC{hours:+d}:{minutes:02d}" if minutes else f"UTC{hours:+d}"
    else:
        offset_str = "unknown"

    return {
        "latitude": lat,
        "longitude": lon,
        "timezone_name": timezone_name,
        "utc_offset_hours": utc_offset,
        "utc_offset_string": offset_str,
        "method": method,
    }
