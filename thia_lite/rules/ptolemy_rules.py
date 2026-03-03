"""
Ptolemy Rules — Tetrabiblos (2nd Century CE)
=============================================
Public domain traditional astrological rules extracted from
Claudius Ptolemy's Tetrabiblos, the foundational text of
Western horoscopic astrology.

These rules are used for RAG (Retrieval-Augmented Generation) —
when the user asks about astrology, relevant Ptolemy rules are
automatically injected into the LLM's context.
"""

from typing import List, Dict, Any

# ─── Ptolemy's Essential Dignities (Tetrabiblos I.20-24) ──────────────────────

PTOLEMY_DIGNITIES = [
    {
        "id": "ptolemy_dig_001",
        "source": "Ptolemy",
        "work": "Tetrabiblos",
        "book": "I",
        "chapter": "20-24",
        "category": "Essential Dignities",
        "text": "Each of the planets has one or two signs as its domicile, wherein it exercises its greatest authority. The Sun rules Leo, the Moon Cancer, Mercury Gemini and Virgo, Venus Taurus and Libra, Mars Aries and Scorpio, Jupiter Sagittarius and Pisces, Saturn Capricorn and Aquarius.",
    },
    {
        "id": "ptolemy_dig_002",
        "source": "Ptolemy",
        "work": "Tetrabiblos",
        "book": "I",
        "chapter": "20",
        "category": "Essential Dignities",
        "text": "The exaltation of a planet is a sign in which its influence is strengthened. The Sun is exalted in Aries, the Moon in Taurus, Mercury in Virgo, Venus in Pisces, Mars in Capricorn, Jupiter in Cancer, Saturn in Libra.",
    },
    {
        "id": "ptolemy_dig_003",
        "source": "Ptolemy",
        "work": "Tetrabiblos",
        "book": "I",
        "chapter": "21",
        "category": "Essential Dignities",
        "text": "When a planet is in the sign opposite its domicile, it is in its detriment and weakened. When in the sign opposite its exaltation, it is in its fall and debilitated.",
    },
]

# ─── Ptolemy's Aspects (Tetrabiblos I.13-16) ─────────────────────────────────

PTOLEMY_ASPECTS = [
    {
        "id": "ptolemy_asp_001",
        "source": "Ptolemy",
        "work": "Tetrabiblos",
        "book": "I",
        "chapter": "13",
        "category": "Aspects",
        "text": "Signs which are in sextile aspect (60°) are said to be in harmonious relationship, as they share either the same element or complementary qualities. This is a moderately benefic aspect.",
    },
    {
        "id": "ptolemy_asp_002",
        "source": "Ptolemy",
        "work": "Tetrabiblos",
        "book": "I",
        "chapter": "13",
        "category": "Aspects",
        "text": "Signs in trine (120°) share the same element and are therefore most harmonious. The trine is the most powerful benefic aspect, as the planets can fully cooperate.",
    },
    {
        "id": "ptolemy_asp_003",
        "source": "Ptolemy",
        "work": "Tetrabiblos",
        "book": "I",
        "chapter": "14",
        "category": "Aspects",
        "text": "The square (90°) creates tension between signs of the same modality but different elements. It is considered a malefic aspect producing conflict and challenge.",
    },
    {
        "id": "ptolemy_asp_004",
        "source": "Ptolemy",
        "work": "Tetrabiblos",
        "book": "I",
        "chapter": "15",
        "category": "Aspects",
        "text": "The opposition (180°) is the strongest malefic aspect, placing planets at maximum distance. However, unlike the square, opposition allows awareness between the two principles.",
    },
    {
        "id": "ptolemy_asp_005",
        "source": "Ptolemy",
        "work": "Tetrabiblos",
        "book": "I",
        "chapter": "16",
        "category": "Aspects",
        "text": "Signs that are not configured by any of these aspects (sextile, square, trine, opposition) are said to be averse or inconjunct, and planets in such signs cannot see one another.",
    },
]

# ─── Ptolemy's Planetary Natures (Tetrabiblos I.4-8) ─────────────────────────

PTOLEMY_PLANETS = [
    {
        "id": "ptolemy_plt_001",
        "source": "Ptolemy",
        "work": "Tetrabiblos",
        "book": "I",
        "chapter": "4",
        "category": "Planetary Nature",
        "text": "Saturn is cold and dry in nature. It is the greater malefic, associated with restriction, limitation, old age, slowness, and melancholy. Its influence is contractive and separative.",
    },
    {
        "id": "ptolemy_plt_002",
        "source": "Ptolemy",
        "work": "Tetrabiblos",
        "book": "I",
        "chapter": "4",
        "category": "Planetary Nature",
        "text": "Jupiter is warm and moist in nature. It is the greater benefic, associated with growth, abundance, justice, wisdom, and good fortune. Its influence is expansive and generative.",
    },
    {
        "id": "ptolemy_plt_003",
        "source": "Ptolemy",
        "work": "Tetrabiblos",
        "book": "I",
        "chapter": "5",
        "category": "Planetary Nature",
        "text": "Mars is hot and dry in nature. It is the lesser malefic, associated with action, conflict, courage, destruction, and fever. Its influence is separative and combustive.",
    },
    {
        "id": "ptolemy_plt_004",
        "source": "Ptolemy",
        "work": "Tetrabiblos",
        "book": "I",
        "chapter": "5",
        "category": "Planetary Nature",
        "text": "Venus is cold and moist in nature. It is the lesser benefic, associated with beauty, pleasure, love, art, and harmony. Its influence is uniting and temperate.",
    },
    {
        "id": "ptolemy_plt_005",
        "source": "Ptolemy",
        "work": "Tetrabiblos",
        "book": "I",
        "chapter": "6",
        "category": "Planetary Nature",
        "text": "Mercury partakes of both drying and moistening and is therefore versatile, taking on the nature of whatever planet it is configured with. It governs speech, writing, commerce, and intellect.",
    },
    {
        "id": "ptolemy_plt_006",
        "source": "Ptolemy",
        "work": "Tetrabiblos",
        "book": "I",
        "chapter": "7",
        "category": "Planetary Nature",
        "text": "The Sun is primarily heating and moderately drying. It is generative and is the source of all light and life. As the center of the cosmos, it governs vitality, authority, and the principle of individuation.",
    },
    {
        "id": "ptolemy_plt_007",
        "source": "Ptolemy",
        "work": "Tetrabiblos",
        "book": "I",
        "chapter": "8",
        "category": "Planetary Nature",
        "text": "The Moon is primarily moistening and moderately heating. Being closest to Earth, she has the greatest effect on terrestrial matters. She governs the body, fertility, change, and the reception of celestial influences.",
    },
]

# ─── Ptolemy's Sect (Tetrabiblos I.7) ────────────────────────────────────────

PTOLEMY_SECT = [
    {
        "id": "ptolemy_sect_001",
        "source": "Ptolemy",
        "work": "Tetrabiblos",
        "book": "I",
        "chapter": "7",
        "category": "Sect",
        "text": "The Sun, Jupiter, and Saturn belong to the diurnal sect. The Moon, Venus, and Mars belong to the nocturnal sect. Mercury is common to both. In a day chart, diurnal planets are more beneficent; in a night chart, nocturnal planets prevail.",
    },
    {
        "id": "ptolemy_sect_002",
        "source": "Ptolemy",
        "work": "Tetrabiblos",
        "book": "I",
        "chapter": "7",
        "category": "Sect",
        "text": "A planet of the diurnal sect in a nocturnal chart is weakened and acts contrary to its best nature. Similarly, a nocturnal planet in a day chart cannot express itself fully. This is the principle of hayz and its contrary.",
    },
]

# ─── Ptolemy on Natal Interpretation (Tetrabiblos III-IV) ─────────────────────

PTOLEMY_NATAL = [
    {
        "id": "ptolemy_nat_001",
        "source": "Ptolemy",
        "work": "Tetrabiblos",
        "book": "III",
        "chapter": "2",
        "category": "Natal Astrology",
        "text": "The quality of the soul is determined principally by the condition of Mercury and the Moon. If both are well-placed in the chart and configured with benefic planets, the native will be of sound mind and good character.",
    },
    {
        "id": "ptolemy_nat_002",
        "source": "Ptolemy",
        "work": "Tetrabiblos",
        "book": "III",
        "chapter": "4",
        "category": "Natal Astrology",
        "text": "The length of life is determined by the hyleg (giver of life) and its relation to the anareta (destroyer of life). The five hylegial places are the Ascendant, Midheaven, Sun, Moon, and the Part of Fortune.",
    },
    {
        "id": "ptolemy_nat_003",
        "source": "Ptolemy",
        "work": "Tetrabiblos",
        "book": "III",
        "chapter": "12",
        "category": "Natal Astrology",
        "text": "The quality of action (career) is judged from the Midheaven, the planets configured with it, and especially the ruler of the sign on the Midheaven. Mercury gives skills in writing, commerce, and calculation; Venus in art and music; Mars in warfare and metalwork.",
    },
    {
        "id": "ptolemy_nat_004",
        "source": "Ptolemy",
        "work": "Tetrabiblos",
        "book": "IV",
        "chapter": "5",
        "category": "Natal Astrology",
        "text": "Marriage is judged from the position and condition of Venus and Mars for men, and from the Sun and Moon for women. Benefic aspects between these significators indicate harmonious partnerships.",
    },
    {
        "id": "ptolemy_nat_005",
        "source": "Ptolemy",
        "work": "Tetrabiblos",
        "book": "III",
        "chapter": "10",
        "category": "Natal Astrology",
        "text": "Wealth and material fortune are determined by the Part of Fortune, its ruler, and the planets configured with them. Jupiter and Venus well-placed indicate abundance; Saturn and Mars poorly placed indicate privation.",
    },
]

# ─── Ptolemy on Mundane Astrology (Tetrabiblos II) ───────────────────────────

PTOLEMY_MUNDANE = [
    {
        "id": "ptolemy_mun_001",
        "source": "Ptolemy",
        "work": "Tetrabiblos",
        "book": "II",
        "chapter": "4",
        "category": "Mundane Astrology",
        "text": "Eclipses are the most powerful indicators in mundane astrology. Their effects extend over a period proportional to the duration of the eclipse: each hour of a solar eclipse corresponds to one year of effects; each hour of a lunar eclipse to one month.",
    },
    {
        "id": "ptolemy_mun_002",
        "source": "Ptolemy",
        "work": "Tetrabiblos",
        "book": "II",
        "chapter": "8",
        "category": "Mundane Astrology",
        "text": "The fixed stars of first magnitude, when in conjunction with planets, significantly modify the nature of events. Stars of the nature of Mars bring war and fire; those of Saturn, plague and famine; those of Jupiter, prosperity and peace.",
    },
]

# ─── Ptolemy on Elements and Qualities (Tetrabiblos I.2-3) ───────────────────

PTOLEMY_ELEMENTS = [
    {
        "id": "ptolemy_elem_001",
        "source": "Ptolemy",
        "work": "Tetrabiblos",
        "book": "I",
        "chapter": "2",
        "category": "Elements",
        "text": "The four qualities — hot, cold, moist, and dry — are the fundamental building blocks of astrological influence. Heat and moisture are generative and life-giving; cold and dryness are destructive and separative.",
    },
    {
        "id": "ptolemy_elem_002",
        "source": "Ptolemy",
        "work": "Tetrabiblos",
        "book": "I",
        "chapter": "3",
        "category": "Elements",
        "text": "Fire signs (Aries, Leo, Sagittarius) are hot and dry. Earth signs (Taurus, Virgo, Capricorn) are cold and dry. Air signs (Gemini, Libra, Aquarius) are hot and moist. Water signs (Cancer, Scorpio, Pisces) are cold and moist.",
    },
]


# ─── All Ptolemy Rules ───────────────────────────────────────────────────────

def get_all_ptolemy_rules() -> List[Dict[str, Any]]:
    """Return all Ptolemy rules as a flat list."""
    return (
        PTOLEMY_DIGNITIES +
        PTOLEMY_ASPECTS +
        PTOLEMY_PLANETS +
        PTOLEMY_SECT +
        PTOLEMY_NATAL +
        PTOLEMY_MUNDANE +
        PTOLEMY_ELEMENTS
    )


def get_ptolemy_rules_by_category(category: str) -> List[Dict[str, Any]]:
    """Get Ptolemy rules filtered by category."""
    return [r for r in get_all_ptolemy_rules() if r["category"] == category]


# ─── Statistics ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    rules = get_all_ptolemy_rules()
    categories = set(r["category"] for r in rules)
    print(f"Ptolemy (Tetrabiblos) Rules: {len(rules)}")
    for cat in sorted(categories):
        count = len([r for r in rules if r["category"] == cat])
        print(f"  {cat}: {count}")
