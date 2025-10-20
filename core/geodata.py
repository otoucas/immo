# core/geodata.py
import requests
import pandas as pd
from math import radians, cos, sin, asin, sqrt


def geocode_city(city_name: str):
    """Renvoie lat/lon/code_postal d'une ville via l'API geo.api.gouv.fr"""
    try:
        url = "https://geo.api.gouv.fr/communes"
        params = {"nom": city_name, "fields": "centre,code,codeDepartement,codeRegion,codesPostaux", "format": "json"}
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if not data:
            return None
        city = data[0]
        return {
            "lat": city["centre"]["coordinates"][1],
            "lon": city["centre"]["coordinates"][0],
            "code_postal": city["codesPostaux"][0] if city.get("codesPostaux") else None,
        }
    except Exception:
        return None


def compute_barycenter(villes: list):
    """Calcule le barycentre (lat, lon) d'une liste de villes"""
    coords = []
    for v in villes:
        city_name = v.split("(")[0].strip()
        g = geocode_city(city_name)
        if g:
            coords.append((g["lat"], g["lon"]))
    if not coords:
        return None
    lat = sum(c[0] for c in coords) / len(coords)
    lon = sum(c[1] for c in coords) / len(coords)
    return (lat, lon)


def haversine(lat1, lon1, lat2, lon2):
    """Calcule la distance en km entre deux points géographiques"""
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return R * 2 * asin(sqrt(a))


def filter_ademe_data_by_radius(df: pd.DataFrame, lat, lon, radius_km):
    """Filtre un DataFrame ADEME pour ne garder que les logements dans un rayon (km)"""
    df = df.copy()
    if "latitude" not in df.columns or "longitude" not in df.columns:
        return df
    df["distance_km"] = df.apply(
        lambda r: haversine(lat, lon, r["latitude"], r["longitude"]), axis=1
    )
    return df[df["distance_km"] <= radius_km]
