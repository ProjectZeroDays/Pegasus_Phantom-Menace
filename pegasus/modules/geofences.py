"""Geofences module for Pegasus Phantom Menace."""
from __future__ import annotations

from typing import List, Dict, Any
import uuid

# In-memory storage for geofences
_geofences: List[Dict[str, Any]] = []
_fence_id_counter = 1


def list_geofences(serial: str) -> List[Dict[str, Any]]:
    """List geofences for a device."""
    return [g for g in _geofences if g.get("serial") == serial]


def create_geofence(serial: str, name: str, lat: float, lng: float, radius_meters: float) -> Dict[str, Any]:
    """Create a new geofence."""
    global _fence_id_counter
    
    # Validate coordinates
    try:
        lat_val = float(lat)
        lng_val = float(lng)
        if not (-90 <= lat_val <= 90) or not (-180 <= lng_val <= 180):
            return {"success": False, "error": "Invalid coordinates"}
    except (ValueError, TypeError):
        return {"success": False, "error": "Invalid coordinates"}
    
    fence = {
        "id": _fence_id_counter,
        "serial": serial,
        "name": name,
        "lat": lat_val,
        "lng": lng_val,
        "radiusMeters": radius_meters,
    }
    _fence_id_counter += 1
    _geofences.append(fence)
    return fence


def toggle_geofence(fence_id: int) -> bool:
    """Toggle a geofence."""
    for fence in _geofences:
        if fence["id"] == fence_id:
            fence["enabled"] = not fence.get("enabled", True)
            return True
    return False


def delete_geofence(fence_id: int) -> bool:
    """Delete a geofence."""
    global _geofences
    for i, fence in enumerate(_geofences):
        if fence["id"] == fence_id:
            del _geofences[i]
            return True
    return False