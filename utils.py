import os
import json
import math
import requests
from typing import List, Tuple, Optional
import pandas as pd


FILTERS_FILE = "saved_filters.json"


# ----------------------------
# Sauvegarde / chargement des filtres
# ----------------------------
def save_filter(name: str, filters: dict):
    data = load_filters()
    data[name] = filters
    with open(FILTERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_filters() -> dict:
    if not os.path.exists(FILTERS_FILE):
        return {}
    with open(FILTERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def delete_saved_filter(name: str):
    data = load_filters()
    if name in data:
        del data[name]
        with open(FILTERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# ----------------------------
# Fonctions géographiques
# ----------------------------
def geocode_city(ville: str):
    try:
        url = "https://nominatim.openstreetmap.org/search"
        resp = requests.get(url, params={"q": ville, "format": "json", "limit": 1}, timeout=10)
        if resp.status_code == 200 and len(resp.json()) > 0:
            j = resp.json()[0]
            return float(j["lat"]), float(j["lon"])
    except Exception:
        pass
    return None, None


def compute_barycenter(cities: List[str]) -> Optional[Tuple[float, float]]:
    coords = []
    for c in cities:
        lat, lon = geocode_city(c)
        if lat and lon:
            coords.append((lat, lon))
    if not coords:
        return None
    lat_mean = sum(x[0] for x in coords) / len(coords)
    lon_mean = sum(x[1] for x in coords) / len(coords)
    return lat_mean, lon_mean


def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def filter_ademe_data_by_radius(df, lat, lon, radius_km):
    df = df.copy()
    df["distance_km"] = df.apply(
        lambda r: haversine(lat, lon, r["latitude"], r["longitude"]), axis=1
    )
    return df[df["distance_km"] <= radius_km]

def get_postal_codes_in_radius(center_coords, rayon_km):
    """
    Retourne les codes postaux dans un rayon autour d’un point donné.
    (approximation simple via bounding box + API adresse.gouv.fr)
    """
    try:
        lat, lon = center_coords
        delta = rayon_km / 111  # conversion km → degré approx.
        bbox = f"{lon - delta},{lat - delta},{lon + delta},{lat + delta}"

        url = "https://geo.api.gouv.fr/communes"
        params = {"bbox": bbox, "format": "json"}
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            return []

        communes = resp.json()
        return [str(c["codesPostaux"][0]) for c in communes if "codesPostaux" in c]
    except Exception as e:
        print("Erreur dans get_postal_codes_in_radius:", e)
        return []

# ----------------------------
# API ADEME
# ----------------------------
def fetch_ademe_all(code_postaux: List[str], page_limit=None):
    base_url = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-france/records"
    all_rows = []
    for cp in code_postaux:
        start = 0
        page = 1
        while True:
            params = {"q": cp, "size": 100, "from": start}
            resp = requests.get(base_url, params=params, timeout=20)
            if resp.status_code != 200:
                break
            rows = resp.json().get("results", [])
            if not rows:
                break
            all_rows.extend(rows)
            if page_limit and page >= page_limit:
                break
            if len(rows) < 100:
                break
            start += 100
            page += 1
    df = pd.DataFrame(all_rows)
    if "geometry" in df.columns:
        df["latitude"] = df["geometry"].apply(lambda g: g["coordinates"][1] if g else None)
        df["longitude"] = df["geometry"].apply(lambda g: g["coordinates"][0] if g else None)
    return df


# ----------------------------
# DVF : historique des ventes
# ----------------------------
def get_dvf_data(code_postal, voie=None, limit=5):
    try:
        base_url = "https://api-dvf.data.gouv.fr/search"
        params = {"code_postal": code_postal, "nombre_resultats": limit}
        if voie:
            params["voie"] = voie
        response = requests.get(base_url, params=params, timeout=10)
        if response.status_code != 200:
            return []
        data = response.json().get("resultats", [])
        ventes = []
        for v in data:
            ventes.append({
                "date": v.get("date_mutation", ""),
                "valeur_fonciere": v.get("valeur_fonciere", 0),
                "surface": v.get("surface_reelle_bati", 0),
                "type": v.get("type_local", "")
            })
        return ventes
    except Exception as e:
        print("Erreur DVF:", e)
        return []


# ----------------------------
# Calque GeoJSON : contours codes postaux
# ----------------------------
def get_postalcode_geojson(code_postaux: List[str]):
    """Récupère les géométries des communes correspondant aux codes postaux"""
    try:
        url = "https://etalab.github.io/geojson/communes.geojson"
        resp = requests.get(url, timeout=20)
        if resp.status_code != 200:
            return None
        geo = resp.json()
        filtered_features = [
            f for f in geo["features"]
            if f["properties"].get("codePostal") in code_postaux
        ]
        if not filtered_features:
            return None
        return {"type": "FeatureCollection", "features": filtered_features}
    except Exception as e:
        print("Erreur GeoJSON:", e)
        return None
