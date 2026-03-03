import pytest
from thia_lite.engines.financial_astrology import calculate_square_of_9

def test_gann_square():
    result = calculate_square_of_9(price=100)
    assert "origin_price" in result
    assert result["origin_price"] == 100
    assert "levels" in result
