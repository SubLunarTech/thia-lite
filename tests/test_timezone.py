import pytest
from datetime import datetime, timezone
from thia_lite.engines.timezone_manager import TimezoneManager

def test_timezone_resolution():
    tzm = TimezoneManager()
    
    # Check timezone parsing
    tz_ny = tzm.parse_timezone("America/New_York")
    assert tz_ny is not None
    
    # Check localization to UTC
    dt_local = datetime(1990, 1, 15, 14, 30)
    dt_localized = dt_local.replace(tzinfo=tz_ny)
    dt_utc = tzm.to_utc(dt_localized)
    
    assert dt_utc.year == 1990
    assert dt_utc.month == 1
    assert dt_utc.day == 15
    assert dt_utc.hour == 19  # 14:30 EST is 19:30 UTC
    assert dt_utc.minute == 30
