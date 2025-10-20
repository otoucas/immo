# core/geodata.py
import streamlit as st
import requests
import math
import pandas as pd


@st.cache_data(ttl=3600)
def geocode_city(ville: str):
    """Retourne les coordonnées et code postal via geo.api.gouv.fr."""
    try:
        url = f"https://api-adresse.data.gouv.fr/search/?q={ville}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data["features"]:
                feat = data["features"][0]
                props = feat["properties"]
                coords = feat["geometry"]["coordinates"]
                return {
                    "lat": coords[1],
                    "lon": coords[0],
                    "code_postal": props.get("postcode"),
                }
    except Exception:
        return None
    return None


@st.cache_data(ttl=3600)
def get_postal_codes_from_radius(lat, lon, rayon_km: float):
    """Renvoie la liste des codes postaux dans un rayon donné."""
    url = "https://geo.api.gouv.fr/communes"
    try:
        r = requests.get(
            url,
            params={
                "lat": lat,
                "lon": lon,
                "fields": "codesPostaux",
                "geometry": "centre",
                "format": "json",
                "radius": int(rayon_km * 1000),
            },
            timeout=5,
        )
        if r.status_code == 200:
            data = r.json()
            codes = []
            for c in data:
                for cp in c.get("codesPostaux", []):
                    if cp not in codes:
                        codes.append(cp)
            return codes
    except Exception:
        return []
    return []


def haversine(lat1, lon1, lat2, lon2):
    """Calcul de distance en km entre deux coordonnées."""
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def filter_ademe_data_by_radius(df: pd.DataFrame, lat, lon, radius_km):
    """Filtre un DataFrame ADEME selon un rayon géographique."""
    if df.empty or "latitude" not in df.columns or "longitude" not in df.columns:
        return df

    df = df.copy()
    df["distance_km"] = df.apply(
        lambda r: haversine(lat, lon, r["latitude"], r["longitude"]), axis=1
    )
    return df[df["distance_km"] <= radius_km]
