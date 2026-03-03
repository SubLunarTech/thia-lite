import pytest
from thia_lite.engines.vedic_astrology import calculate_nakshatra

def test_nakshatra():
    result = calculate_nakshatra(longitude=45.0)
    assert "name" in result
    assert "pada" in result
    assert "ruler" in result
