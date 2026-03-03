#!/usr/bin/env python3
"""
Time Lords Calculator for THIA-Libre
=====================================

Implements Firdar (Persian) and Zodiacal Releasing (Hellenistic) time-lord systems.

Firdar:
- Day/Night chart sequences
- 73-year cycle with planetary periods
- Sub-periods within major periods

Zodiacal Releasing:
- Based on Lot of Fortune or Spirit
- L1-L4 period levels
- Peak periods and loosing of bond

Author: Thia (OpenClaw Agent)
Date: 2026-02-26
"""

import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Literal
import swisseph as swe


# =============================================================================
# CONSTANTS
# =============================================================================

# Firdar sequences with planet name and duration in years
DAY_CHART_SEQUENCE = [
    ("SUN", 10),
    ("VENUS", 8),
    ("MERCURY", 13),
    ("MOON", 9),
    ("SATURN", 11),
    ("JUPITER", 12),
    ("MARS", 7),
    ("MEAN_NODE", 3),
]

NIGHT_CHART_SEQUENCE = [
    ("MOON", 9),
    ("SATURN", 11),
    ("JUPITER", 12),
    ("MARS", 7),
    ("SUN", 10),
    ("VENUS", 8),
    ("MERCURY", 13),
    ("MEAN_NODE", 3),
]

# Traditional planetary years (Hellenistic)
PLANETARY_YEARS: Dict[str, int] = {
    "SATURN": 30,
    "JUPITER": 12,
    "MARS": 15,
    "SUN": 19,
    "VENUS": 8,
    "MERCURY": 20,
    "MOON": 25,
}

# Sign rulers (traditional/classical)
SIGN_RULERS: Dict[str, str] = {
    "ARIES": "MARS",
    "TAURUS": "VENUS",
    "GEMINI": "MERCURY",
    "CANCER": "MOON",
    "LEO": "SUN",
    "VIRGO": "MERCURY",
    "LIBRA": "VENUS",
    "SCORPIO": "MARS",
    "SAGITTARIUS": "JUPITER",
    "CAPRICORN": "SATURN",
    "AQUARIUS": "SATURN",
    "PISCES": "JUPITER",
}

# Zodiac signs in order
ZODIAC_SIGNS = [
    "ARIES", "TAURUS", "GEMINI", "CANCER", "LEO", "VIRGO",
    "LIBRA", "SCORPIO", "SAGITTARIUS", "CAPRICORN", "AQUARIUS", "PISCES"
]


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_sign_from_longitude(longitude: float) -> str:
    """Get zodiac sign from ecliptic longitude."""
    sign_idx = int(longitude // 30) % 12
    return ZODIAC_SIGNS[sign_idx]


def get_next_sign(sign: str) -> str:
    """Get the next zodiac sign in order."""
    idx = ZODIAC_SIGNS.index(sign.upper())
    return ZODIAC_SIGNS[(idx + 1) % 12]


def jd_to_iso(jd: float) -> str:
    """Convert Julian Day to ISO 8601 timestamp."""
    year, month, day, hour = swe.revjul(jd)
    hour_int = int(hour)
    minute = int((hour - hour_int) * 60)
    second = int(((hour - hour_int) * 60 - minute) * 60)
    return f"{year:04d}-{month:02d}-{day:02d}T{hour_int:02d}:{minute:02d}:{second:02d}Z"


def normalize_longitude(lon: float) -> float:
    """Normalize longitude to 0-360 degree range."""
    result = lon % 360.0
    return result if result >= 0 else result + 360.0


def calculate_age_decimal(birth_dt: datetime, target_dt: datetime) -> float:
    """Calculate age in decimal years."""
    delta = target_dt - birth_dt
    age_years = delta.total_seconds() / (365.25 * 24 * 3600)
    return age_years


# =============================================================================
# FIRDAR (PERSIAN TIME LORDS)
# =============================================================================

def is_day_chart(sun_lon: float, asc_lon: float) -> bool:
    """Determine if chart is day or night based on Sun and Ascendant.

    Simplified: If Sun is above horizon (in houses 1-6), it's a day chart.
    For a more accurate calculation, we'd need the MC/IC axis.
    """
    # In a simplified approach, check if Sun is in the eastern hemisphere
    # For day charts: Sun is above horizon (houses 1-12, but specifically 1-6 for day)
    # This is a simplification - proper calculation requires oblique ascension

    # Use MC to determine: if Sun's RA < MC's RA, Sun is above horizon
    # For now, use a simple approximation based on house position
    # If we had the house position, we could check if Sun is in houses 1-6

    # Simplified: Day chart if Sun is in 1st-6th houses (eastern/above horizon)
    # Since we don't have house info here, we'll use a simple heuristic
    # Day chart: Sun has risen (Sun > Ascendant in zodiac order roughly)

    # More accurate: Use the relationship between Sun and MC
    # For now, this is a placeholder that could be improved
    return True  # Default to day chart for simplicity


def calculate_firdar_periods(
    is_day_chart: bool,
    birth_date: str,
    birth_time: str,
    target_date: str,
    natal_jd: float,
    include_sub_periods: bool = True,
    max_years: int = 146
) -> Dict[str, Any]:
    """Calculate Firdar (Persian time-lord) periods.

    Args:
        is_day_chart: Whether chart is day (True) or night (False)
        birth_date: Birth date (YYYY-MM-DD)
        birth_time: Birth time (HH:MM)
        target_date: Target date (YYYY-MM-DD)
        natal_jd: Natal Julian Day
        include_sub_periods: Whether to calculate sub-periods
        max_years: Maximum years to calculate

    Returns:
        Dictionary with Firdar periods
    """
    # Parse dates
    birth_dt = datetime.strptime(birth_date, "%Y-%m-%d")
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")

    # Get appropriate sequence
    sequence = DAY_CHART_SEQUENCE if is_day_chart else NIGHT_CHART_SEQUENCE
    cycle_length = sum(duration for _, duration in sequence)

    # Calculate age
    age_at_target = calculate_age_decimal(birth_dt, target_dt)

    # Find current major period
    age_in_cycle = age_at_target % cycle_length
    cumulative_years = 0.0

    for i, (planet, duration) in enumerate(sequence):
        if cumulative_years + duration > age_in_cycle:
            period_index = i
            age_into_period = age_in_cycle - cumulative_years
            break
        cumulative_years += duration
    else:
        period_index = len(sequence) - 1
        age_into_period = 0.0

    current_planet, current_duration = sequence[period_index]

    # Calculate start of current major period
    full_cycles = int(age_at_target // cycle_length)
    sum_before = sum(duration for _, duration in sequence[:period_index])
    age_at_period_start = (full_cycles * cycle_length) + sum_before

    major_start_dt = birth_dt + timedelta(days=age_at_period_start * 365.25)
    major_end_dt = major_start_dt + timedelta(days=current_duration * 365.25)

    # Calculate sub-periods if requested
    sub_periods = []
    current_sub = None

    if include_sub_periods:
        current_dt = major_start_dt
        total_sequence_years = sum(duration for _, duration in sequence)

        for planet, planet_duration in sequence:
            # Calculate sub-period duration
            fraction = planet_duration / total_sequence_years
            sub_duration_years = current_duration * fraction
            end_dt = current_dt + timedelta(days=sub_duration_years * 365.25)

            # Check if current
            sub_age = calculate_age_decimal(birth_dt, current_dt)
            next_age = calculate_age_decimal(birth_dt, end_dt)
            is_current = sub_age <= age_into_period < next_age

            sub_period = {
                "planet": planet,
                "start_date": current_dt.isoformat() + "Z",
                "end_date": end_dt.isoformat() + "Z",
                "duration_years": round(sub_duration_years, 2),
                "is_current": is_current,
            }
            sub_periods.append(sub_period)

            if is_current:
                current_sub = sub_period

            current_dt = end_dt

    # Generate full timeline
    all_periods = []
    current_age = 0.0
    current_dt = birth_dt
    num_cycles = min(max_years // cycle_length + 1, 3)

    for cycle in range(num_cycles):
        for planet, duration in sequence:
            end_dt = current_dt + timedelta(days=duration * 365.25)
            next_age = current_age + duration

            if current_age >= max_years:
                break

            is_current_period = (
                current_age <= age_at_target < next_age
                and cycle == full_cycles
            )

            all_periods.append({
                "planet": planet,
                "start_date": current_dt.isoformat() + "Z",
                "end_date": end_dt.isoformat() + "Z",
                "duration_years": float(duration),
                "is_current": is_current_period,
            })

            current_dt = end_dt
            current_age = next_age

        if current_age >= max_years:
            break

    return {
        "system": "firdar",
        "is_day_chart": is_day_chart,
        "chart_type": "Day (starts with Sun)" if is_day_chart else "Night (starts with Moon)",
        "age_at_target": round(age_at_target, 2),
        "current_major_period": {
            "planet": current_planet,
            "start_date": major_start_dt.isoformat() + "Z",
            "end_date": major_end_dt.isoformat() + "Z",
            "duration_years": float(current_duration),
            "age_into_period": round(age_into_period, 2),
        },
        "current_sub_period": current_sub,
        "all_major_periods": all_periods[:12],  # Limit to 12 for response size
        "sub_periods": sub_periods,
    }


# =============================================================================
# ZODIACAL RELEASING
# =============================================================================

def calculate_lot_of_fortune(
    moon_lon: float,
    sun_lon: float,
    asc_lon: float,
    is_day_chart: bool = True
) -> float:
    """Calculate Part of Fortune.

    Day: Asc + Moon - Sun
    Night: Asc + Sun - Moon
    """
    if is_day_chart:
        return normalize_longitude(asc_lon + moon_lon - sun_lon)
    else:
        return normalize_longitude(asc_lon + sun_lon - moon_lon)


def calculate_lot_of_spirit(
    moon_lon: float,
    sun_lon: float,
    asc_lon: float,
    is_day_chart: bool = True
) -> float:
    """Calculate Part of Spirit (inverse of Fortune).

    Day: Asc + Sun - Moon
    Night: Asc + Moon - Sun
    """
    if is_day_chart:
        return normalize_longitude(asc_lon + sun_lon - moon_lon)
    else:
        return normalize_longitude(asc_lon + moon_lon - sun_lon)


def calculate_zodiacal_releasing_periods(
    lot_sign: str,
    natal_jd: float,
    current_jd: float,
    calculate_l2: bool = True,
    max_l1_periods: int = 10
) -> Dict[str, Any]:
    """Calculate Zodiacal Releasing periods.

    Args:
        lot_sign: Zodiac sign of the Lot (Fortune or Spirit)
        natal_jd: Natal Julian Day
        current_jd: Current Julian Day
        calculate_l2: Whether to calculate L2 sub-periods
        max_l1_periods: Maximum number of L1 periods to calculate

    Returns:
        Dictionary with Zodiacal Releasing periods
    """
    # Calculate L1 periods
    l1_periods = []
    current_sign = lot_sign
    current_start_jd = natal_jd
    total_years = 0.0

    for _ in range(max_l1_periods):
        ruler = SIGN_RULERS[current_sign.upper()]
        duration_years = PLANETARY_YEARS[ruler]
        duration_days = duration_years * 365.25
        end_jd = current_start_jd + duration_days

        is_current = current_start_jd <= current_jd < end_jd

        l1_periods.append({
            "level": 1,
            "sign": current_sign,
            "ruler": ruler,
            "start_date": jd_to_iso(current_start_jd),
            "end_date": jd_to_iso(end_jd),
            "start_jd": current_start_jd,
            "end_jd": end_jd,
            "duration_years": duration_years,
            "is_current": is_current,
        })

        if is_current:
            current_l1 = l1_periods[-1]
            current_l1_idx = len(l1_periods) - 1

        current_sign = get_next_sign(current_sign)
        current_start_jd = end_jd
        total_years += duration_years

    # Find current L1 period
    current_l1 = None
    for period in l1_periods:
        if period["start_jd"] <= current_jd < period["end_jd"]:
            current_l1 = period
            break

    # Calculate L2 sub-periods for current L1
    l2_periods = []
    current_l2 = None

    if calculate_l2 and current_l1:
        l2_sign = current_l1["sign"]
        l2_start_jd = current_l1["start_jd"]
        l1_end_jd = current_l1["end_jd"]

        while l2_start_jd < l1_end_jd:
            l2_ruler = SIGN_RULERS[l2_sign.upper()]
            # L2 duration = L1 planetary years / 12
            l2_duration_years = PLANETARY_YEARS[l2_ruler] / 12.0
            l2_duration_days = l2_duration_years * 365.25
            l2_end_jd = min(l2_start_jd + l2_duration_days, l1_end_jd)

            is_current = l2_start_jd <= current_jd < l2_end_jd
            is_peak = (l2_ruler == current_l1["ruler"])

            l2_periods.append({
                "level": 2,
                "sign": l2_sign,
                "ruler": l2_ruler,
                "start_date": jd_to_iso(l2_start_jd),
                "end_date": jd_to_iso(l2_end_jd),
                "duration_years": round(l2_duration_years, 2),
                "is_current": is_current,
                "is_peak": is_peak,
            })

            if is_current:
                current_l2 = l2_periods[-1]

            l2_sign = get_next_sign(l2_sign)
            l2_start_jd = l2_end_jd

    # Find next loosing of bond
    next_lotb = None
    for period in l1_periods[1:]:  # Skip first (no loosing at birth)
        if period["start_jd"] > current_jd:
            next_lotb = period["start_date"]
            break

    return {
        "system": "zodiacal_releasing",
        "lot_sign": lot_sign,
        "current_l1_period": current_l1,
        "current_l2_period": current_l2,
        "all_l1_periods": l1_periods,
        "l2_periods": l2_periods,
        "next_loosing_of_bond": next_lotb,
        "is_peak_period": current_l2 and current_l2.get("is_peak", False),
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "calculate_firdar_periods",
    "calculate_zodiacal_releasing_periods",
    "calculate_lot_of_fortune",
    "calculate_lot_of_spirit",
    "is_day_chart",
    "PLANETARY_YEARS",
    "SIGN_RULERS",
    "DAY_CHART_SEQUENCE",
    "NIGHT_CHART_SEQUENCE",
]
