    # utils.py
import requests
import pandas as pd
import json
import os
import re
from math import radians, sin, cos, sqrt, atan2
from typing import Optional, Tuple

FILTER_FILE = "saved_filters.json"

# -------------------------
# Sauvegarde / chargement filtres
# -------------------------
def save_filters(name: str, filters: dict):
    """Sauvegarde un jeu de filtres sous un nom."""
    saved = {}
    if os.path.exists(FILTER_FILE):
        try:
            with open(FILTER_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
        except Exception:
            saved = {}
    saved[name] = filters
    with open(FILTER_FILE, "w", encoding="utf-8") as f:
        json.dump(saved, f, ensure_ascii=False, indent=2)

def load_filters() -> dict:
    """Retourne le dict de jeux de filtres sauvegardés (possiblement vide)."""
    if os.path.exists(FILTER_FILE):
        try:
            with open(FILTER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def delete_filter(name: str):
    """Supprime un jeu de filtres."""
    if not os.path.exists(FILTER_FILE):
        return
    try:
        with open(FILTER_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
    except Exception:
        saved = {}
    if name in saved:
        del saved[name]
        with open(FILTER_FILE, "w", encoding="utf-8") as f:
            json.dump(saved, f, ensure_ascii=False, indent=2)

# -------------------------
# Géocodage et distance
# -------------------------
def geocode_city(city: str) -> Optional[Tuple[float, float]]:
    """Retourne (lat, lon) pour le centre d'une ville via Nominatim (OpenStreetMap)."""
    try:
        url = "https://nominatim.openstreetmap.org/search"
        resp = requests.get(url, params={"q": city, "format": "json", "limit": 1}, headers={"User-Agent": "immo-app"}, timeout=10)
        resp.raise_for_status()
        js = resp.json()
        if js:
            return float(js[0]["lat"]), float(js[0]["lon"])
    except Exception:
        return None
    return None

def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Retourne la distance en kilomètres entre deux points WGS84 (Haversine)."""
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

# -------------------------
# Recherche / pagination ADEME
# -------------------------
def fetch_ademe_all(q: str = "", pages: Optional[int] = None, page_size: int = 300):
    """
    Récupère les enregistrements ADEME (dataset dpe-france).
    - q: terme de recherche (ville / code postal / texte)
    - pages: nombre de pages à récupérer (None = récupérer jusqu'à épuisement)
    - page_size: nombre d'items par page (max 300 si l'API le supporte)
    Retourne un DataFrame pandas (vide si aucun résultat).
    """
    base = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-france/lines"
    all_rows = []
    page = 1
    while True:
        params = {"q": q, "size": page_size, "page": page}
        try:
            resp = requests.get(base, params=params, timeout=20)
            if resp.status_code != 200:
                break
            data = resp.json()
        except Exception:
            break

        # endpoint 'lines' returns list of dict entries
        results = data.get("results") or data.get("data") or data.get("rows") or []
        if not results:
            break

        # ensure we append the actual dicts (fields vary by endpoint)
        for r in results:
            if isinstance(r, dict):
                all_rows.append(r)
            else:
                # fallback: try to coerce
                try:
                    all_rows.append(dict(r))
                except Exception:
                    pass

        # stop conditions
        if pages and page >= pages:
            break
        page += 1

        # if API returns less than a full page, assume last
        if len(results) < page_size:
            break

    # normaliser : si les rows ont une clé "fields" (comme 'records' endpoint), unwrap
    normalized = []
    for r in all_rows:
        if isinstance(r, dict) and "fields" in r and isinstance(r["fields"], dict):
            normalized.append(r["fields"])
        else:
            normalized.append(r)

    if normalized:
        return pd.DataFrame(normalized)
    return pd.DataFrame()

# -------------------------
# (Optionnel) parse minimal si tu veux récupérer une page HTML
# -------------------------
# On supprime l'extraction Leboncoin dans cette version (tu as demandé de la retirer).
# Si tu veux la remettre, on peut l'ajouter séparément.
