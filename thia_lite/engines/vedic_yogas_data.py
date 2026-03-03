"""
Vedic Astrology Data Store
Contains static data for Nakshatras, Tithis, and rule definitions for Yogas.
"""

from typing import Dict, Any, List

# --- Nakshatras (Lunar Mansions) ---
# Each Nakshatra spans exactly 13 degrees and 20 minutes (13.333333 degrees) of the ecliptic.
# There are 27 Nakshatras totaling 360 degrees.
NAKSHATRAS = [
    {"id": 1, "name": "Ashwini", "ruler": "Ketu", "deity": "Ashwini Kumaras", "symbol": "Horse's head", "quality": "Light/Swift"},
    {"id": 2, "name": "Bharani", "ruler": "Venus", "deity": "Yama", "symbol": "Yoni", "quality": "Fierce/Severe"},
    {"id": 3, "name": "Krittika", "ruler": "Sun", "deity": "Agni", "symbol": "Razor/Flame", "quality": "Mixed"},
    {"id": 4, "name": "Rohini", "ruler": "Moon", "deity": "Brahma", "symbol": "Chariot", "quality": "Fixed/Steady"},
    {"id": 5, "name": "Mrigashira", "ruler": "Mars", "deity": "Soma", "symbol": "Deer's head", "quality": "Soft/Mild"},
    {"id": 6, "name": "Ardra", "ruler": "Rahu", "deity": "Rudra", "symbol": "Teardrop/Diamond", "quality": "Fierce/Severe"},
    {"id": 7, "name": "Punarvasu", "ruler": "Jupiter", "deity": "Aditi", "symbol": "Bow/Quiver", "quality": "Movable"},
    {"id": 8, "name": "Pushya", "ruler": "Saturn", "deity": "Brihaspati", "symbol": "Cow's udder/Flower", "quality": "Light/Swift"},
    {"id": 9, "name": "Ashlesha", "ruler": "Mercury", "deity": "Nagas", "symbol": "Coiled serpent", "quality": "Sharp/Dreadful"},
    {"id": 10, "name": "Magha", "ruler": "Ketu", "deity": "Pitris", "symbol": "Royal throne", "quality": "Fierce/Severe"},
    {"id": 11, "name": "Purva Phalguni", "ruler": "Venus", "deity": "Bhaga", "symbol": "Front legs of bed", "quality": "Fierce/Severe"},
    {"id": 12, "name": "Uttara Phalguni", "ruler": "Sun", "deity": "Aryaman", "symbol": "Back legs of bed", "quality": "Fixed/Steady"},
    {"id": 13, "name": "Hasta", "ruler": "Moon", "deity": "Savitar", "symbol": "Hand/Fist", "quality": "Light/Swift"},
    {"id": 14, "name": "Chitra", "ruler": "Mars", "deity": "Vishvakarma", "symbol": "Pearl/Gem", "quality": "Soft/Mild"},
    {"id": 15, "name": "Swati", "ruler": "Rahu", "deity": "Vayu", "symbol": "Shoot of plant/Coral", "quality": "Movable"},
    {"id": 16, "name": "Vishakha", "ruler": "Jupiter", "deity": "Indrani/Mitra", "symbol": "Triumphal arch", "quality": "Mixed"},
    {"id": 17, "name": "Anuradha", "ruler": "Saturn", "deity": "Mitra", "symbol": "Triumphal arch/Lotus", "quality": "Soft/Mild"},
    {"id": 18, "name": "Jyeshtha", "ruler": "Mercury", "deity": "Indra", "symbol": "Umbrella/Earring", "quality": "Sharp/Dreadful"},
    {"id": 19, "name": "Mula", "ruler": "Ketu", "deity": "Nirriti", "symbol": "Tied bunch of roots", "quality": "Sharp/Dreadful"},
    {"id": 20, "name": "Purva Ashadha", "ruler": "Venus", "deity": "Apas", "symbol": "Elephant tusk/Fan", "quality": "Fierce/Severe"},
    {"id": 21, "name": "Uttara Ashadha", "ruler": "Sun", "deity": "Vishwadevas", "symbol": "Elephant tusk/Bed", "quality": "Fixed/Steady"},
    {"id": 22, "name": "Shravana", "ruler": "Moon", "deity": "Vishnu", "symbol": "Ear/Three footprints", "quality": "Movable"},
    {"id": 23, "name": "Dhanishta", "ruler": "Mars", "deity": "Vasus", "symbol": "Drum/Flute", "quality": "Movable"},
    {"id": 24, "name": "Shatabhisha", "ruler": "Rahu", "deity": "Varuna", "symbol": "Empty circle/100 stars", "quality": "Movable"},
    {"id": 25, "name": "Purva Bhadrapada", "ruler": "Jupiter", "deity": "Aja Ekapada", "symbol": "Swords/Two front legs of funeral cot", "quality": "Fierce/Severe"},
    {"id": 26, "name": "Uttara Bhadrapada", "ruler": "Saturn", "deity": "Ahir Budhyana", "symbol": "Twins/Back legs of funeral cot", "quality": "Fixed/Steady"},
    {"id": 27, "name": "Revati", "ruler": "Mercury", "deity": "Pushan", "symbol": "Fish/Drum", "quality": "Soft/Mild"}
]

# Map Nakshatra ruler to Vimshottari Dasha period in years
VIMSHOTTARI_YEARS = {
    "Ketu": 7,
    "Venus": 20,
    "Sun": 6,
    "Moon": 10,
    "Mars": 7,
    "Rahu": 18,
    "Jupiter": 16,
    "Saturn": 19,
    "Mercury": 17
}

# --- Tithis (Vedic Lunar Days) ---
# 1-15: Shukla Paksha (Waxing Phase)
# 16-30: Krishna Paksha (Waning Phase)
TITHIS = [
    # Shukla Paksha
    {"id": 1, "name": "Pratipada (Shukla)", "nature": "Nanda (Joy/Happiness)", "deity": "Agni", "auspicious": True},
    {"id": 2, "name": "Dwitiya (Shukla)", "nature": "Bhadra (Auspicious)", "deity": "Ashwini Kumaras", "auspicious": True},
    {"id": 3, "name": "Tritiya (Shukla)", "nature": "Jaya (Victory)", "deity": "Gauri", "auspicious": True},
    {"id": 4, "name": "Chaturthi (Shukla)", "nature": "Rikta (Empty/Loss)", "deity": "Ganesha", "auspicious": False}, # Rikta tithis generally avoided
    {"id": 5, "name": "Panchami (Shukla)", "nature": "Purna (Fullness)", "deity": "Nagas", "auspicious": True},
    {"id": 6, "name": "Shashthi (Shukla)", "nature": "Nanda", "deity": "Kartikeya", "auspicious": True},
    {"id": 7, "name": "Saptami (Shukla)", "nature": "Bhadra", "deity": "Surya", "auspicious": True},
    {"id": 8, "name": "Ashtami (Shukla)", "nature": "Jaya", "deity": "Shiva/Durga", "auspicious": True},
    {"id": 9, "name": "Navami (Shukla)", "nature": "Rikta", "deity": "Durga", "auspicious": False},
    {"id": 10, "name": "Dashami (Shukla)", "nature": "Purna", "deity": "Yama", "auspicious": True},
    {"id": 11, "name": "Ekadashi (Shukla)", "nature": "Nanda", "deity": "Vishnu", "auspicious": True},
    {"id": 12, "name": "Dwadashi (Shukla)", "nature": "Bhadra", "deity": "Vishnu", "auspicious": True},
    {"id": 13, "name": "Trayodashi (Shukla)", "nature": "Jaya", "deity": "Kamadeva", "auspicious": True},
    {"id": 14, "name": "Chaturdashi (Shukla)", "nature": "Rikta", "deity": "Shiva", "auspicious": False},
    {"id": 15, "name": "Purnima", "nature": "Purna", "deity": "Moon", "auspicious": True}, # Full Moon
    
    # Krishna Paksha
    {"id": 16, "name": "Pratipada (Krishna)", "nature": "Nanda", "deity": "Agni", "auspicious": True},
    {"id": 17, "name": "Dwitiya (Krishna)", "nature": "Bhadra", "deity": "Ashwini Kumaras", "auspicious": True},
    {"id": 18, "name": "Tritiya (Krishna)", "nature": "Jaya", "deity": "Gauri", "auspicious": True},
    {"id": 19, "name": "Chaturthi (Krishna)", "nature": "Rikta", "deity": "Ganesha", "auspicious": False},
    {"id": 20, "name": "Panchami (Krishna)", "nature": "Purna", "deity": "Nagas", "auspicious": True},
    {"id": 21, "name": "Shashthi (Krishna)", "nature": "Nanda", "deity": "Kartikeya", "auspicious": True},
    {"id": 22, "name": "Saptami (Krishna)", "nature": "Bhadra", "deity": "Surya", "auspicious": True},
    {"id": 23, "name": "Ashtami (Krishna)", "nature": "Jaya", "deity": "Shiva", "auspicious": True},
    {"id": 24, "name": "Navami (Krishna)", "nature": "Rikta", "deity": "Durga", "auspicious": False},
    {"id": 25, "name": "Dashami (Krishna)", "nature": "Purna", "deity": "Yama", "auspicious": True},
    {"id": 26, "name": "Ekadashi (Krishna)", "nature": "Nanda", "deity": "Vishnu", "auspicious": True},
    {"id": 27, "name": "Dwadashi (Krishna)", "nature": "Bhadra", "deity": "Vishnu", "auspicious": True},
    {"id": 28, "name": "Trayodashi (Krishna)", "nature": "Jaya", "deity": "Kamadeva", "auspicious": True},
    {"id": 29, "name": "Chaturdashi (Krishna)", "nature": "Rikta", "deity": "Shiva", "auspicious": False},
    {"id": 30, "name": "Amavasya", "nature": "Purna", "deity": "Pitris", "auspicious": False}  # New Moon
]
