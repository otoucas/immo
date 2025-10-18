import requests
import pandas as pd
from math import radians, cos, sin, sqrt, atan2

def geocode_city(city):
    """Retourne les coordonnées (lat, lon) d'une ville via Nominatim."""
    url = f"https://nominatim.openstreetmap.org/search?q={city}&format=json&limit=1"
    try:
        r = requests.get(url, headers={"User-Agent": "immo-app"})
        r.raise_for_status()
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        return None
    return None


def distance_km(lat1, lon1, lat2, lon2):
    """Distance entre deux points en km (Haversine)."""
    R = 6371
    d_lat, d_lon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(d_lat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def fetch_ademe_all(city_coords, rayon_km=10):
    """Récupère toutes les pages de l'API ADEME pour une ou plusieurs villes."""
    dfs = []
    base_url = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-france/lines"
    for city, (lat, lon) in city_coords:
        offset, limit = 0, 1000
        while True:
            params = {
                "size": limit,
                "from": offset,
                "geofilter.distance": f"{lat},{lon},{rayon_km*1000}"
            }
            try:
                r = requests.get(base_url, params=params, timeout=20)
                r.raise_for_status()
                data = r.json()
                records = data.get("results", [])
                if not records:
                    break
                df = pd.DataFrame(records)
                dfs.append(df)
                offset += limit
            except Exception:
                break
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
