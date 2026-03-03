import pytest
from thia_lite.engines.fixed_stars import list_fixed_stars

def test_fixed_stars():
    result = list_fixed_stars()
    ids = [star["id"].lower() for star in result]
    assert "aldebaran" in ids
    assert "regulus" in ids
