"""
Vedic Astrology Calculations
Core logic for Nakshatras, Tithis, Vargas (Divisional Charts), and Yogas.
"""

from typing import Dict, Any, List
from thia_lite.engines.vedic_yogas_data import NAKSHATRAS, TITHIS, VIMSHOTTARI_YEARS

def calculate_nakshatra(longitude: float) -> Dict[str, Any]:
    """Calculate the Nakshatra and Pada (quarter) from a sidereal longitude."""
    # Ensure longitude is 0-360
    lon = longitude % 360.0
    
    # 27 Nakshatras, each 13°20' (13.3333... degrees)
    nakshatra_length = 360.0 / 27.0
    
    # Each Nakshatra has 4 Padas, each 3°20' (3.3333... degrees)
    pada_length = nakshatra_length / 4.0
    
    # Find index (0-26)
    idx = int(lon / nakshatra_length)
    
    # Find remainder in current Nakshatra
    remainder = lon - (idx * nakshatra_length)
    
    # Find Pada (1-4)
    pada = int(remainder / pada_length) + 1
    
    # Get Nakshatra data
    nak_data = NAKSHATRAS[idx]
    
    return {
        "id": nak_data["id"],
        "name": nak_data["name"],
        "ruler": nak_data["ruler"],
        "deity": nak_data["deity"],
        "pada": pada,
        "longitude_in_nakshatra": round(remainder, 6),
        "quality": nak_data["quality"]
    }

def calculate_tithi(sun_lon: float, moon_lon: float) -> Dict[str, Any]:
    """Calculate the Vedic lunar day (Tithi) based on the angle between Sun and Moon."""
    # Tithi is the 12-degree phase angle of the Moon from the Sun
    # (Moon_Lon - Sun_Lon) / 12
    # If negative, add 360
    
    angle = (moon_lon - sun_lon) % 360.0
    
    # Tithi index is 0-29
    tithi_idx = int(angle / 12.0)
    
    # Fraction through the current Tithi
    fraction = (angle % 12.0) / 12.0
    
    tithi_data = TITHIS[tithi_idx]
    
    return {
        "id": tithi_data["id"],
        "name": tithi_data["name"],
        "nature": tithi_data["nature"],
        "deity": tithi_data["deity"],
        "auspicious": tithi_data["auspicious"],
        "completion_percentage": round(fraction * 100, 2)
    }

def calculate_navamsa(longitude: float) -> float:
    """
    Calculate the Navamsa (D9) longitude.
    Multiply longitude by 9.
    """
    return (longitude * 9.0) % 360.0

def _get_lord_of_house(house_num: int, ascendant_sign: str) -> str:
    """Helper to find the ruling planet of a specific house given the Ascendant."""
    signs = [
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", 
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
    ]
    rulers = {
        "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon",
        "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars",
        "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter"
    }
    
    try:
        asc_idx = signs.index(ascendant_sign)
        house_sign_idx = (asc_idx + house_num - 1) % 12
        house_sign = signs[house_sign_idx]
        return rulers[house_sign]
    except ValueError:
        return "Unknown"

def calculate_yogas(planets_data: Dict[str, Any], planets_in_houses: Dict[str, int], ascendant_sign: str) -> List[Dict[str, Any]]:
    """
    Evaluate basic Vedic Yogas based on planetary positions and house lordships.
    Returns a list of identified yogas with their name and description.
    """
    yogas_found = []
    
    # 1. Pancha Mahapurusha Yogas (Mars, Mercury, Jupiter, Venus, Saturn in Domicile/Exaltation in Kendras)
    kendras = [1, 4, 7, 10]
    
    mahapurusha_rules = {
        "Mars": {"name": "Ruchaka Yoga", "signs": ["Aries", "Scorpio", "Capricorn"], "desc": "Courage, wealth, military skill or strong leadership."},
        "Mercury": {"name": "Bhadra Yoga", "signs": ["Gemini", "Virgo"], "desc": "High intelligence, communication skills, and business acumen."},
        "Jupiter": {"name": "Hamsa Yoga", "signs": ["Sagittarius", "Pisces", "Cancer"], "desc": "Wisdom, pure ethics, spirituality, and respect."},
        "Venus": {"name": "Malavya Yoga", "signs": ["Taurus", "Libra", "Pisces"], "desc": "Artistic success, beauty, luxury, and marital happiness."},
        "Saturn": {"name": "Sasha Yoga", "signs": ["Capricorn", "Aquarius", "Libra"], "desc": "Power, authority over masses, and deep structural stamina."}
    }
    
    for planet, rule in mahapurusha_rules.items():
        if planet in planets_data and planet in planets_in_houses:
            p_data = planets_data[planet]
            p_house = planets_in_houses[planet]
            if p_house in kendras and p_data["sign"] in rule["signs"]:
                yogas_found.append({"name": rule["name"], "type": "Pancha Mahapurusha", "description": rule["desc"], "planets": [planet]})

    # 2. Lunar Yogas
    # Gaja Kesari (Jupiter in Kendra from Moon)
    if "Moon" in planets_in_houses and "Jupiter" in planets_in_houses:
        moon_house = planets_in_houses["Moon"]
        jup_house = planets_in_houses["Jupiter"]
        
        # Calculate relative distance in houses
        relative_idx = ((jup_house - moon_house) % 12) + 1
        if relative_idx in kendras:
             yogas_found.append({
                 "name": "Gaja Kesari Yoga", 
                 "type": "Lunar", 
                 "description": "Jupiter is in a Kendra from the Moon. Grants eloquence, wisdom, and lasting reputation.",
                 "planets": ["Moon", "Jupiter"]
             })
             
    # 3. Basic Raja & Dhana Yogas (Lordships)
    # Trikonas (Trines): 1, 5, 9
    # Kendras (Angles): 1, 4, 7, 10
    # Dhana Houses (Wealth): 2, 11
    
    kendra_lords = set([_get_lord_of_house(h, ascendant_sign) for h in kendras])
    trikona_lords = set([_get_lord_of_house(h, ascendant_sign) for h in [1, 5, 9]])
    dhana_lords = set([_get_lord_of_house(h, ascendant_sign) for h in [2, 11, 5, 9]])
    
    # Check conjunctions in the same house for Raja/Dhana yogas
    from collections import defaultdict
    house_occupants = defaultdict(list)
    for p, h in planets_in_houses.items():
        if p not in ["True Node", "Mean Node", "South Node", "Uranus", "Neptune", "Pluto"]: # Traditional only
            house_occupants[h].append(p)
            
    for house, occupants in house_occupants.items():
        if len(occupants) >= 2:
            # Check combinations
            is_kendra = False
            is_trikona = False
            is_dhana_1 = False
            is_dhana_2 = False
            
            for o in occupants:
                if o in kendra_lords: is_kendra = True
                if o in trikona_lords: is_trikona = True
                if o == _get_lord_of_house(2, ascendant_sign) or o == _get_lord_of_house(11, ascendant_sign): is_dhana_1 = True
                if o in trikona_lords: is_dhana_2 = True
                
            if is_kendra and is_trikona:
                yogas_found.append({
                    "name": f"Raja Yoga in House {house}",
                    "type": "Raja",
                    "description": "Conjunction of a Kendra lord and a Trikona lord, elevating status and success.",
                    "planets": occupants
                })
            
            if is_dhana_1 and is_dhana_2:
                yogas_found.append({
                    "name": f"Dhana Yoga in House {house}",
                    "type": "Dhana",
                    "description": "Conjunction of wealth house lords (2/11) with trine lords (5/9), indicating financial prosperity.",
                    "planets": occupants
                })
                
    return yogas_found
