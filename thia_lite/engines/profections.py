#!/usr/bin/env python3
"""
Annual Profections Calculator for THIA-Libre
=============================================

Implements annual, monthly, and daily profections for predictive astrology.

Profections:
- Annual: One sign per year, starting from Ascendant
- Monthly: One sign per month within the annual profection
- Daily: One sign per day within the monthly profection
- Time Lord: Planet ruling the profected sign

Integration with Time Lords:
- Combines with Firdar for dual time-lord analysis
- Combines with Zodiacal Releasing for triple timing confirmation

Author: Thia (OpenClaw Agent)
Date: 2026-02-26
"""

import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import swisseph as swe

# Primary Directions integration
from .primary_directions import calculate_primary_directions

# Planet IDs for Swiss Ephemeris
PLANETS = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO,
}


# =============================================================================
# CONSTANTS
# =============================================================================

# Zodiac signs in order (traditional names)
ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

# Traditional sign rulers
SIGN_RULERS: Dict[str, str] = {
    "Aries": "MARS",
    "Taurus": "VENUS",
    "Gemini": "MERCURY",
    "Cancer": "MOON",
    "Leo": "SUN",
    "Virgo": "MERCURY",
    "Libra": "VENUS",
    "Scorpio": "MARS",
    "Sagittarius": "JUPITER",
    "Capricorn": "SATURN",
    "Aquarius": "SATURN",
    "Pisces": "JUPITER",
}

# Planet meanings for interpretation
PLANET_MEANINGS: Dict[str, str] = {
    "SUN": "Identity, vitality, authority, leadership, father figures",
    "MOON": "Emotions, home, mother, public, fluctuation, nurture",
    "MERCURY": "Communication, learning, travel, commerce, siblings, intellect",
    "VENUS": "Love, beauty, pleasure, art, relationships, values",
    "MARS": "Action, conflict, passion, courage, competition, drive",
    "JUPITER": "Growth, expansion, wisdom, fortune, philosophy, benevolence",
    "SATURN": "Structure, discipline, limitation, responsibility, maturity, karma",
}

# House themes for interpretation
HOUSE_THEMES: Dict[int, str] = {
    1: "Identity, physical body, self-expression, new beginnings",
    2: "Money, possessions, values, self-worth, material security",
    3: "Communication, siblings, short trips, learning, immediate environment",
    4: "Home, family, roots, foundation, private life, mother",
    5: "Creativity, romance, children, pleasure, self-expression",
    6: "Work, health, service, daily routines, pets, responsibility",
    7: "Partnerships, marriage, close relationships, open enemies, contracts",
    8: "Death, transformation, intimacy, shared resources, occult",
    9: "Higher education, travel, philosophy, religion, foreign lands",
    10: "Career, reputation, public image, authority, achievements",
    11: "Friends, groups, hopes, wishes, social networks, community",
    12: "Subconscious, secrets, solitude, self-undo, spiritual growth",
}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def normalize_longitude(lon: float) -> float:
    """Normalize longitude to 0-360 degree range."""
    result = lon % 360.0
    return result if result >= 0 else result + 360.0


def get_sign_from_degree(degree: float) -> Tuple[str, int]:
    """Get zodiac sign name and number from degree.

    Args:
        degree: Longitude (0-360)

    Returns:
        Tuple of (sign_name, sign_number) where sign_number is 0-11
    """
    degree = normalize_longitude(degree)
    sign_number = int(degree // 30) % 12
    sign_name = ZODIAC_SIGNS[sign_number]
    return sign_name, sign_number


def get_degree_in_sign(degree: float) -> float:
    """Get degree within sign (0-30)."""
    degree = normalize_longitude(degree)
    return degree % 30


def jd_to_iso(jd: float) -> str:
    """Convert Julian Day to ISO 8601 timestamp."""
    year, month, day, hour = swe.revjul(jd)
    hour_int = int(hour)
    minute = int((hour - hour_int) * 60)
    second = int(((hour - hour_int) * 60 - minute) * 60)
    return f"{year:04d}-{month:02d}-{day:02d}T{hour_int:02d}:{minute:02d}:{second:02d}Z"


def calculate_age_decimal(birth_dt: datetime, target_dt: datetime) -> float:
    """Calculate age in decimal years."""
    delta = target_dt - birth_dt
    age_years = delta.total_seconds() / (365.25 * 24 * 3600)
    return age_years


def datetime_to_jd(dt: datetime) -> float:
    """Convert datetime to Julian Day."""
    hour = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
    return swe.julday(dt.year, dt.month, dt.day, hour)


def parse_timestamp(timestamp: str) -> datetime:
    """Parse ISO 8601 timestamp to datetime (naive for internal calculations)."""
    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    # Return naive datetime (strip timezone) for internal calculations
    return dt.replace(tzinfo=None)


# =============================================================================
# PROFECTION CALCULATIONS
# =============================================================================

def get_profected_sign(
    natal_asc_sign_number: int,
    years_elapsed: int
) -> Tuple[str, int, int]:
    """Calculate proflected sign after N years.

    Args:
        natal_asc_sign_number: Natal Ascendant sign (0-11)
        years_elapsed: Years since birth

    Returns:
        Tuple of (sign_name, sign_number, house_number)
    """
    # Profections advance one sign per year
    profected_sign_number = (natal_asc_sign_number + years_elapsed) % 12
    profected_sign = ZODIAC_SIGNS[profected_sign_number]

    # House is 1-indexed (1st house, 2nd house, etc.)
    profected_house = (years_elapsed % 12) + 1

    return profected_sign, profected_sign_number, profected_house


def get_sign_ruler(sign_name: str) -> str:
    """Get traditional planetary ruler of sign."""
    return SIGN_RULERS.get(sign_name, "SUN")


def interpret_time_lord_in_house(planet: str, house: int, profected_sign: str) -> Dict[str, Any]:
    """Generate interpretation for time lord in house.

    Args:
        planet: Time lord planet
        house: Profected house number
        profected_sign: Profected sign name

    Returns:
        Dictionary with interpretation keywords and themes
    """
    planet_meaning = PLANET_MEANINGS.get(planet, "Unknown influence")
    house_theme = HOUSE_THEMES.get(house, "Unknown area of life")

    # Determine dignity
    ruler_of_sign = get_sign_ruler(profected_sign)
    is_domicile = (planet == ruler_of_sign)

    # Generate interpretation
    interpretation = {
        "time_lord": planet,
        "house": house,
        "profected_sign": profected_sign,
        "is_domicile": is_domicile,
        "strength": "strong" if is_domicile else "moderate",
        "keywords": {
            "planet_themes": planet_meaning,
            "house_themes": house_theme,
        },
        "interpretation": f"The year focuses on {house_theme.lower()}, activated by {planet.lower()} themes ({planet_meaning.lower()})."
    }

    if is_domicile:
        interpretation["interpretation"] += f" {planet} is dignified as ruler of {profected_sign}, strengthening its influence."

    return interpretation


# =============================================================================
# MAIN PROFECTIONS FUNCTION
# =============================================================================

def calculate_profections(
    natal_timestamp: str,
    natal_latitude: float,
    natal_longitude: float,
    target_timestamp: Optional[str] = None,
    profection_type: str = "annual",
    house_system: str = "P",
    include_interpretation: bool = True,
) -> Dict[str, Any]:
    """Calculate profections for a target date.

    Args:
        natal_timestamp: Birth timestamp (ISO 8601)
        natal_latitude: Birth latitude
        natal_longitude: Birth longitude
        target_timestamp: Date to calculate for (default: now)
        profection_type: Type of profection (annual/monthly/daily)
        house_system: House system for natal chart
        include_interpretation: Whether to include interpretive text

    Returns:
        Dictionary with complete profection data
    """
    # Parse timestamps
    natal_dt = parse_timestamp(natal_timestamp)
    natal_jd = datetime_to_jd(natal_dt)

    if target_timestamp is None:
        target_dt = datetime.utcnow()
        target_timestamp = target_dt.isoformat() + "Z"
    else:
        target_dt = parse_timestamp(target_timestamp)

    target_jd = datetime_to_jd(target_dt)

    # Calculate natal chart to get Ascendant
    hsys = house_system.encode("ascii") if house_system else b"P"
    cusps, ascmc = swe.houses_ex(natal_jd, natal_latitude, natal_longitude, hsys)

    natal_asc = ascmc[0]  # Ascendant is first element
    natal_asc_sign, natal_asc_sign_num = get_sign_from_degree(natal_asc)
    natal_asc_degree = get_degree_in_sign(natal_asc)

    # Calculate age and profection year
    age_at_target = calculate_age_decimal(natal_dt, target_dt)
    age_int = int(age_at_target)
    profection_year = age_int % 12  # 0-11
    cycle_number = age_int // 12

    # Calculate annual profection
    annual_sign, annual_sign_num, annual_house = get_profected_sign(
        natal_asc_sign_num, age_int
    )

    # Calculate profected Ascendant degree
    profected_degree = (annual_sign_num * 30) + natal_asc_degree

    # Get time lord
    time_lord = get_sign_ruler(annual_sign)

    # Calculate sign entry/exit dates
    # This year's profection starts on the most recent birthday
    birth_month = natal_dt.month
    birth_day = natal_dt.day
    birth_hour = natal_dt.hour
    birth_minute = natal_dt.minute

    # Handle timezone-aware datetimes
    target_tz = target_dt.tzinfo

    # Entry date: most recent birthday
    entry_dt = datetime(
        target_dt.year,
        birth_month,
        birth_day,
        birth_hour,
        birth_minute,
        tzinfo=target_tz,
    )
    if entry_dt > target_dt:
        entry_dt = datetime(
            target_dt.year - 1,
            birth_month,
            birth_day,
            birth_hour,
            birth_minute,
            tzinfo=target_tz,
        )

    # Exit date: next birthday
    exit_dt = datetime(
        entry_dt.year + 1,
        birth_month,
        birth_day,
        birth_hour,
        birth_minute,
    )

    sign_entry_date = entry_dt.isoformat() + "Z"
    sign_exit_date = exit_dt.isoformat() + "Z"

    # Calculate sub-profections
    monthly_sign = None
    monthly_house = None
    monthly_time_lord = None
    daily_sign = None
    daily_house = None
    daily_time_lord = None

    if profection_type in ["monthly", "daily"]:
        # Calculate months since entry
        months_since_entry = (
            (target_dt.year - entry_dt.year) * 12
            + target_dt.month
            - entry_dt.month
        )

        monthly_sign, monthly_sign_num, monthly_house = get_profected_sign(
            annual_sign_num, months_since_entry
        )
        monthly_time_lord = get_sign_ruler(monthly_sign)

        if profection_type == "daily":
            # Daily profection
            days_since_month_start = (target_dt - target_dt.replace(day=1)).days
            daily_sign, daily_sign_num, daily_house = get_profected_sign(
                monthly_sign_num, days_since_month_start
            )
            daily_time_lord = get_sign_ruler(daily_sign)

    # Build interpretation
    interpretation = None
    if include_interpretation:
        interpretation = interpret_time_lord_in_house(
            time_lord, annual_house, annual_sign
        )

    return {
        "profection_type": profection_type,
        "natal": {
            "timestamp": natal_timestamp,
            "ascendant": round(natal_asc, 6),
            "ascendant_sign": natal_asc_sign,
            "ascendant_degree": round(natal_asc_degree, 4),
        },
        "target": {
            "timestamp": target_timestamp,
            "age_at_target": round(age_at_target, 2),
        },
        "annual_profection": {
            "sign": annual_sign,
            "sign_number": annual_sign_num,
            "house": annual_house,
            "profected_degree": round(profected_degree, 6),
            "time_lord": time_lord,
            "profection_year": profection_year,  # 0-11
            "cycle_number": cycle_number,  # Which 12-year cycle
            "sign_entry_date": sign_entry_date,
            "sign_exit_date": sign_exit_date,
        },
        "monthly_profection": {
            "sign": monthly_sign,
            "house": monthly_house,
            "time_lord": monthly_time_lord,
        } if monthly_sign else None,
        "daily_profection": {
            "sign": daily_sign,
            "house": daily_house,
            "time_lord": daily_time_lord,
        } if daily_sign else None,
        "interpretation": interpretation,
    }


def calculate_profection_timeline(
    natal_timestamp: str,
    natal_latitude: float,
    natal_longitude: float,
    max_years: int = 84,
    house_system: str = "P",
) -> Dict[str, Any]:
    """Calculate profection timeline for entire life.

    Args:
        natal_timestamp: Birth timestamp
        natal_latitude: Birth latitude
        natal_longitude: Birth longitude
        max_years: Maximum years to calculate (default: 84)
        house_system: House system for natal chart

    Returns:
        Dictionary with timeline of all profection periods
    """
    if max_years > 150:
        raise ValueError("Maximum years cannot exceed 150")

    # Parse natal data
    natal_dt = parse_timestamp(natal_timestamp)
    natal_jd = datetime_to_jd(natal_dt)

    # Calculate natal Ascendant
    hsys = house_system.encode("ascii") if house_system else b"P"
    cusps, ascmc = swe.houses_ex(natal_jd, natal_latitude, natal_longitude, hsys)
    natal_asc = ascmc[0]
    natal_asc_sign, natal_asc_sign_num = get_sign_from_degree(natal_asc)

    # Calculate current age
    now = datetime.now()
    current_age = calculate_age_decimal(natal_dt, now)
    current_year = int(current_age)

    # Generate timeline
    periods = []
    for year in range(max_years):
        sign, sign_num, house = get_profected_sign(natal_asc_sign_num, year)
        time_lord = get_sign_ruler(sign)

        # Calculate period dates
        start_dt = natal_dt + timedelta(days=365.25 * year)
        end_dt = natal_dt + timedelta(days=365.25 * (year + 1))

        period = {
            "year_number": year,
            "age_range": f"{year}-{year + 1}",
            "profected_sign": sign,
            "profected_house": house,
            "time_lord": time_lord,
            "time_lord_meaning": PLANET_MEANINGS.get(time_lord, ""),
            "house_theme": HOUSE_THEMES.get(house, ""),
            "start_date": start_dt.isoformat() + "Z",
            "end_date": end_dt.isoformat() + "Z",
            "is_current": (year == current_year),
        }
        periods.append(period)

    return {
        "natal_timestamp": natal_timestamp,
        "natal_ascendant_sign": natal_asc_sign,
        "current_age": round(current_age, 2),
        "current_year": current_year,
        "periods": periods,
    }


# =============================================================================
# INTEGRATION WITH TIME LORDS
# =============================================================================

def calculate_unified_timing(
    natal_timestamp: str,
    natal_latitude: float,
    natal_longitude: float,
    target_timestamp: Optional[str] = None,
    include_firdar: bool = True,
    include_zr: bool = True,
) -> Dict[str, Any]:
    """Calculate unified timing combining profections with time lords.

    Args:
        natal_timestamp: Birth timestamp
        natal_latitude: Birth latitude
        natal_longitude: Birth longitude
        target_timestamp: Target date (default: now)
        include_firdar: Include Firdar time lords
        include_zr: Include Zodiacal Releasing

    Returns:
        Dictionary with unified timing analysis
    """
    # Calculate profections
    prof = calculate_profections(
        natal_timestamp=natal_timestamp,
        natal_latitude=natal_latitude,
        natal_longitude=natal_longitude,
        target_timestamp=target_timestamp,
        profection_type="annual",
        include_interpretation=True,
    )

    result = {
        "target_timestamp": target_timestamp or datetime.now().isoformat() + "Z",
        "profections": prof,
        "time_lords_synthesis": {},
    }

    # Get natal data for other calculations
    natal_dt = parse_timestamp(natal_timestamp)
    natal_jd = datetime_to_jd(natal_dt)

    if target_timestamp is None:
        target_dt = datetime.now()
        target_timestamp = target_dt.isoformat() + "Z"
    else:
        target_dt = parse_timestamp(target_timestamp)
    target_jd = datetime_to_jd(target_dt)

    # Calculate sun/moon for Firdar and ZR
    sun_pos = swe.calc_ut(natal_jd, swe.SUN)[0]
    moon_pos = swe.calc_ut(natal_jd, swe.MOON)[0]
    sun_lon = sun_pos[0]
    moon_lon = moon_pos[0]

    # Get Ascendant
    hsys = b"P"
    cusps, ascmc = swe.houses_ex(natal_jd, natal_latitude, natal_longitude, hsys)
    asc_lon = ascmc[0]

    # Determine day/night chart: Sun above horizon
    # azalt takes: (tjdut, flag, geopos, atpress, attemp, xin)
    # flag = swe.EQU2HOR for equatorial input (RA/Dec)
    # xin is (RA, Dec, distance) - we'll use 1.0 for distance
    res = swe.azalt(target_jd, swe.EQU2HOR, (natal_longitude, natal_latitude, 0.0), 0.0, 0.0, [sun_pos[0], sun_pos[1], 1.0])
    sun_alt = res[1] # azimuth, true_altitude, apparent_altitude
    is_day = sun_alt > 0

    # Collect all timing indicators
    time_lords = []

    # 1. Annual Profection Time Lord
    annual_lord = prof["annual_profection"]["time_lord"]
    annual_house = prof["annual_profection"]["house"]
    time_lords.append({
        "system": "Annual Profections",
        "lord": annual_lord,
        "context": f"House {annual_house}",
        "strength": "primary",
    })

    # 2. Firdar Major Period
    if include_firdar:
        from time_lords import calculate_firdar_periods

        firdar = calculate_firdar_periods(
            is_day_chart=is_day,
            birth_date=natal_dt.strftime("%Y-%m-%d"),
            birth_time=natal_dt.strftime("%H:%M"),
            target_date=target_dt.strftime("%Y-%m-%d"),
            natal_jd=natal_jd,
            include_sub_periods=False,
        )

        firdar_lord = firdar["current_major_period"]["planet"]
        time_lords.append({
            "system": "Firdar (Persian)",
            "lord": firdar_lord,
            "context": f"Major period, age {round(firdar['age_at_target'], 1)}",
            "strength": "major",
        })

        result["firdar"] = firdar

    # 3. Zodiacal Releasing L1
    if include_zr:
        from time_lords import calculate_lot_of_fortune, calculate_zodiacal_releasing_periods

        lot_fortune_lon = calculate_lot_of_fortune(moon_lon, sun_lon, asc_lon, is_day)
        lot_fortune_sign, _ = get_sign_from_degree(lot_fortune_lon)

        zr = calculate_zodiacal_releasing_periods(
            lot_sign=lot_fortune_sign,
            natal_jd=natal_jd,
            current_jd=target_jd,
            calculate_l2=False,
        )

        if zr["current_l1_period"]:
            zr_lord = zr["current_l1_period"]["ruler"]
            time_lords.append({
                "system": "Zodiacal Releasing (L1)",
                "lord": zr_lord,
                "context": f"Sign of {zr['current_l1_period']['sign']}",
                "strength": "primary",
            })

        result["zodiacal_releasing"] = zr

    # 4. Primary Directions (Active)
    # Calculate current age to focus primary directions search
    age_years = calculate_age_decimal(natal_dt, target_dt)
    
    # Primary directions are roughly 1 degree per year.
    # We set max_arc slightly above current age and filter for active ones.
    target_arc = age_years
    
    # Convert natal_jd and natal positions for PD calculator
    def _all_positions(jd):
        pos = {}
        for name, pid in PLANETS.items():
            vals = swe.calc_ut(jd, pid)[0]
            pos[name] = {"longitude": vals[0], "latitude": vals[1]}
        return pos

    pd_result = calculate_primary_directions(
        natal_positions=_all_positions(natal_jd),
        julian_day=natal_jd,
        latitude=natal_latitude,
        longitude=natal_longitude,
        target_date=target_dt.strftime("%Y-%m-%d"),
        max_arc=target_arc + 1.2 # Buffer for tight aspects
    )

    active_directions = []
    # Only keep directions active within +/- 1 year
    for direction in pd_result.get("directions", []):
        arc_deg = direction["arc"]["arc_degrees"]
        if abs(arc_deg - target_arc) <= 1.0:
            active_directions.append(direction)
            
            # Add to time lords for synthesis text
            time_lords.append({
                "system": f"Primary Direction ({direction['direction_type'].capitalize()})",
                "lord": direction["promissor"],
                "context": f"{direction['aspect'].capitalize()} to natal {direction['significator']}",
                "strength": "secondary",
            })

    result["primary_directions"] = {
        "active_directions": active_directions,
        "count": len(active_directions)
    }

    # Synthesis - find agreements
    lord_counts = {}
    for tl in time_lords:
        lord = tl["lord"]
        lord_counts[lord] = lord_counts.get(lord, 0) + 1

    # Find strongest planets (mentioned in 2+ systems)
    strong_lords = [lord for lord, count in lord_counts.items() if count >= 2]

    result["time_lords_synthesis"] = {
        "all_time_lords": time_lords,
        "planet_counts": lord_counts,
        "strongest_planets": strong_lords,
        "synthesis": _generate_synthesis_text(time_lords, strong_lords),
    }

    return result


def _generate_synthesis_text(time_lords: List[Dict], strong_lords: List[str]) -> str:
    """Generate interpretive synthesis text for timing analysis."""
    if not time_lords:
        return "No timing data available."

    lines = []
    lines.append("=== UNIFIED TIMING ANALYSIS ===")

    for tl in time_lords:
        lines.append(f"• {tl['system']}: {tl['lord']} ({tl['context']})")

    if strong_lords:
        lines.append(f"\n**Strongest influences:** {', '.join(strong_lords)}")
        lines.append(f"Themes of {strong_lords[0]} dominate this period through multiple timing systems.")
    else:
        lines.append("\n**No strong agreements** - Mixed influences suggest a transitional period.")

    return "\n".join(lines)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "calculate_profections",
    "calculate_profection_timeline",
    "calculate_unified_timing",
    "get_profected_sign",
    "get_sign_ruler",
    "get_sign_from_degree",
    "calculate_age_decimal",
    "interpret_time_lord_in_house",
    "SIGN_RULERS",
    "PLANET_MEANINGS",
    "HOUSE_THEMES",
]
