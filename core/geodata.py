import math
import pandas as pd
import requests

def haversine(lat1, lon1, lat2, lon2):
    if any(pd.isna([lat1, lon1, lat2, lon2])):
        return float("nan")
    try:
        lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
        c = 2 * math.asin(math.sqrt(a))
        return 6371 * c
    except Exception:
        return float("nan")

def geocode_city(ville):
    try:
        url = "https://api-adresse.data.gouv.fr/search/"
        resp = requests.get(url, params={"q": ville, "type": "municipality"}, timeout=10)
        js = resp.json()
        if js["features"]:
            f = js["features"][0]
            return {
                "lat": f["geometry"]["coordinates"][1],
                "lon": f["geometry"]["coordinates"][0],
                "code_postal": f["properties"].get("postcode"),
            }
    except Exception:
        pass
    return None

def compute_barycenter(cities):
    coords = []
    for v in cities:
        g = geocode_city(v)
        if g:
            coords.append((g["lat"], g["lon"]))
    if not coords:
        return None
    lat = sum(c[0] for c in coords) / len(coords)
    lon = sum(c[1] for c in coords) / len(coords)
    return (lat, lon)

def filter_ademe_data_by_radius(df, lat, lon, radius_km):
    df = df.copy()
    if "latitude" not in df or "longitude" not in df:
        return df.iloc[0:0]
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"])
    df["distance_km"] = df.apply(lambda r: haversine(lat, lon, r["latitude"], r["longitude"]), axis=1)
    return df[df["distance_km"] <= radius_km].reset_index(drop=True)

def get_postal_codes_in_radius(center_coords, rayon_km):
    try:
        lat, lon = center_coords
        delta = rayon_km / 111
        bbox = f"{lon - delta},{lat - delta},{lon + delta},{lat + delta}"
        url = "https://geo.api.gouv.fr/communes"
        params = {"bbox": bbox, "format": "json"}
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            return []
        communes = resp.json()
        return [c["codesPostaux"][0] for c in communes if "codesPostaux" in c]
    except Exception:
        return []
