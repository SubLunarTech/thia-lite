"""
William Lilly Rules — Christian Astrology (1647)
=================================================
Public domain traditional astrological rules extracted from
William Lilly's "Christian Astrology", the definitive horary
and natal astrology text of the Western tradition.

Used for RAG (Retrieval-Augmented Generation) — relevant rules are
automatically injected into the LLM's context during conversations.
"""

from typing import List, Dict, Any

# ─── Lilly's Essential Dignities (CA pp. 101-104) ────────────────────────────

LILLY_DIGNITIES = [
    {
        "id": "lilly_dig_001",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "101",
        "category": "Essential Dignities",
        "text": "A planet in its own house is like a man in his own castle: he is strong, confident, and can exercise his full authority without impediment. This is the strongest essential dignity.",
    },
    {
        "id": "lilly_dig_002",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "102",
        "category": "Essential Dignities",
        "text": "A planet in its exaltation is like a man amongst his friends, where he is received with honour. He is not quite as powerful as in his own house, but he is greatly dignified and respected.",
    },
    {
        "id": "lilly_dig_003",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "102",
        "category": "Essential Dignities",
        "text": "A planet in its triplicity has moderate dignity, like a man who has modest support from kin. It gives some strength but less than domicile or exaltation.",
    },
    {
        "id": "lilly_dig_004",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "103",
        "category": "Essential Dignities",
        "text": "A planet in its term has minor dignity, akin to a man who holds a small office. It provides a little essential virtue but not enough to overcome debility on its own.",
    },
    {
        "id": "lilly_dig_005",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "103",
        "category": "Essential Dignities",
        "text": "A planet in its face (decan) has the least essential dignity, like a man barely able to keep himself from poverty. It is a very weak dignity indeed.",
    },
    {
        "id": "lilly_dig_006",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "104",
        "category": "Essential Dignities",
        "text": "A planet peregrine — having no essential dignity whatsoever — is like a vagabond, without means or standing. A peregrine malefic is exceedingly destructive.",
    },
    {
        "id": "lilly_dig_007",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "104",
        "category": "Essential Dignities",
        "text": "A planet in its detriment is like a man banished from his home: he is weakened, uncomfortable, and unable to perform his natural functions well.",
    },
    {
        "id": "lilly_dig_008",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "104",
        "category": "Essential Dignities",
        "text": "A planet in its fall is like a man cast into prison: he is at his weakest, most debilitated, and his virtues are corrupted or rendered impotent.",
    },
]

# ─── Lilly's Horary Principles (CA pp. 121-298) ─────────────────────────────

LILLY_HORARY = [
    {
        "id": "lilly_hor_001",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "121",
        "category": "Horary",
        "text": "The Ascendant and its lord represent the querent — the person asking the question. The condition of the lord of the Ascendant shows the state and disposition of the querent.",
    },
    {
        "id": "lilly_hor_002",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "122",
        "category": "Horary",
        "text": "The house ruling the matter asked about represents the quesited. Its lord, planets therein, and the Moon are all significators to be examined.",
    },
    {
        "id": "lilly_hor_003",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "124",
        "category": "Horary",
        "text": "If the lord of the Ascendant and the lord of the house of the quesited apply to conjunction, sextile, or trine, the matter will be brought to perfection (accomplished) with ease.",
    },
    {
        "id": "lilly_hor_004",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "125",
        "category": "Horary",
        "text": "If significators apply to square or opposition, the matter may be accomplished but with difficulty, delay, and strife. Mutual reception between the significators greatly helps.",
    },
    {
        "id": "lilly_hor_005",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "125",
        "category": "Horary",
        "text": "The Moon is always co-significator of the querent and the question. If the Moon applies to the significator of the quesited, this is a strong testimony in favour of the matter.",
    },
    {
        "id": "lilly_hor_006",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "126",
        "category": "Horary",
        "text": "Translation of light occurs when a faster planet separates from one significator and applies to another, carrying the light between them and bringing the matter to completion through an intermediary.",
    },
    {
        "id": "lilly_hor_007",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "127",
        "category": "Horary",
        "text": "Collection of light occurs when both significators apply to a heavier, slower planet that collects their light. This planet represents the person who will bring the two parties together.",
    },
    {
        "id": "lilly_hor_008",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "128",
        "category": "Horary",
        "text": "Prohibition occurs when a planet interposes itself between the two significators before they perfect their aspect, thereby preventing the matter from coming to pass.",
    },
    {
        "id": "lilly_hor_009",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "129",
        "category": "Horary",
        "text": "Refranation occurs when one significator, before perfecting the aspect, turns retrograde and withdraws. The matter seemed about to happen but falls apart at the last moment.",
    },
    {
        "id": "lilly_hor_010",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "130",
        "category": "Horary",
        "text": "Combustion — when a planet is within 8°30' of the Sun — is the most severe accidental debility. A combust significator shows the person in a terrible state, unable to act.",
    },
    {
        "id": "lilly_hor_011",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "131",
        "category": "Horary",
        "text": "Considerations before judgement: if the Ascendant is in the first 3° or last 3° of a sign, the chart may be too early or too late to judge. Also, if Saturn is in the 7th house, the astrologer's judgment may be faulty.",
    },
    {
        "id": "lilly_hor_012",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "133",
        "category": "Horary",
        "text": "The Moon void of course signifies that nothing will come of the matter — the current situation will persist without resolution, unless the Moon is in Taurus, Cancer, Sagittarius, or Pisces where being void is less harmful.",
    },
]

# ─── Lilly's Houses (CA pp. 50-64) ──────────────────────────────────────────

LILLY_HOUSES = [
    {
        "id": "lilly_house_001",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "50-64",
        "category": "Houses",
        "text": "1st House: Life, body, complexion, temperament of the querent. 2nd: Money, possessions. 3rd: Brethren, short journeys, letters. 4th: Father, lands, hidden treasure, the end of the matter. 5th: Children, pleasure, gambling. 6th: Sickness, servants, small animals.",
    },
    {
        "id": "lilly_house_002",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "50-64",
        "category": "Houses",
        "text": "7th House: Marriage, open enemies, lawsuits, partnerships. 8th: Death, legacies, the substance of others. 9th: Long journeys, religion, dreams, philosophy. 10th: Honour, profession, the mother, authority. 11th: Friends, hopes, wishes. 12th: Secret enemies, imprisonment, large animals, self-undoing.",
    },
]

# ─── Lilly's Planetary Significations (CA pp. 66-97) ────────────────────────

LILLY_PLANETS = [
    {
        "id": "lilly_plt_001",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "66-68",
        "category": "Planetary Nature",
        "text": "Saturn well-dignified signifies gravity, wisdom, constancy, patience, and industry. Ill-dignified he is envious, covetous, suspicious, malcontent, slow, and deceitful.",
    },
    {
        "id": "lilly_plt_002",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "72-74",
        "category": "Planetary Nature",
        "text": "Jupiter well-dignified signifies magnanimity, faithfulness, justice, honesty, and prudence. Ill-dignified he shows wastefulness, hypocrisy, negligence, and carelessness.",
    },
    {
        "id": "lilly_plt_003",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "78-80",
        "category": "Planetary Nature",
        "text": "Mars well-dignified makes a man invincible in war, fearless, bold, and confident. Ill-dignified he brings quarrels, violence, theft, murder, and cruelty without remorse.",
    },
    {
        "id": "lilly_plt_004",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "84-86",
        "category": "Planetary Nature",
        "text": "Venus well-dignified signifies quiet civility, pleasant mirth, love of music and art, and all things that bring delight. Ill-dignified she brings scandalous, lustful, and prodigal behaviour.",
    },
    {
        "id": "lilly_plt_005",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "90-92",
        "category": "Planetary Nature",
        "text": "Mercury well-dignified gives sharp wit, excellent learning, eloquent speech, and skill in divination. Ill-dignified he produces a troublesome wit, a liar, thief, and mean-spirited boaster.",
    },
]

# ─── Lilly's Timing Rules (CA pp. 215-220) ───────────────────────────────────

LILLY_TIMING = [
    {
        "id": "lilly_time_001",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "215-220",
        "category": "Timing",
        "text": "In angular houses, events happen swiftly — degrees represent days or weeks. In succedent houses, events take moderate time — degrees represent weeks or months. In cadent houses, events take the longest — degrees represent months or years.",
    },
    {
        "id": "lilly_time_002",
        "source": "William Lilly",
        "work": "Christian Astrology",
        "page": "215-220",
        "category": "Timing",
        "text": "Cardinal signs hasten matters, fixed signs delay them, common (mutable) signs give a moderate pace. The number of degrees between applying significators gives the count of time units.",
    },
]


# ─── All Lilly Rules ─────────────────────────────────────────────────────────

def get_all_lilly_rules() -> List[Dict[str, Any]]:
    """Return all William Lilly rules as a flat list."""
    return (
        LILLY_DIGNITIES +
        LILLY_HORARY +
        LILLY_HOUSES +
        LILLY_PLANETS +
        LILLY_TIMING
    )


def get_lilly_rules_by_category(category: str) -> List[Dict[str, Any]]:
    """Get Lilly rules filtered by category."""
    return [r for r in get_all_lilly_rules() if r["category"] == category]


# ─── Statistics ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    rules = get_all_lilly_rules()
    categories = set(r["category"] for r in rules)
    print(f"William Lilly (Christian Astrology) Rules: {len(rules)}")
    for cat in sorted(categories):
        count = len([r for r in rules if r["category"] == cat])
        print(f"  {cat}: {count}")
