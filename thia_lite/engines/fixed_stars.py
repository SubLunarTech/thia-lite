#!/usr/bin/env python3
"""
Fixed Stars Calculator for THIA-Libre
======================================

Implements fixed star calculations including:
- Star catalog with traditional astrological meanings
- Star positions and conjunctions with planets
- Paranatellonta (rising/culminating times)
- Star interpretations

Traditional Fixed Stars (15 Major Stars):
The four Royal Stars: Aldebaran, Regulus, Antares, Fomalhaut
Plus 11 other major stars: Sirius, Arcturus, Vega, Spica, Canopus,
Capella, Pollux, Betelgeuse, Rigel, Procyon, Deneb

Author: Thia (OpenClaw Agent)
Date: 2026-02-26
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import swisseph as swe


# =============================================================================
# CONSTANTS
# =============================================================================

# Zodiac signs in order
ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

# Planet IDs for Swiss Ephemeris
PLANET_IDS = {
    "sun": swe.SUN,
    "moon": swe.MOON,
    "mercury": swe.MERCURY,
    "venus": swe.VENUS,
    "mars": swe.MARS,
    "jupiter": swe.JUPITER,
    "saturn": swe.SATURN,
    "uranus": swe.URANUS,
    "neptune": swe.NEPTUNE,
    "pluto": swe.PLUTO,
    "north_node": swe.MEAN_NODE,
    "south_node": swe.MEAN_APOG,
}


# =============================================================================
# FIXED STAR CATALOG
# =============================================================================

@dataclass
class FixedStar:
    """Represents a fixed star with astrological properties."""
    id: str
    name: str
    bayer_designation: Optional[str] = None
    longitude: float = 0.0  # Ecliptic longitude (J2000)
    latitude: float = 0.0   # Ecliptic latitude
    magnitude: float = 0.0  # Visual magnitude
    constellation: str = ""
    nature: List[str] = field(default_factory=list)  # Mars/Jupiter, Venus/Mercury, etc.
    meaning: str = ""  # Traditional astrological meaning
    orb_degrees: float = 1.0  # Default orb for conjunctions
    keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "bayer_designation": self.bayer_designation,
            "longitude": self.longitude,
            "latitude": self.latitude,
            "magnitude": self.magnitude,
            "constellation": self.constellation,
            "nature": self.nature,
            "meaning": self.meaning,
            "orb_degrees": self.orb_degrees,
            "keywords": self.keywords,
        }


# Major fixed stars with traditional meanings
FIXED_STAR_CATALOG: List[FixedStar] = [
    # === THE FOUR ROYAL STARS (Watchers of the Four Directions) ===
    FixedStar(
        id="aldebaran",
        name="Aldebaran",
        bayer_designation="Alpha Tauri",
        longitude=68.98,
        latitude=-5.39,
        magnitude=0.85,
        constellation="Taurus",
        nature=["Mars", "Venus"],
        meaning="Eye of the Bull. One of the four Royal Stars (Watcher of the East). Honors, intelligence, eloquence, firmness, integrity. When prominent and well-aspected: success, courage, wealth. When afflicted: violence, recklessness, danger from weapons.",
        keywords=["honor", "courage", "wealth", "integrity", "military", "danger", "violence"],
        orb_degrees=3.0,
    ),
    FixedStar(
        id="regulus",
        name="Regulus",
        bayer_designation="Alpha Leonis",
        longitude=151.83,
        latitude=0.47,
        magnitude=1.40,
        constellation="Leo",
        nature=["Mars", "Jupiter"],
        meaning="Heart of the Lion. One of the four Royal Stars (Watcher of the North). Royal power, military honor, wealth, glory, fame. When prominent: high command, leadership, success. When afflicted: downfall, violence, disaster, temporary defeat.",
        keywords=["royalty", "fame", "honor", "leadership", "military", "command", "downfall"],
        orb_degrees=3.0,
    ),
    FixedStar(
        id="antares",
        name="Antares",
        bayer_designation="Alpha Scorpii",
        longitude=247.56,
        latitude=-4.40,
        magnitude=1.06,
        constellation="Scorpius",
        nature=["Mars", "Jupiter"],
        meaning="Heart of the Scorpion. One of the four Royal Stars (Watcher of the West). Martial nature, destructiveness, malevolence, jealousy. When prominent: military success, occult power, surgeon. When afflicted: danger of death, violence, stabbing, eye problems.",
        keywords=["war", "death", "occult", "surgeon", "violence", "jealousy", "danger"],
        orb_degrees=3.0,
    ),
    FixedStar(
        id="fomalhaut",
        name="Fomalhaut",
        bayer_designation="Alpha Piscis Austrini",
        longitude=353.23,
        latitude=-5.63,
        magnitude=1.16,
        constellation="Piscis Austrinus",
        nature=["Venus", "Mercury"],
        meaning=" Mouth of the Fish. One of the four Royal Stars (Watcher of the South). Poetic, artistic, religious, mystical. When prominent: psychic ability, artistic talent, spiritual devotion. When afflicted: melancholy, depression, scandals, misfortune through water.",
        keywords=["psychic", "artistic", "spiritual", "mystical", "melancholy", "water", "scandal"],
        orb_degrees=3.0,
    ),

    # === OTHER MAJOR STARS ===
    FixedStar(
        id="sirius",
        name="Sirius",
        bayer_designation="Alpha Canis Majoris",
        longitude=258.32,
        latitude=-39.75,
        magnitude=-1.46,
        constellation="Canis Major",
        nature=["Jupiter", "Mars"],
        meaning="The Dog Star. Brightest star in the sky. Honor, fame, wealth, ardor, devotion. When prominent: high office, guardianship, sacred writing. When afflicted: scandal, violence, sudden death.",
        keywords=["fame", "honor", "wealth", "devotion", "guardian", "violence", "scandal"],
        orb_degrees=3.0,
    ),
    FixedStar(
        id="arcturus",
        name="Arcturus",
        bayer_designation="Alpha Bootis",
        longitude=145.60,
        latitude=19.27,
        magnitude=-0.05,
        constellation="Bootes",
        nature=["Mars", "Jupiter"],
        meaning="Bear Guard. Prosperity, fortune, popularity, guardian of people. When prominent: wealth through shipping, exploration, honors. When afflicted: changeable, despondency, selfishness.",
        keywords=["wealth", "fortune", "popularity", "exploration", "guardian", "changeable"],
        orb_degrees=2.5,
    ),
    FixedStar(
        id="vega",
        name="Vega",
        bayer_designation="Alpha Lyrae",
        longitude=80.76,
        latitude=51.20,
        magnitude=0.03,
        constellation="Lyra",
        nature=["Venus", "Mercury"],
        meaning="The Harp. Poetry, music, magic, artistic ability. When prominent: musical talent, spiritual refinement, charisma. When afflicted: artistic but impractical, scandal through love affairs.",
        keywords=["music", "poetry", "art", "magic", "charisma", "refinement", "scandal"],
        orb_degrees=2.0,
    ),
    FixedStar(
        id="spica",
        name="Spica",
        bayer_designation="Alpha Virginis",
        longitude=204.55,
        latitude=-2.11,
        magnitude=0.97,
        constellation="Virgo",
        nature=["Venus", "Mars"],
        meaning="Ear of Wheat. Gift of brilliance, artistic, scientific, fortunate. One of the most benefic stars. When prominent: success, fame, wealth, occult insight. Very protective and beneficial.",
        keywords=["success", "fame", "wealth", "brilliance", "occult", "benefic", "fortunate"],
        orb_degrees=2.0,
    ),
    FixedStar(
        id="canopus",
        name="Canopus",
        bayer_designation="Alpha Carinae",
        longitude=265.94,
        latitude=-52.70,
        magnitude=-0.74,
        constellation="Carina",
        nature=["Saturn", "Jupiter"],
        meaning="The Helm. Ancient wisdom, leadership, navigation, guidance. When prominent: navigators, explorers, leaders, teachers. When afflicted: religious fanaticism, conservative.",
        keywords=["wisdom", "leadership", "navigation", "exploration", "teaching", "ancient"],
        orb_degrees=2.0,
    ),
    FixedStar(
        id="capella",
        name="Capella",
        bayer_designation="Alpha Aurigae",
        longitude=79.17,
        latitude=45.99,
        magnitude=0.08,
        constellation="Auriga",
        nature=["Mars", "Mercury"],
        meaning="The She-Goat. Honor, wealth, pride, danger from military. When prominent: military success, public office, artistic. When afflicted: broken bones, falls from height.",
        keywords=["honor", "wealth", "military", "artistic", "pride", "danger", "falls"],
        orb_degrees=2.5,
    ),
    FixedStar(
        id="pollux",
        name="Pollux",
        bayer_designation="Beta Geminorum",
        longitude=113.81,
        latitude=28.03,
        magnitude=1.14,
        constellation="Gemini",
        nature=["Saturn", "Mercury"],
        meaning="The Heavenly Twin. Athletic, competitive, success in sports. When prominent: athletic ability, competition, success. When afflicted: danger from violence, wounds.",
        keywords=["athletic", "competition", "sports", "violence", "wounds", "brothers"],
        orb_degrees=2.0,
    ),
    FixedStar(
        id="betelgeuse",
        name="Betelgeuse",
        bayer_designation="Alpha Orionis",
        longitude=88.43,
        latitude=7.41,
        magnitude=0.42,
        constellation="Orion",
        nature=["Mars", "Mercury", "Saturn"],
        meaning="The Shoulder. Military honors, fortune, lasting position. When prominent: martial success, wealth, endurance. When afflicted: violence, accidents, sudden death.",
        keywords=["military", "fortune", "endurance", "violence", "accidents", "sudden"],
        orb_degrees=2.5,
    ),
    FixedStar(
        id="rigel",
        name="Rigel",
        bayer_designation="Beta Orionis",
        longitude=78.63,
        latitude=-8.20,
        magnitude=0.13,
        constellation="Orion",
        nature=["Jupiter", "Saturn"],
        meaning="The Foot. Teaching, philosophy, research, inventor. When prominent: scholarly success, invention, philosophy. When afflicted:boastfulness, wastefulness.",
        keywords=["teaching", "philosophy", "invention", "scholar", "research", "boastful"],
        orb_degrees=2.0,
    ),
    FixedStar(
        id="deneb",
        name="Deneb",
        bayer_designation="Alpha Cygni",
        longitude=310.36,
        latitude=45.28,
        magnitude=1.25,
        constellation="Cygnus",
        nature=["Venus", "Mercury"],
        meaning="The Tail. Artistic, philosophical, visionary. When prominent: artistic ability, spiritual insight, writing. When afflicted: artistic but impractical.",
        keywords=["artistic", "philosophical", "visionary", "spiritual", "writing", "insight"],
        orb_degrees=2.0,
    ),
    FixedStar(
        id="procyon",
        name="Procyon",
        bayer_designation="Alpha Canis Minoris",
        longitude=230.54,
        latitude=-16.54,
        magnitude=0.34,
        constellation="Canis Minor",
        nature=["Mercury", "Mars"],
        meaning="The Little Dog. Activity, sudden gains, guards. When prominent: writers, speakers, business success. When afflicted: danger from water, sudden misfortune.",
        keywords=["activity", "gains", "writing", "speaking", "business", "water", "danger"],
        orb_degrees=2.0,
    ),
]


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


def datetime_to_jd(dt: datetime) -> float:
    """Convert datetime to Julian Day."""
    hour = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
    return swe.julday(dt.year, dt.month, dt.day, hour)


def jd_to_iso(jd: float) -> str:
    """Convert Julian Day to ISO 8601 timestamp."""
    year, month, day, hour = swe.revjul(jd)
    hour_int = int(hour)
    minute = int((hour - hour_int) * 60)
    second = int(((hour - hour_int) * 60 - minute) * 60)
    return f"{year:04d}-{month:02d}-{day:02d}T{hour_int:02d}:{minute:02d}:{second:02d}Z"


def angle_diff(a: float, b: float) -> float:
    """Calculate angular difference between two longitudes (0-180)."""
    diff = abs((a - b + 180) % 360 - 180)
    return diff


# =============================================================================
# FIXED STAR QUERIES
# =============================================================================

def list_fixed_stars(
    constellation: Optional[str] = None,
    magnitude_limit: Optional[float] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """List fixed stars from the catalog.

    Args:
        constellation: Filter by constellation name
        magnitude_limit: Maximum magnitude (brightness) - smaller is brighter
        limit: Maximum number of stars to return

    Returns:
        List of fixed star dictionaries
    """
    results = []
    for star in FIXED_STAR_CATALOG:
        # Filter by constellation
        if constellation and star.constellation.lower() != constellation.lower():
            continue
        # Filter by magnitude
        if magnitude_limit is not None and star.magnitude > magnitude_limit:
            continue
        results.append(star.to_dict())

        if len(results) >= limit:
            break

    return results


def get_fixed_star(star_id: str) -> Optional[Dict[str, Any]]:
    """Get a single fixed star by ID or name.

    Args:
        star_id: Star ID or name (case-insensitive)

    Returns:
        Star dictionary or None if not found
    """
    for star in FIXED_STAR_CATALOG:
        if star.id == star_id.lower() or star.name.lower() == star_id.lower():
            return star.to_dict()
    return None


# =============================================================================
# PLANETARY POSITIONS
# =============================================================================

def calculate_planet_positions(jd: float) -> Dict[str, Dict[str, Any]]:
    """Calculate positions of all planets for a given Julian Day.

    Args:
        jd: Julian Day

    Returns:
        Dictionary mapping planet names to position data
    """
    positions = {}
    for name, pid in PLANET_IDS.items():
        try:
            result = swe.calc_ut(jd, pid)
            lon, lat, _, speed = result[0]
            sign, _ = get_sign_from_degree(lon)

            positions[name] = {
                "longitude": float(lon),
                "latitude": float(lat),
                "speed": float(speed),
                "sign": sign,
                "degree_in_sign": float(lon % 30),
            }
        except Exception:
            continue

    return positions


# =============================================================================
# CONJUNCTION DETECTION
# =============================================================================

def find_star_conjunctions(
    natal_timestamp: str,
    latitude: float,
    longitude: float,
    orb: Optional[float] = None
) -> Dict[str, Any]:
    """Find fixed stars conjunct with natal planets.

    Args:
        natal_timestamp: Birth timestamp (ISO 8601)
        latitude: Birth latitude
        longitude: Birth longitude (not used for star positions but for completeness)
        orb: Custom orb limit (uses star's default orb if None)

    Returns:
        Dictionary with conjunctions found
    """
    # Parse timestamp
    if "T" in natal_timestamp:
        dt = datetime.fromisoformat(natal_timestamp.replace("Z", "+00:00"))
        dt = dt.replace(tzinfo=None)
    else:
        dt = datetime.fromisoformat(natal_timestamp)

    jd = datetime_to_jd(dt)

    # Calculate planet positions
    planet_positions = calculate_planet_positions(jd)

    # Find conjunctions
    conjunctions = []
    for star in FIXED_STAR_CATALOG:
        star_orb = orb if orb is not None else star.orb_degrees

        for planet_name, planet_pos in planet_positions.items():
            # Get actual star position for this JD to account for precession
            try:
                # Use swe.fixstar2_ut for accurate position including precession
                # The star name in Swiss Ephemeris usually follows specific conventions
                # We'll try the common name first
                star_name_swe = star.name
                res = swe.fixstar2_ut(star_name_swe, jd)
                star_lon = res[0][0]
                star_lat = res[0][1]
            except Exception:
                # Fallback to J2000 if lookup fails
                star_lon = star.longitude

            diff = angle_diff(planet_pos["longitude"], star_lon)

            if diff <= star_orb:
                conjunctions.append({
                    "star": {**star.to_dict(), "current_longitude": float(star_lon)},
                    "planet": planet_name,
                    "planet_longitude": planet_pos["longitude"],
                    "planet_sign": planet_pos["sign"],
                    "orb_distance": round(diff, 4),
                    "exact": diff < 0.5,
                    "interpretation": interpret_star_planet_conjunction(star, planet_name),
                })

    return {
        "natal_timestamp": natal_timestamp,
        "julian_day": jd,
        "conjunctions_count": len(conjunctions),
        "conjunctions": conjunctions,
    }


def interpret_star_planet_conjunction(star: FixedStar, planet: str) -> str:
    """Generate interpretation for a star-planet conjunction.

    Args:
        star: FixedStar object
        planet: Planet name

    Returns:
        Interpretive text
    """
    planet_meanings = {
        "sun": "identity, vitality, core self",
        "moon": "emotions, instincts, mother, public",
        "mercury": "mind, communication, learning",
        "venus": "love, values, relationships, beauty",
        "mars": "action, drive, conflict, desire",
        "jupiter": "growth, wisdom, fortune, expansion",
        "saturn": "structure, discipline, limitation, karma",
        "uranus": "innovation, rebellion, sudden change",
        "neptune": "idealism, illusion, spirituality",
        "pluto": "transformation, power, rebirth",
        "north_node": "destiny, soul path, evolution",
        "south_node": "past life, release, karma",
    }

    planet_meaning = planet_meanings.get(planet, "influence")

    return f"{star.name} conjunct {planet.capitalize()} activates {planet_meaning} themes with {star.meaning.lower()[:100]}... Keywords: {', '.join(star.keywords[:5])}"


# =============================================================================
# PARANATELLONTA (Rising/Culminating Times)
# =============================================================================

def calculate_star_parans(
    star_name: str,
    latitude: float,
    longitude: float,
    date: Optional[str] = None
) -> Dict[str, Any]:
    """Calculate paranatellonta (rising/setting/culminating times) for a star.

    Args:
        star_name: Name of the star
        latitude: Observer's latitude
        longitude: Observer's longitude
        date: Date for calculation (ISO 8601), defaults to current date

    Returns:
        Dictionary with paran times
    """
    # Find the star
    star = None
    for s in FIXED_STAR_CATALOG:
        if s.name.lower() == star_name.lower() or s.id == star_name.lower():
            star = s
            break

    if not star:
        return {"error": f"Star '{star_name}' not found in catalog"}

    # Use current date if not provided
    if date:
        if "T" in date:
            dt = datetime.fromisoformat(date.replace("Z", "+00:00"))
            dt = dt.replace(tzinfo=None)
        else:
            dt = datetime.fromisoformat(date)
    else:
        dt = datetime.utcnow()

    # Calculate rising, setting, culmination times
    # This is a simplified calculation using the star's right ascension
    # For precise results, would need to convert star's ecliptic coords to equatorial

    jd_noon = datetime_to_jd(dt.replace(hour=12, minute=0, second=0))

    # Get star's approximate position (simplified - using ecliptic longitude directly)
    # For full accuracy, would convert to RA/Dec and calculate hour angles
    star_lon = star.longitude

    # Estimate local sidereal time at noon
    # This is approximate - full calculation would use more precise formulas
    lst_noon = (jd_noon * 360.98564736629) % 360

    # Approximate culmination (when star crosses meridian)
    # Star culminates when LST equals star's right ascension
    # Using ecliptic longitude as rough proxy for RA
    ha_culmination = (star_lon - lst_noon + 180) % 360 - 180
    culmination_hours = ha_culmination / 15.0  # Convert degrees to hours

    culmination_time = (dt.replace(hour=12, minute=0, second=0) +
                       timedelta(hours=culmination_hours))

    # Rising and setting (very approximate)
    # Would need horizon calculations for accuracy
    rise_hours = culmination_hours - 6  # Roughly 6 hours before culmination
    set_hours = culmination_hours + 6    # Roughly 6 hours after culmination

    rise_time = (dt.replace(hour=12, minute=0, second=0) +
                timedelta(hours=rise_hours))
    set_time = (dt.replace(hour=12, minute=0, second=0) +
               timedelta(hours=set_hours))

    return {
        "star": star.to_dict(),
        "location": {
            "latitude": latitude,
            "longitude": longitude,
        },
        "date": dt.strftime("%Y-%m-%d"),
        "parans": {
            "rising": {
                "time": rise_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "type": "heliacal_rising",
                "note": "Approximate - precise calculation requires horizon math",
            },
            "culmination": {
                "time": culmination_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "type": "upper_culmination",
                "altitude": "highest point in sky",
            },
            "setting": {
                "time": set_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "type": "heliacal_setting",
                "note": "Approximate - precise calculation requires horizon math",
            },
        },
        "interpretation": f"{star.name} ({star.constellation}) - {star.meaning[:150]}...",
    }


# =============================================================================
# STAR PHASE CALCULATIONS
# =============================================================================

def calculate_star_phase(star_id: str, timestamp: str) -> Dict[str, Any]:
    """Calculate the phase and position of a star at a given time.

    Args:
        star_id: Star ID or name
        timestamp: Timestamp for calculation (ISO 8601)

    Returns:
        Dictionary with star position data
    """
    star = None
    for s in FIXED_STAR_CATALOG:
        if s.id == star_id.lower() or s.name.lower() == star_id.lower():
            star = s
            break

    if not star:
        return {"error": f"Star '{star_id}' not found"}

    # Parse timestamp
    if "T" in timestamp:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        dt = dt.replace(tzinfo=None)
    else:
        dt = datetime.fromisoformat(timestamp)

    jd = datetime_to_jd(dt)

    # Get star's sign position
    sign_name, sign_num = get_sign_from_degree(star.longitude)
    degree_in_sign = star.longitude % 30

    return {
        "star": star.to_dict(),
        "timestamp": timestamp,
        "julian_day": jd,
        "position": {
            "ecliptic_longitude": star.longitude,
            "ecliptic_latitude": star.latitude,
            "sign": sign_name,
            "sign_number": sign_num,
            "degree_in_sign": round(degree_in_sign, 4),
            "formatted_position": f"{sign_name} {degree_in_sign:.2f}°",
        },
        "visibility": {
            "magnitude": star.magnitude,
            "brightness_class": "very bright" if star.magnitude < 0.5 else
                               "bright" if star.magnitude < 1.5 else
                               "moderate" if star.magnitude < 2.5 else "faint",
        },
    }


# =============================================================================
# COMPREHENSIVE STAR ANALYSIS
# =============================================================================

def analyze_natal_fixed_stars(
    natal_timestamp: str,
    latitude: float,
    longitude: float
) -> Dict[str, Any]:
    """Comprehensive fixed star analysis for a natal chart.

    Args:
        natal_timestamp: Birth timestamp (ISO 8601)
        latitude: Birth latitude
        longitude: Birth longitude

    Returns:
        Comprehensive analysis including conjunctions and interpretations
    """
    # Find conjunctions
    conjunctions_result = find_star_conjunctions(natal_timestamp, latitude, longitude)

    # Analyze patterns
    powerful_conjunctions = [c for c in conjunctions_result["conjunctions"] if c["exact"]]
    royal_star_conjunctions = [
        c for c in conjunctions_result["conjunctions"]
        if c["star"]["id"] in ["aldebaran", "regulus", "antares", "fomalhaut"]
    ]

    # Count planets in conjunction with stars
    planets_with_stars = set(c["planet"] for c in conjunctions_result["conjunctions"])

    return {
        "natal_timestamp": natal_timestamp,
        "location": {"latitude": latitude, "longitude": longitude},
        "summary": {
            "total_conjunctions": conjunctions_result["conjunctions_count"],
            "exact_conjunctions": len(powerful_conjunctions),
            "royal_star_conjunctions": len(royal_star_conjunctions),
            "planets_activated": list(planets_with_stars),
        },
        "conjunctions": conjunctions_result["conjunctions"],
        "interpretation": generate_natal_star_interpretation(conjunctions_result),
    }


def generate_natal_star_interpretation(conjunctions_result: Dict[str, Any]) -> str:
    """Generate interpretive text for natal fixed star analysis.

    Args:
        conjunctions_result: Result from find_star_conjunctions

    Returns:
        Interpretive text
    """
    conjunctions = conjunctions_result["conjunctions"]

    if not conjunctions:
        return "No major fixed star conjunctions found within orb. The native's chart is not significantly activated by the fixed stars."

    lines = ["=== FIXED STAR INTERPRETATION ===\n"]

    # Group by planet
    by_planet = {}
    for c in conjunctions:
        planet = c["planet"]
        if planet not in by_planet:
            by_planet[planet] = []
        by_planet[planet].append(c)

    for planet, star_cons in sorted(by_planet.items()):
        lines.append(f"\n**{planet.capitalize()} activated by:**")
        for sc in star_cons:
            star = sc["star"]
            orb = sc["orb_distance"]
            exact_mark = " (EXACT)" if sc["exact"] else ""
            lines.append(f"  - {star['name']}: {star['meaning'][:80]}...{exact_mark}")
            if star["keywords"]:
                lines.append(f"    Keywords: {', '.join(star['keywords'][:5])}")

    # Royal star conjunctions
    royal_stars = [sc for sc in conjunctions
                   if sc["star"]["id"] in ["aldebaran", "regulus", "antares", "fomalhaut"]]
    if royal_stars:
        lines.append("\n**Royal Star Activations:**")
        for sc in royal_stars:
            star = sc["star"]
            lines.append(f"  - {star['name']} (Watcher of the Four Directions): {star['meaning'][:100]}...")

    return "\n".join(lines)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "FixedStar",
    "FIXED_STAR_CATALOG",
    "list_fixed_stars",
    "get_fixed_star",
    "find_star_conjunctions",
    "calculate_star_parans",
    "calculate_star_phase",
    "analyze_natal_fixed_stars",
]
