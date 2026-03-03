#!/usr/bin/env python3
"""
Timezone Manager for OpenClaw
==============================

Central timezone management with MST (UTC-7) as default.
Provides timezone detection, conversion, and MST-aware timestamp handling
for all memory operations across the system.

Author: Thia (OpenClaw Agent)
Date: 2026-02-12
Phase: STREAM A - Timezone & Temporal Intelligence
"""

from __future__ import annotations

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from pathlib import Path
from enum import Enum

try:
    import zoneinfo
    ZONEINFO_AVAILABLE = True
except ImportError:
    ZONEINFO_AVAILABLE = False
    # Fallback: dateutil would be used if available
    try:
        from dateutil import tz as dateutil_tz
        DATEUTIL_AVAILABLE = True
    except ImportError:
        DATEUTIL_AVAILABLE = False

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════

# Default timezone: Mountain Standard Time (MST = UTC-7)
# Note: During DST (MDT), this becomes UTC-6
MST_OFFSET = timedelta(hours=-7)
MDT_OFFSET = timedelta(hours=-6)

# Common timezone abbreviations to UTC offsets
TZ_ABBREVIATIONS: Dict[str, timedelta] = {
    'UTC': timedelta(0),
    'GMT': timedelta(0),
    'MST': MST_OFFSET,
    'MDT': MDT_OFFSET,
    'CST': timedelta(hours=-6),
    'CDT': timedelta(hours=-5),
    'EST': timedelta(hours=-5),
    'EDT': timedelta(hours=-4),
    'PST': timedelta(hours=-8),
    'PDT': timedelta(hours=-7),
    'AKST': timedelta(hours=-9),
    'AKDT': timedelta(hours=-8),
    'HST': timedelta(hours=-10),
    'CET': timedelta(hours=1),
    'CEST': timedelta(hours=2),
    'EET': timedelta(hours=2),
    'EEST': timedelta(hours=3),
    'JST': timedelta(hours=9),
    'AEST': timedelta(hours=10),
    'AEDT': timedelta(hours=11),
}


# ═══════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════

class TimezoneSource(Enum):
    """Source of timezone configuration."""
    DEFAULT = "default"           # System default MST
    SYSTEM = "system"             # Detected from system locale
    ENV = "environment"           # From environment variable
    CONFIG = "config"             # From config file
    USER = "user"                # Explicitly set by user


@dataclass
class TimezoneConfig:
    """Timezone configuration state."""
    default_tz: timezone          # Primary timezone (MST)
    system_tz: Optional[timezone] # Detected system timezone
    source: TimezoneSource         # How timezone was set
    dst_aware: bool = True       # Whether DST is considered

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'default_offset_hours': self.default_tz.utcoffset(datetime.now()).total_seconds() / 3600,
            'system_tz': str(self.system_tz) if self.system_tz is not None else None,
            'source': self.source.value,
            'dst_aware': self.dst_aware,
        }


# ═══════════════════════════════════════════════════════════════
# TIMEZONE MANAGER
# ═══════════════════════════════════════════════════════════════

class TimezoneManager:
    """
    Central timezone management for OpenClaw.

    Features:
    - Default MST (UTC-7) timezone for all operations
    - Automatic system timezone detection
    - Timezone conversion utilities
    - Memory timestamp handling in MST
    - DST-aware calculations
    """

    # Singleton instance
    _instance: Optional['TimezoneManager'] = None
    _config: TimezoneConfig = None

    def __new__(cls) -> 'TimezoneManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._config is None:
            self._config = self._detect_or_load_config()
            logger.info(f"TimezoneManager initialized: {self._config.default_tz}")

    @property
    def default_tz(self) -> timezone:
        """Get the default timezone (MST)."""
        return self._config.default_tz

    @property
    def system_tz(self) -> Optional[timezone]:
        """Get the detected system timezone."""
        return self._config.system_tz

    @property
    def config(self) -> TimezoneConfig:
        """Get the full configuration."""
        return self._config

    def _detect_or_load_config(self) -> TimezoneConfig:
        """
        Detect or load timezone configuration.

        Priority:
        1. Environment variable (OPENCLAW_TZ)
        2. System locale detection
        3. Default to MST
        """
        source = TimezoneSource.DEFAULT
        system_tz = None
        default_tz = timezone(MST_OFFSET)

        # Check environment variable
        env_tz = os.getenv('OPENCLAW_TZ', '').strip().upper()
        if env_tz:
            if env_tz in TZ_ABBREVIATIONS:
                default_tz = timezone(TZ_ABBREVIATIONS[env_tz])
                source = TimezoneSource.ENV
                logger.info(f"Using timezone from OPENCLAW_TZ: {env_tz}")
            elif ZONEINFO_AVAILABLE:
                try:
                    default_tz = zoneinfo.ZoneInfo(env_tz)
                    source = TimezoneSource.ENV
                    logger.info(f"Using timezone from OPENCLAW_TZ: {env_tz}")
                except Exception as e:
                    logger.warning(f"Invalid OPENCLAW_TZ value: {e}")

        # Detect system timezone if not from env
        if source == TimezoneSource.DEFAULT:
            detected_tz = self._detect_system_timezone()
            if detected_tz is not None:
                system_tz = detected_tz
                logger.info(f"Detected system timezone: {system_tz}")

        # DEBUG: Log types
        logger.debug(f"Config: source type = {type(source)}")
        logger.debug(f"Config: source value = {source}")

        return TimezoneConfig(
            default_tz=default_tz,
            system_tz=system_tz,
            source=source,
            dst_aware=True,
        )

    def _detect_system_timezone(self) -> Optional[timezone]:
        """
        Detect system timezone from locale/environment.

        Returns:
            System timezone or None if detection fails
        """
        # Try TZ environment variable
        tz_env = os.getenv('TZ')
        if tz_env:
            if tz_env in TZ_ABBREVIATIONS:
                return timezone(TZ_ABBREVIATIONS[tz_env])
            if ZONEINFO_AVAILABLE:
                try:
                    return zoneinfo.ZoneInfo(tz_env)
                except Exception:
                    pass

        # Try reading /etc/timezone on Linux
        try:
            timezone_path = Path('/etc/timezone')
            if timezone_path.exists():
                tz_name = timezone_path.read_text().strip()
                if ZONEINFO_AVAILABLE:
                    try:
                        return zoneinfo.ZoneInfo(tz_name)
                    except Exception:
                        pass
        except Exception:
            pass

        # Try reading /etc/localtime symlink
        try:
            localtime_path = Path('/etc/localtime')
            if localtime_path.is_symlink():
                target = localtime_path.resolve()
                # Extract timezone name from path like /usr/share/zoneinfo/America/Denver
                parts = target.parts
                if 'zoneinfo' in parts:
                    idx = parts.index('zoneinfo')
                    if idx + 1 < len(parts):
                        tz_name = '/'.join(parts[idx + 1:])
                        if ZONEINFO_AVAILABLE:
                            try:
                                return zoneinfo.ZoneInfo(tz_name)
                            except Exception:
                                pass
        except Exception:
            pass

        # Return MST as fallback to ensure we always return a valid timezone
        return timezone(MST_OFFSET)

    # ═══════════════════════════════════════════════════════════

    def now(self) -> datetime:
        """
        Get current time in default timezone.

        Returns:
            Current datetime in MST (or configured default)
        """
        return datetime.now(self.default_tz)

    def now_utc(self) -> datetime:
        """
        Get current time in UTC.

        Returns:
            Current datetime in UTC
        """
        return datetime.now(timezone.utc)

    def localize(self, dt: datetime) -> datetime:
        """
        Localize a naive datetime to the default timezone.

        Args:
            dt: Naive datetime (no timezone info)

        Returns:
            Datetime with default timezone applied
        """
        if dt.tzinfo is None:
            return dt.replace(tzinfo=self.default_tz)
        return dt

    def to_mst(self, dt: datetime) -> datetime:
        """
        Convert any datetime to MST (or configured default timezone).

        Args:
            dt: Input datetime with timezone info

        Returns:
            Datetime converted to MST
        """
        if dt.tzinfo is None:
            # Naive datetime - assume it's in the default timezone
            dt = dt.replace(tzinfo=self.default_tz)
        return dt.astimezone(self.default_tz)

    def to_utc(self, dt: datetime) -> datetime:
        """
        Convert any datetime to UTC.

        Args:
            dt: Input datetime

        Returns:
            Datetime converted to UTC
        """
        if dt.tzinfo is None:
            # Naive datetime - assume it's in the default timezone
            dt = dt.replace(tzinfo=self.default_tz)
        return dt.astimezone(timezone.utc)

    def convert(self, dt: datetime, target_tz: timezone) -> datetime:
        """
        Convert datetime to a specific timezone.

        Args:
            dt: Input datetime
            target_tz: Target timezone

        Returns:
            Datetime converted to target timezone
        """
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=self.default_tz)
        return dt.astimezone(target_tz)

    def parse_timezone(self, tz_str: str) -> Optional[timezone]:
        """
        Parse a timezone string into a timezone object.

        Args:
            tz_str: Timezone string (e.g., 'MST', 'UTC', 'America/Denver')

        Returns:
            Timezone object or None if parsing fails
        """
        if not tz_str:
            return None
            
        tz_raw = tz_str.strip()
        tz_upper = tz_raw.upper()

        # 1. Try common abbreviations (case-insensitive)
        if tz_upper in TZ_ABBREVIATIONS:
            return timezone(TZ_ABBREVIATIONS[tz_upper])

        # 2. Try zoneinfo (case-sensitive for IANA names)
        if ZONEINFO_AVAILABLE:
            try:
                # Try raw string (e.g., 'America/New_York')
                return zoneinfo.ZoneInfo(tz_raw)
            except Exception:
                try:
                    # Try title case (e.g., 'Europe/London')
                    return zoneinfo.ZoneInfo(tz_raw.title())
                except Exception:
                    pass

        # 3. Try UTC/GMT offset format (+07:00, -0700, GMT-5, etc.)
        offset_part = tz_upper
        if offset_part.startswith(('GMT', 'UTC')):
            offset_part = offset_part[3:]
            
        if offset_part.startswith(('+', '-')):
            try:
                # Normalize format to HH:MM
                clean_offset = offset_part
                if ':' not in clean_offset:
                    if len(clean_offset) == 5:  # +0700
                        clean_offset = clean_offset[:3] + ':' + clean_offset[3:]
                    elif len(clean_offset) == 4:  # +700
                        clean_offset = clean_offset[:2] + ':' + clean_offset[2:]
                    elif len(clean_offset) == 3:  # +05
                        clean_offset = clean_offset + ':00'

                hours = int(clean_offset[:3])
                minutes = int(clean_offset[4:6]) if len(clean_offset) > 4 else 0
                total_seconds = hours * 3600 + minutes * 60
                return timezone(timedelta(seconds=total_seconds))
            except Exception:
                pass

        logger.warning(f"Failed to parse timezone string: '{tz_str}'")
        return None

    def format_with_tz(self, dt: datetime, tz: Optional[timezone] = None,
                       fmt: str = '%Y-%m-%d %H:%M:%S %Z') -> str:
        """
        Format datetime with timezone abbreviation.

        Args:
            dt: Datetime to format
            tz: Target timezone (uses default if None)
            fmt: Format string

        Returns:
            Formatted datetime string
        """
        if tz is None:
            tz = self.default_tz

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=self.default_tz)

        dt_local = dt.astimezone(tz)

        # Get timezone abbreviation
        offset = dt_local.utcoffset()
        if offset is None:
            tz_abbr = '???'
        else:
            offset_hours = offset.total_seconds() / 3600
            # Find matching abbreviation
            tz_abbr = None
            for abbr, abbr_offset in TZ_ABBREVIATIONS.items():
                if abbr_offset.total_seconds() / 3600 == offset_hours:
                    tz_abbr = abbr
                    break
            if tz_abbr is None:
                tz_abbr = f"UTC{'+' if offset_hours >= 0 else ''}{int(offset_hours)}"

        return dt_local.strftime(fmt.replace('%Z', tz_abbr))

    # ═══════════════════════════════════════════════════════════

    def get_mst_offset(self, dt: Optional[datetime] = None) -> timedelta:
        """
        Get MST/MDT offset for a given date (accounts for DST).

        Args:
            dt: Date to check (uses current if None)

        Returns:
            UTC offset (either -7 for MST or -6 for MDT)
        """
        if dt is None:
            dt = datetime.now(timezone.utc)

        # DST in US Mountain Time: Second Sunday March to First Sunday November
        # Approximate calculation (good enough for most use cases)
        if not self._config.dst_aware:
            return MST_OFFSET

        # Simple DST heuristic for Mountain Time
        # DST: March (3) to November (11)
        if dt.month < 3 or dt.month > 11:
            return MST_OFFSET  # Standard time
        if dt.month > 3 and dt.month < 11:
            return MDT_OFFSET  # Daylight time

        # March and November boundary checks would go here for exact calculation
        # For simplicity, use MST for now
        return MST_OFFSET

    def is_dst(self, dt: Optional[datetime] = None) -> bool:
        """
        Check if DST is active for a given date.

        Args:
            dt: Date to check (uses current if None)

        Returns:
            True if DST (MDT) is active
        """
        return self.get_mst_offset(dt) == MDT_OFFSET

    # ═══════════════════════════════════════════════════════════

    def create_timestamp(self) -> str:
        """
        Create a current timestamp in ISO format with MST timezone.

        Returns:
            ISO format timestamp string
        """
        return self.now().isoformat()

    def create_timestamp_utc(self) -> str:
        """
        Create a current timestamp in ISO format with UTC timezone.

        Returns:
            ISO format timestamp string
        """
        return self.now_utc().isoformat()

    def parse_timestamp(self, ts: str) -> datetime:
        """
        Parse an ISO timestamp string, defaulting to MST if naive.

        Args:
            ts: ISO format timestamp string

        Returns:
            Datetime object
        """
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = self.localize(dt)
            return dt
        except Exception as e:
            logger.warning(f"Failed to parse timestamp '{ts}': {e}")
            return self.now()


# ═══════════════════════════════════════════════════════════════
# SINGLETON ACCESSOR
# ═══════════════════════════════════════════════════════════════

_manager: Optional[TimezoneManager] = None


def get_timezone_manager() -> TimezoneManager:
    """Get the singleton TimezoneManager instance."""
    global _manager
    if _manager is None:
        _manager = TimezoneManager()
    return _manager


def set_timezone(tz_str: str) -> bool:
    """
    Set a new default timezone.

    Args:
        tz_str: Timezone string (e.g., 'MST', 'UTC', 'America/Denver')

    Returns:
        True if timezone was set successfully
    """
    manager = get_timezone_manager()
    tz = manager.parse_timezone(tz_str)

    if tz is None:
        logger.error(f"Failed to parse timezone: {tz_str}")
        return False

    # Update configuration
    manager._config.default_tz = tz
    manager._config.source = TimezoneSource.USER
    logger.info(f"Timezone updated to: {tz}")
    return True


# ═══════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════

__all__ = [
    'TimezoneManager',
    'TimezoneConfig',
    'TimezoneSource',
    'get_timezone_manager',
    'set_timezone',
    'MST_OFFSET',
    'MDT_OFFSET',
    'TZ_ABBREVIATIONS',
]
# Test write access
