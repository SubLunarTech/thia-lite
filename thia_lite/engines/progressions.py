#!/usr/bin/env python3
"""
Progressions Calculator for THIA-Libre
========================================

Implements secondary, tertiary, and converse progressions for predictive astrology.

Progression Types:
- Secondary Progressions: 1 day after birth = 1 year of life
- Tertiary Progressions: 1 day after birth = 1 lunar month (~27.32 days)
- Converse Progressions: 1 day before birth = 1 year of life (reverse)

Author: Thia (OpenClaw Agent)
Date: 2026-02-26
"""

import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import swisseph as swe


# =============================================================================
# CONSTANTS
# =============================================================================

SECONDARY_RATE = 1.0  # 1 day = 1 year
TERTIARY_RATE = 27.32166  # 1 day = 1 lunar month (sidereal month)
CONVERSE_RATE = -1.0  # 1 day backwards = 1 year

# Station detection thresholds (degrees per day)
STATION_THRESHOLDS = {
    "MERCURY": 0.5,
    "VENUS": 0.5,
    "MARS": 0.2,
    "JUPITER": 0.05,
    "SATURN": 0.03,
    "URANUS": 0.01,
    "NEPTUNE": 0.01,
    "PLUTO": 0.01,
}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def normalize_longitude(lon: float) -> float:
    """Normalize longitude to 0-360 degree range."""
    result = lon % 360.0
    return result if result >= 0 else result + 360.0


def jd_to_iso_timestamp(jd: float) -> str:
    """Convert Julian Day to ISO 8601 timestamp."""
    year, month, day, hour = swe.revjul(jd)
    hour_int = int(hour)
    minute = int((hour - hour_int) * 60)
    second = int(((hour - hour_int) * 60 - minute) * 60)
    return f"{year:04d}-{month:02d}-{day:02d}T{hour_int:02d}:{minute:02d}:{second:02d}Z"


def aspect_diff(lon1: float, lon2: float) -> float:
    """Calculate shortest angular distance between two longitudes."""
    diff = abs(lon1 - lon2)
    return diff if diff <= 180 else 360 - diff


def estimate_days_to_sign_change(
    current_longitude: float,
    daily_motion: float
) -> Optional[float]:
    """Estimate days until planet enters next sign."""
    if abs(daily_motion) < 0.001:  # Essentially stationary
        return None

    # Degree within current sign (0-30)
    degree_in_sign = current_longitude % 30

    if daily_motion > 0:
        # Direct motion - moving toward next sign
        degrees_remaining = 30 - degree_in_sign
        return degrees_remaining / daily_motion
    else:
        # Retrograde - moving toward previous sign
        return degree_in_sign / abs(daily_motion)


def estimate_days_to_station(
    speed_longitude: float,
    planet_name: str
) -> tuple[Optional[float], Optional[str]]:
    """Estimate days until planet stations (changes direction)."""
    threshold = STATION_THRESHOLDS.get(planet_name, 0.1)

    if abs(speed_longitude) < threshold:
        # Planet is near station
        if speed_longitude > 0:
            return (0.0, "direct")  # About to go retrograde
        else:
            return (0.0, "retrograde")  # About to go direct

    # Not near station
    return (None, None)


# =============================================================================
# PROGRESSION CALCULATIONS
# =============================================================================

def calculate_progressed_julian_day(
    natal_jd: float,
    age_years: float,
    progression_rate: float = SECONDARY_RATE
) -> float:
    """Calculate Julian Day for progressed date.

    Args:
        natal_jd: Natal Julian Day
        age_years: Age in years
        progression_rate: Days per year (1.0 for secondary, 27.32 for tertiary, -1.0 for converse)

    Returns:
        Julian Day for progressed calculation
    """
    days_elapsed = age_years * progression_rate
    return natal_jd + days_elapsed


def calculate_sign_and_degree(longitude: float) -> tuple[str, float]:
    """Get zodiac sign and degree within sign from longitude."""
    SIGNS = [
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
    ]
    sign_idx = int(longitude // 30) % 12
    degree = longitude % 30
    return SIGNS[sign_idx], degree


# =============================================================================
# MAIN PROGRESSION FUNCTIONS
# =============================================================================

def calculate_secondary_progression(
    natal_jd: float,
    target_age: float,
    natal_positions: Dict[str, Dict],
    progressed_positions: Dict[str, Dict],
    latitude: float = 0.0,
    longitude: float = 0.0,
    calculate_aspects: bool = True,
    aspect_orbs: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """Calculate secondary progressions for a given age.

    Formula: Progressed date = Natal date + (age in years × 1 day)

    Args:
        natal_jd: Natal Julian Day
        target_age: Age in years (can be decimal, e.g., 30.5)
        natal_positions: Dictionary of natal planet positions
        progressed_positions: Dictionary of progressed planet positions
        latitude: Geographic latitude (for house calculation)
        longitude: Geographic longitude (for house calculation)
        calculate_aspects: Whether to calculate progressed-to-natal aspects
        aspect_orbs: Custom aspect orbs (optional)

    Returns:
        Dictionary with complete progression data
    """
    # Standard aspect orbs
    if aspect_orbs is None:
        aspect_orbs = {
            "conjunction": 8.0,
            "opposition": 8.0,
            "trine": 8.0,
            "square": 8.0,
            "sextile": 6.0,
        }

    # Build progressed positions with analysis
    progressed_planets = []

    for planet_name, prog_pos in progressed_positions.items():
        if planet_name not in natal_positions:
            continue

        natal_pos = natal_positions[planet_name]

        natal_sign = natal_pos.get("sign", "Unknown")
        prog_sign = prog_pos.get("sign", "Unknown")
        sign_changed = natal_sign != prog_sign

        # Estimate days to sign change
        days_to_sign = estimate_days_to_sign_change(
            prog_pos["longitude"],
            prog_pos.get("speed", 0.0)
        )

        # Estimate days to station
        days_to_station, station_type = estimate_days_to_station(
            prog_pos.get("speed", 0.0),
            planet_name
        )

        progressed_planets.append({
            "planet": planet_name,
            "natal_position": {
                "longitude": round(natal_pos["longitude"], 6),
                "sign": natal_sign,
                "degree_in_sign": round(natal_pos.get("degree", 0.0), 2),
                "is_retrograde": natal_pos.get("is_retrograde", False),
            },
            "progressed_position": {
                "longitude": round(prog_pos["longitude"], 6),
                "sign": prog_sign,
                "degree_in_sign": round(prog_pos.get("degree", 0.0), 2),
                "is_retrograde": prog_pos.get("is_retrograde", False),
            },
            "sign_changed": sign_changed,
            "days_to_next_sign": round(days_to_sign, 2) if days_to_sign else None,
            "days_to_station": round(days_to_station, 2) if days_to_station else None,
            "station_type": station_type,
            "arc_motion": round((prog_pos["longitude"] - natal_pos["longitude"]) % 360, 6),
        })

    # Calculate progressed-to-natal aspects
    aspects_list = []
    if calculate_aspects:
        for prog_planet, prog_pos in progressed_positions.items():
            if prog_planet not in natal_positions:
                continue

            for natal_planet, nat_pos in natal_positions.items():
                if prog_planet == natal_planet:
                    continue

                angle = aspect_diff(prog_pos["longitude"], nat_pos["longitude"])

                # Check against aspects
                for aspect_name, max_orb in aspect_orbs.items():
                    # Convert aspect name to angle
                    aspect_angles = {
                        "conjunction": 0,
                        "sextile": 60,
                        "square": 90,
                        "trine": 120,
                        "opposition": 180,
                    }

                    target_angle = aspect_angles.get(aspect_name, 0)
                    orb = abs(angle - target_angle)

                    if orb <= max_orb:
                        aspects_list.append({
                            "progressed_planet": prog_planet,
                            "natal_planet": natal_planet,
                            "aspect": aspect_name,
                            "orb": round(orb, 2),
                            "actual_angle": round(angle, 2),
                            "progressed_longitude": round(prog_pos["longitude"], 4),
                            "natal_longitude": round(nat_pos["longitude"], 4),
                        })
                        break  # Only record closest aspect

    return {
        "progression_type": "secondary",
        "target_age": target_age,
        "progressed_planets": progressed_planets,
        "progressed_to_natal_aspects": aspects_list,
        "aspect_count": len(aspects_list),
        "formula": "1 day after birth = 1 year of life",
    }


def calculate_tertiary_progression(
    natal_jd: float,
    target_age: float,
    natal_positions: Dict[str, Dict],
    progressed_positions: Dict[str, Dict],
    calculate_aspects: bool = True
) -> Dict[str, Any]:
    """Calculate tertiary progressions (1 day = 1 lunar month).

    Formula: Progressed date = Natal date + (age in years × 27.32 days)

    Tertiary progressions use the lunar month cycle, giving a faster-moving
    progression system often used for monthly timing.
    """
    # Build progressed positions
    progressed_planets = []

    for planet_name, prog_pos in progressed_positions.items():
        if planet_name not in natal_positions:
            continue

        natal_pos = natal_positions[planet_name]

        natal_sign = natal_pos.get("sign", "Unknown")
        prog_sign = prog_pos.get("sign", "Unknown")
        sign_changed = natal_sign != prog_sign

        progressed_planets.append({
            "planet": planet_name,
            "natal_position": {
                "longitude": round(natal_pos["longitude"], 6),
                "sign": natal_sign,
            },
            "progressed_position": {
                "longitude": round(prog_pos["longitude"], 6),
                "sign": prog_sign,
            },
            "sign_changed": sign_changed,
            "arc_motion": round((prog_pos["longitude"] - natal_pos["longitude"]) % 360, 6),
        })

    # Calculate aspects
    aspects_list = []
    if calculate_aspects:
        for prog_planet, prog_pos in progressed_positions.items():
            if prog_planet not in natal_positions:
                continue

            for natal_planet, nat_pos in natal_positions.items():
                if prog_planet == natal_planet:
                    continue

                angle = aspect_diff(prog_pos["longitude"], nat_pos["longitude"])

                # Standard orbs
                ASPECT_ORBS = {"conjunction": 8.0, "opposition": 8.0, "trine": 8.0, "square": 8.0, "sextile": 6.0}

                for aspect_name, max_orb in ASPECT_ORBS.items():
                    aspect_angles = {"conjunction": 0, "sextile": 60, "square": 90, "trine": 120, "opposition": 180}
                    target_angle = aspect_angles.get(aspect_name, 0)
                    orb = abs(angle - target_angle)

                    if orb <= max_orb:
                        aspects_list.append({
                            "progressed_planet": prog_planet,
                            "natal_planet": natal_planet,
                            "aspect": aspect_name,
                            "orb": round(orb, 2),
                            "actual_angle": round(angle, 2),
                        })
                        break

    return {
        "progression_type": "tertiary",
        "target_age": target_age,
        "progressed_planets": progressed_planets,
        "progressed_to_natal_aspects": aspects_list,
        "aspect_count": len(aspects_list),
        "formula": "1 day after birth = 1 lunar month (27.32 days)",
    }


def calculate_converse_progression(
    natal_jd: float,
    target_age: float,
    natal_positions: Dict[str, Dict],
    progressed_positions: Dict[str, Dict],
    calculate_aspects: bool = True
) -> Dict[str, Any]:
    """Calculate converse (reverse) progressions.

    Formula: Progressed date = Natal date - (age in years × 1 day)

    Converse progressions move backwards in time, used in some predictive
    techniques to reveal prenatal or karmic patterns.
    """
    # Build progressed positions
    progressed_planets = []

    for planet_name, prog_pos in progressed_positions.items():
        if planet_name not in natal_positions:
            continue

        natal_pos = natal_positions[planet_name]

        natal_sign = natal_pos.get("sign", "Unknown")
        prog_sign = prog_pos.get("sign", "Unknown")
        sign_changed = natal_sign != prog_sign

        progressed_planets.append({
            "planet": planet_name,
            "natal_position": {
                "longitude": round(natal_pos["longitude"], 6),
                "sign": natal_sign,
            },
            "progressed_position": {
                "longitude": round(prog_pos["longitude"], 6),
                "sign": prog_sign,
            },
            "sign_changed": sign_changed,
            "arc_motion": round((prog_pos["longitude"] - natal_pos["longitude"]) % 360, 6),
        })

    # Calculate aspects
    aspects_list = []
    if calculate_aspects:
        for prog_planet, prog_pos in progressed_positions.items():
            if prog_planet not in natal_positions:
                continue

            for natal_planet, nat_pos in natal_positions.items():
                if prog_planet == natal_planet:
                    continue

                angle = aspect_diff(prog_pos["longitude"], nat_pos["longitude"])

                ASPECT_ORBS = {"conjunction": 8.0, "opposition": 8.0, "trine": 8.0, "square": 8.0, "sextile": 6.0}

                for aspect_name, max_orb in ASPECT_ORBS.items():
                    aspect_angles = {"conjunction": 0, "sextile": 60, "square": 90, "trine": 120, "opposition": 180}
                    target_angle = aspect_angles.get(aspect_name, 0)
                    orb = abs(angle - target_angle)

                    if orb <= max_orb:
                        aspects_list.append({
                            "progressed_planet": prog_planet,
                            "natal_planet": natal_planet,
                            "aspect": aspect_name,
                            "orb": round(orb, 2),
                            "actual_angle": round(angle, 2),
                        })
                        break

    return {
        "progression_type": "converse",
        "target_age": target_age,
        "progressed_planets": progressed_planets,
        "progressed_to_natal_aspects": aspects_list,
        "aspect_count": len(aspects_list),
        "formula": "1 day before birth = 1 year of life (reverse direction)",
    }


# =============================================================================
# SOLAR ARC DIRECTIONS
# =============================================================================

def calculate_solar_arc_directions(
    natal_positions: Dict[str, Dict],
    target_age: float,
    longitude_arc: float
) -> Dict[str, Any]:
    """Calculate solar arc directions.

    In solar arc directions, all planets move by the same arc as the
    progressed Sun. This is simpler than secondary progressions but
    widely used in predictive work.

    Args:
        natal_positions: Natal planet positions
        target_age: Age in years
        longitude_arc: The arc the Sun has moved (in degrees)

    Returns:
        Dictionary with solar arc directed positions
    """
    directed_positions = []

    for planet_name, natal_pos in natal_positions.items():
        natal_lon = natal_pos["longitude"]
        directed_lon = (natal_lon + longitude_arc) % 360
        sign, degree = calculate_sign_and_degree(directed_lon)

        directed_positions.append({
            "planet": planet_name,
            "natal_longitude": round(natal_lon, 6),
            "directed_longitude": round(directed_lon, 6),
            "solar_arc": round(longitude_arc, 6),
            "sign": sign,
            "degree_in_sign": round(degree, 2),
        })

    return {
        "direction_type": "solar_arc",
        "target_age": target_age,
        "solar_arc": round(longitude_arc, 6),
        "directed_positions": directed_positions,
        "formula": "All planets move by the Sun's progressed arc",
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "calculate_secondary_progression",
    "calculate_tertiary_progression",
    "calculate_converse_progression",
    "calculate_solar_arc_directions",
    "calculate_progressed_julian_day",
    "jd_to_iso_timestamp",
    "SECONDARY_RATE",
    "TERTIARY_RATE",
    "CONVERSE_RATE",
]
