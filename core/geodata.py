# core/geodata.py (ajouts / remplacements)
import requests
import pandas as pd
import math

# ... (tes autres fonctions: haversine, geocode_city, compute_barycenter, etc.)

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
