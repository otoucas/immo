# services/geocoding.py
from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple
import requests

from config import settings


def geocode_city(name: str) -> Optional[Dict[str, Any]]:
    """Geocode a French municipality using BAN (api-adresse).
    Returns dict with city, lat, lon, insee, bbox
    """
    params = {
        "q": name,
        "type": "municipality",
        "limit": 1,
    }
    r = requests.get(settings.BAN_SEARCH_URL, params=params, timeout=20)
    r.raise_for_status()
    js = r.json()
    feats = js.get("features", [])
    if not feats:
        return None
    f = feats[0]
    props = f.get("properties", {})
    lon, lat = f.get("geometry", {}).get("coordinates", [None, None])
    bbox = f.get("bbox")  # [minx, miny, maxx, maxy]
    return {
        "city": props.get("label") or name,
        "lat": lat,
        "lon": lon,
        "insee": props.get("citycode"),
        "bbox": bbox,
    }


def geocode_cities(cities: List[str]) -> List[Dict[str, Any]]:
    out = []
    for c in cities:
        try:
            g = geocode_city(c)
            if g:
                out.append(g)
        except Exception:
            # Ignore failing city, continue
            continue
    return out


def compute_cities_extent(geo: List[Dict[str, Any]]) -> Dict[str, float]:
    """Compute an extent that covers all cities.
    Returns dict with center_lat, center_lon, zoom_like, bbox
    """
    lats = [g["lat"] for g in geo if g.get("lat") is not None]
    lons = [g["lon"] for g in geo if g.get("lon") is not None]
    if not lats or not lons:
        return {"center_lat": 46.6, "center_lon": 2.6, "zoom_like": 5.0, "bbox": None}

    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)

    # bbox union
    minx = min((g["bbox"][0] for g in geo if g.get("bbox")), default=None)
    miny = min((g["bbox"][1] for g in geo if g.get("bbox")), default=None)
    maxx = max((g["bbox"][2] for g in geo if g.get("bbox")), default=None)
    maxy = max((g["bbox"][3] for g in geo if g.get("bbox")), default=None)

    # Simple zoom heuristic
    if None in (minx, miny, maxx, maxy):
        zoom_like = 8.0 if len(geo) == 1 else 6.0
    else:
        dx = maxx - minx
        dy = maxy - miny
        span = max(dx, dy)
        if span <= 0.2:
            zoom_like = 11
        elif span <= 0.5:
            zoom_like = 9
        elif span <= 1.5:
            zoom_like = 8
        elif span <= 3:
            zoom_like = 7
        else:
            zoom_like = 6

    return {
        "center_lat": center_lat,
        "center_lon": center_lon,
        "zoom_like": float(zoom_like),
        "bbox": [minx, miny, maxx, maxy] if None not in (minx, miny, maxx, maxy) else None,
    }
