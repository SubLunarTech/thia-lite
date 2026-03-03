import pytest
from thia_lite.engines.astrology import _astrology_dispatch

def test_calculate_natal_chart():
    # Test a basic natal chart via dispatcher
    result = _astrology_dispatch("calculate_natal_chart", {
        "date": "1990-01-15",
        "time": "14:30",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "timezone": "America/New_York"
    })
    
    # Missing explicit 'data' wrapper, returns direct dict
    assert "houses" in result
    assert "chart_type" in result

