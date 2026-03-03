import pytest
from thia_lite.engines.profections import calculate_profections

def test_annual_profection():
    result = calculate_profections(
        natal_timestamp="1990-01-15T12:00:00Z",
        natal_latitude=40.7128,
        natal_longitude=-74.0060,
        target_timestamp="2026-03-01T12:00:00Z",
        profection_type="annual"
    )
    
    assert "annual_profection" in result
    assert "profection_year" in result["annual_profection"]
    assert result["target"]["age_at_target"] >= 36.0
