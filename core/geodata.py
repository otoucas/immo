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

def _nearby_communes_by_radius(center_coords, rayon_km):
    """
    Tente d'utiliser lat/lon/radius de l'API communes.
    Fallback auto sur bbox si non supporté.
    Retourne une liste de communes (dict) avec leurs codesPostaux.
    """
    lat, lon = center_coords
    radius_m = int(rayon_km * 1000)

    # 1) Essai lat/lon/radius
    try:
        url = "https://geo.api.gouv.fr/communes"
        params = {
            "lat": lat,
            "lon": lon,
            "fields": "nom,code,codesPostaux,centre",
            "geometry": "centre",
            "format": "json",
            "radius": radius_m,
        }
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass

    # 2) Fallback bbox (approx)
    try:
        delta = rayon_km / 111.0
        bbox = f"{lon - delta},{lat - delta},{lon + delta},{lat + delta}"
        params = {
            "bbox": bbox,
            "fields": "nom,code,codesPostaux,centre",
            "geometry": "centre",
            "format": "json",
        }
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass

    return []


def get_postal_codes_in_radius(center_coords, rayon_km):
    """
    Retourne la liste UNIQUE des codes postaux dont la commune est située
    dans le rayon (lat/lon/radius) autour du point donné.
    """
    communes = _nearby_communes_by_radius(center_coords, rayon_km)
    cps = []
    for c in communes:
        for cp in c.get("codesPostaux", []):
            cps.append(str(cp))
    # unicité + tri
    return sorted(set(cps))
