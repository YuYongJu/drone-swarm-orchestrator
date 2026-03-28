"""Shared geographic utility functions."""

import math

from .drone import Waypoint


def haversine(lat1, lon1, lat2, lon2) -> float:
    """Distance in meters between two GPS points."""
    earth_r = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return earth_r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def offset_gps(lat, lon, alt, north_m, east_m) -> Waypoint:
    """Offset a GPS point by meters in NED frame."""
    d_lat = north_m / 111_320.0
    m_lon = meters_per_deg_lon(lat)
    d_lon = east_m / m_lon if m_lon > 1e-3 else 0.0
    return Waypoint(lat=lat + d_lat, lon=lon + d_lon, alt=alt)


def meters_per_deg_lat() -> float:
    return 111_320.0


def meters_per_deg_lon(lat: float) -> float:
    """Metres per degree of longitude, clamped to avoid near-zero at poles."""
    clamped = max(-89.999, min(89.999, lat))
    return 111_320.0 * math.cos(math.radians(clamped))
