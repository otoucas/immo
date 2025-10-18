# utils.py
import requests
import pandas as pd
import json
import os
from math import radians, sin, cos, sqrt, atan2
from typing import Optional, Tuple, List, Dict, Any

# -------------------------
# Fichier de sauvegarde des filtres
# -------------------------
FILTER_FILE = "saved_filters.json"

def save_filter(name: str, filters: dict):
    """Sauvegarde (ou remplace) un jeu de filtres sous le nom 'name'."""
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

def load_filters() -> Dict[str, dict]:
    """Retourne le dict de jeux de filtres sauvegardés."""
    if os.path.exists(FILTER_FILE):
        try:
            with open(FILTER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def delete_saved_filter(name: str):
    """Supprime un filtre enregistré par son nom."""
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
# Géocodage / Distance
# -------------------------
def geocode_city(city: str) -> Optional[Tuple[float, float]]:
    """Retourne (lat, lon) pour une ville via Nominatim (OpenStreetMap)."""
    try:
        url = "https://nominatim.openstreetmap.org/search"
        resp = requests.get(url, params={"q": city, "format": "json", "limit": 1}, headers={"User-Agent": "immo-app"}, timeout=10)
        resp.raise_for_status()
        js = resp.json()
        if js:
            return float(js[0]["lat"]), float(js[0]["lon"])
    except Exception:
        return None

def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance Haversine (km) entre deux points."""
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

# -------------------------
# Récupération ADEME (toutes les pages ou limité)
# -------------------------
def fetch_ademe_all(q: str = "", pages: Optional[int] = None, page_size: int = 300) -> pd.DataFrame:
    """Récupère les données du dataset DPE ADEME (toutes les pages ou limitées)."""
    base = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-france/records"
    all_rows = []
    page = 1
    while True:
        params = {"q": q, "size": page_size, "page": page}
        try:
            r = requests.get(base, params=params, timeout=30)
            if r.status_code != 200:
                break
            js = r.json()
        except Exception:
            break
        hits = js.get("results") or js.get("records") or js.get("data") or []
        if not hits:
            break
        for h in hits:
            if isinstance(h, dict) and "fields" in h and isinstance(h["fields"], dict):
                all_rows.append(h["fields"])
            elif isinstance(h, dict):
                all_rows.append(h)
        if pages and page >= pages:
            break
        page += 1
        if len(hits) < page_size:
            break
    if not all_rows:
        return pd.DataFrame()
    return pd.DataFrame(all_rows)

# -------------------------
# Historique des prix (DVF)
# -------------------------
def get_price_history(lat: float, lon: float, radius_m: int = 100) -> List[Dict[str, Any]]:
    """Récupère l'historique des ventes DVF proches d’un point."""
    try:
        url = "http://api.cquest.org/dvf"
        params = {"lat": lat, "lon": lon, "dist": radius_m}
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        js = r.json()
        records = js.get("resultats") or js.get("records") or js.get("rows") or js.get("data") or js.get("results") or js
        out = []
        if isinstance(records, list):
            for rec in records:
                out.append({
                    "date_mutation": rec.get("date_mutation"),
                    "valeur_fonciere": rec.get("valeur_fonciere"),
                    "type_local": rec.get("type_local"),
                    "surface_relle_bati": rec.get("surface_relle_bati"),
                    "adresse": rec.get("adresse") or rec.get("adresse_rep"),
                })
        return out
    except Exception:
        return []
