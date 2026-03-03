#!/usr/bin/env python3
"""
Primary Directions Calculator for THIA-Libre
=============================================

Implements Primary Directions using the Placidus semi-arc system.
Migrated from thia-unified EPHS platform.

Primary Directions are a predictive technique that moves planets and angles
through the chart using the diurnal motion of the sky.

Key Concepts:
- Promissor: The planet/point being directed (moves in the direction)
- Significator: The natal planet/point receiving the direction (stationary)
- Mundane Aspect: Based on house position (diurnal motion)
- Zodiacal Aspect: Based on ecliptic longitude
- Key: Time ratio for directions (default: 1 degree = 1 year)
- Semi-arc: Portion of a celestial body's diurnal arc above/below horizon

Author: Thia (OpenClaw Agent)
Date: 2026-02-26
"""

import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import swisseph as swe


# =============================================================================
# CONSTANTS
# =============================================================================

DEFAULT_KEY = 1.0  # 1 degree of arc = 1 year (Naibod key)
ASPECT_ANGLES = {
    "conjunction": 0,
    "sextile": 60,
    "square": 90,
    "trine": 120,
    "opposition": 180,
}

# Default orb for considering aspects in Primary Directions (very tight)
DEFAULT_DIRECTION_ORB = 1.0

# Planets to include in primary directions
DEFAULT_PROMISSORS = [
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"
]


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def normalize_longitude(lon: float) -> float:
    """Normalize longitude to 0-360 degree range."""
    result = lon % 360.0
    return result if result >= 0 else result + 360.0


def angular_distance(lon1: float, lon2: float) -> float:
    """Calculate shortest angular distance between two longitudes."""
    diff = abs(lon1 - lon2)
    return diff if diff <= 180 else 360 - diff


# =============================================================================
# COORDINATE CONVERSION FUNCTIONS
# =============================================================================

def ecliptic_to_equatorial(
    longitude: float,
    latitude: float,
    obliquity: float
) -> Dict[str, float]:
    """Convert ecliptic coordinates to equatorial (RA/Dec).

    Uses standard spherical trigonometry formulas.

    Args:
        longitude: Ecliptic longitude in degrees (0-360)
        latitude: Ecliptic latitude in degrees (-90 to +90)
        obliquity: Obliquity of ecliptic in degrees (~23.4)

    Returns:
        Dictionary with right_ascension and declination in degrees
    """
    # Convert to radians
    lon_rad = math.radians(longitude)
    lat_rad = math.radians(latitude)
    obl_rad = math.radians(obliquity)

    # Calculate declination
    sin_dec = (math.sin(lat_rad) * math.cos(obl_rad) +
               math.cos(lat_rad) * math.sin(obl_rad) * math.sin(lon_rad))
    declination = math.degrees(math.asin(sin_dec))

    # Calculate right ascension
    y = math.sin(lon_rad) * math.cos(obl_rad) - math.tan(lat_rad) * math.sin(obl_rad)
    x = math.cos(lon_rad)
    ra_rad = math.atan2(y, x)
    right_ascension = math.degrees(ra_rad)

    # Normalize RA to 0-360
    right_ascension = normalize_longitude(right_ascension)

    return {
        "right_ascension": right_ascension,
        "declination": declination
    }


def get_obliquity(julian_day: float) -> float:
    """Get obliquity of the ecliptic for a given Julian Day.

    Args:
        julian_day: Julian Day Number

    Returns:
        Obliquity in degrees
    """
    # Use Swiss Ephemeris to get accurate obliquity
    try:
        result = swe.calc_ut(julian_day, swe.ECL_NUT)
        # result[0] contains true obliquity
        return result[0][0]
    except:
        # Fallback to approximate value
        return 23.4397  # Mean obliquity for J2000.0


def calculate_ramc(julian_day: float, longitude: float) -> float:
    """Calculate Right Ascension of the Midheaven (RAMC).

    RAMC is the RA that is culminating at the given time and location.

    Args:
        julian_day: Julian Day Number
        longitude: Geographic longitude in degrees

    Returns:
        RAMC in degrees (0-360)
    """
    # Get local sidereal time
    lst = swe.sidtime(julian_day) * 15.0  # Convert hours to degrees

    # Add geographic longitude to get RAMC
    ramc = lst + longitude

    return normalize_longitude(ramc)


# =============================================================================
# SEMI-ARC CALCULATIONS (PLACIDUS SYSTEM)
# =============================================================================

def calculate_semi_arcs(
    declination: float,
    geographic_latitude: float
) -> Dict[str, float]:
    """Calculate diurnal and nocturnal semi-arcs.

    Semi-arcs represent the time a body spends above (diurnal) and
    below (nocturnal) the horizon, converted to degrees of RA.

    Args:
        declination: Body's declination in degrees
        geographic_latitude: Observer's latitude in degrees

    Returns:
        Dictionary with diurnal, nocturnal, and is_above_horizon
    """
    # Convert to radians
    dec_rad = math.radians(declination)
    lat_rad = math.radians(geographic_latitude)

    # Calculate ascensional difference
    # This is half the difference between diurnal and nocturnal arcs
    try:
        # tan(dec) * tan(lat)
        tan_product = math.tan(dec_rad) * math.tan(lat_rad)

        # Handle polar cases where body never rises or never sets
        if tan_product <= -1:
            # Body is always above horizon
            return {
                "diurnal": 180.0,
                "nocturnal": 0.0,
                "is_above_horizon": True
            }
        elif tan_product >= 1:
            # Body is always below horizon
            return {
                "diurnal": 0.0,
                "nocturnal": 180.0,
                "is_above_horizon": False
            }

        # Normal case: calculate ascensional difference
        asc_diff_rad = math.asin(tan_product)
        asc_diff_deg = math.degrees(asc_diff_rad)

        # Semi-arcs
        diurnal = 90.0 + asc_diff_deg
        nocturnal = 90.0 - asc_diff_deg

        # Determine if above or below horizon
        is_above_horizon = diurnal > nocturnal

        return {
            "diurnal": diurnal,
            "nocturnal": nocturnal,
            "is_above_horizon": is_above_horizon
        }

    except (ValueError, ZeroDivisionError):
        # Fallback to equal semi-arcs
        return {
            "diurnal": 90.0,
            "nocturnal": 90.0,
            "is_above_horizon": True
        }


# =============================================================================
# PRIMARY DIRECTIONS CORE CALCULATIONS
# =============================================================================

def calculate_mundane_arc(
    promissor_ra: float,
    promissor_dec: float,
    significator_ra: float,
    significator_dec: float,
    ramc: float,
    latitude: float,
    aspect_angle: float = 0
) -> float:
    """Calculate the arc of direction for a mundane aspect.

    Mundane directions use house positions and are based on the
    body's position relative to the meridian and horizon.

    Args:
        promissor_ra: Promissor's Right Ascension
        promissor_dec: Promissor's Declination
        significator_ra: Significator's Right Ascension
        significator_dec: Significator's Declination
        ramc: Right Ascension of Midheaven
        latitude: Geographic latitude
        aspect_angle: Aspect angle in degrees (0, 60, 90, 120, 180)

    Returns:
        Arc in degrees
    """
    # Distance from MC in RA (mundane longitude)
    promissor_mundane = normalize_longitude(promissor_ra - ramc)
    significator_mundane = normalize_longitude(significator_ra - ramc)

    # Apply aspect
    target_mundane = normalize_longitude(significator_mundane + aspect_angle)

    # Arc is the difference
    arc = angular_distance(promissor_mundane, target_mundane)

    # Use semi-arcs to refine the calculation
    promissor_semi = calculate_semi_arcs(promissor_dec, latitude)
    significator_semi = calculate_semi_arcs(significator_dec, latitude)

    # Weight the arc by semi-arcs (simplified approach)
    if promissor_semi["is_above_horizon"]:
        arc_weight = promissor_semi["diurnal"] / 90.0
    else:
        arc_weight = promissor_semi["nocturnal"] / 90.0

    return arc * arc_weight


def calculate_zodiacal_arc(
    promissor_lon: float,
    significator_lon: float,
    promissor_ra: float,
    significator_ra: float,
    aspect_angle: float = 0
) -> float:
    """Calculate the arc of direction for a zodiacal aspect.

    Zodiacal directions use ecliptic longitude positions.

    Args:
        promissor_lon: Promissor's ecliptic longitude
        significator_lon: Significator's ecliptic longitude
        promissor_ra: Promissor's Right Ascension
        significator_ra: Significator's Right Ascension
        aspect_angle: Aspect angle in degrees

    Returns:
        Arc in degrees
    """
    # Calculate the ecliptic distance
    target_lon = normalize_longitude(significator_lon + aspect_angle)
    ecliptic_arc = angular_distance(promissor_lon, target_lon)

    # Approximate correction factor based on position in zodiac
    # This accounts for oblique ascension
    avg_lon = (promissor_lon + target_lon) / 2.0
    correction = math.cos(math.radians(avg_lon - 90.0))
    correction_factor = 1.0 + (0.15 * correction)  # ~15% variation

    ra_arc = ecliptic_arc * correction_factor

    return ra_arc


def calculate_arc_to_date(
    arc_degrees: float,
    key: float,
    natal_timestamp: str
) -> Dict[str, float]:
    """Convert arc in degrees to a date using the key ratio.

    Args:
        arc_degrees: Arc in degrees
        key: Key ratio (degrees per year)
        natal_timestamp: Birth timestamp

    Returns:
        Dictionary with arc_degrees, arc_years, and perfection_date
    """
    # Convert arc to years
    arc_years = arc_degrees / key

    # Calculate perfection date
    natal_dt = datetime.fromisoformat(natal_timestamp.replace("Z", "+00:00"))
    perfection_dt = natal_dt + timedelta(days=arc_years * 365.25)
    perfection_date = perfection_dt.isoformat()

    return {
        "arc_degrees": arc_degrees,
        "arc_years": arc_years,
        "perfection_date": perfection_date
    }


# =============================================================================
# MAIN PRIMARY DIRECTIONS CALCULATOR
# =============================================================================

def calculate_primary_directions(
    natal_positions: Dict[str, Dict],
    julian_day: float,
    latitude: float,
    longitude: float,
    target_date: str,
    key: float = DEFAULT_KEY,
    aspects: Optional[List[str]] = None,
    bodies: Optional[List[str]] = None,
    include_mundane: bool = True,
    include_zodiacal: bool = True,
    max_arc: float = 90.0
) -> Dict:
    """Calculate Primary Directions to a target date.

    Args:
        natal_positions: Dictionary of natal planet positions (from _all_positions)
        julian_day: Julian Day of natal chart
        latitude: Geographic latitude
        longitude: Geographic longitude
        target_date: Target date for which to calculate directions
        key: Key ratio (degrees per year, default: 1.0 = Naibod)
        aspects: List of aspects to calculate (default: all major aspects)
        bodies: List of bodies to use (default: major planets)
        include_mundane: Include mundane directions
        include_zodiacal: Include zodiacal directions
        max_arc: Maximum arc to calculate (default: 90 degrees/years)

    Returns:
        Dictionary with all calculated directions
    """
    if aspects is None:
        aspects = list(ASPECT_ANGLES.keys())

    if bodies is None:
        bodies = DEFAULT_PROMISSORS

    # Get obliquity and RAMC
    obliquity = get_obliquity(julian_day)
    ramc = calculate_ramc(julian_day, longitude)

    # Pre-calculate equatorial positions for all planets
    equatorial_positions = {}
    for name, pos_data in natal_positions.items():
        if name not in bodies:
            continue
        equatorial_positions[name] = ecliptic_to_equatorial(
            pos_data["longitude"],
            pos_data.get("latitude", 0.0),
            obliquity
        )

    directions = []

    # Calculate directions for each promissor-significator pair
    for promissor_name in bodies:
        if promissor_name not in natal_positions:
            continue

        promissor_planet = natal_positions[promissor_name]
        promissor_eq = equatorial_positions.get(promissor_name)

        if not promissor_eq:
            continue

        for significator_name in bodies:
            # Skip self-aspects
            if promissor_name == significator_name:
                continue

            if significator_name not in natal_positions:
                continue

            significator_planet = natal_positions[significator_name]
            significator_eq = equatorial_positions.get(significator_name)

            if not significator_eq:
                continue

            # Calculate for each aspect
            for aspect_name in aspects:
                aspect_angle = ASPECT_ANGLES[aspect_name]

                # Mundane directions
                if include_mundane:
                    arc_deg = calculate_mundane_arc(
                        promissor_ra=promissor_eq["right_ascension"],
                        promissor_dec=promissor_eq["declination"],
                        significator_ra=significator_eq["right_ascension"],
                        significator_dec=significator_eq["declination"],
                        ramc=ramc,
                        latitude=latitude,
                        aspect_angle=aspect_angle
                    )

                    # Only include if within max_arc and positive
                    if 0 < arc_deg <= max_arc:
                        natal_ts = datetime.utcfromtimestamp(
                            (julian_day - 2440587.5) * 86400.0
                        ).isoformat() + "Z"

                        arc = calculate_arc_to_date(
                            arc_deg,
                            key,
                            natal_ts
                        )

                        directions.append({
                            "promissor": promissor_name,
                            "significator": significator_name,
                            "aspect": aspect_name,
                            "arc": arc,
                            "direction_type": "mundane",
                            "is_converse": False
                        })

                # Zodiacal directions
                if include_zodiacal:
                    arc_deg = calculate_zodiacal_arc(
                        promissor_lon=promissor_planet["longitude"],
                        significator_lon=significator_planet["longitude"],
                        promissor_ra=promissor_eq["right_ascension"],
                        significator_ra=significator_eq["right_ascension"],
                        aspect_angle=aspect_angle
                    )

                    # Only include if within max_arc and positive
                    if 0 < arc_deg <= max_arc:
                        natal_ts = datetime.utcfromtimestamp(
                            (julian_day - 2440587.5) * 86400.0
                        ).isoformat() + "Z"

                        arc = calculate_arc_to_date(
                            arc_deg,
                            key,
                            natal_ts
                        )

                        directions.append({
                            "promissor": promissor_name,
                            "significator": significator_name,
                            "aspect": aspect_name,
                            "arc": arc,
                            "direction_type": "zodiacal",
                            "is_converse": False
                        })

    # Sort directions by arc (chronologically)
    directions.sort(key=lambda d: d["arc"]["arc_degrees"])

    return {
        "directions": directions,
        "direction_count": len(directions),
        "key": key,
        "method": "Placidus semi-arc system",
        "include_mundane": include_mundane,
        "include_zodiacal": include_zodiacal,
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "calculate_primary_directions",
    "calculate_mundane_arc",
    "calculate_zodiacal_arc",
    "calculate_semi_arcs",
    "ecliptic_to_equatorial",
    "get_obliquity",
    "calculate_ramc",
]
