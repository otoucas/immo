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
    """
    Interroge l'API ADEME (dataset dpe-france). 
    - q: chaîne de recherche (ville, cp, ...)
    - pages: None => récupérer jusqu'à épuisement ; sinon nombre de pages max
    - page_size: taille page (max 300 par requête si l'API supporte)
    """
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

        # l'API peut retourner sous "results" ou "records" selon endpoint
        hits = js.get("results") or js.get("records") or js.get("data") or []
        if not hits:
            break

        for h in hits:
            # certains endpoints retournent {"fields": {...}}
            if isinstance(h, dict) and "fields" in h and isinstance(h["fields"], dict):
                all_rows.append(h["fields"])
            elif isinstance(h, dict):
                all_rows.append(h)
            else:
                # skip unknown structure
                pass

        # stop if requested number of pages reached
        if pages and page >= pages:
            break
        page += 1

        # if returned less than a full page, likely finished
        if isinstance(hits, list) and len(hits) < page_size:
            break

    if not all_rows:
        return pd.DataFrame()
    df = pd.DataFrame(all_rows)
    # Normalize common fields: try to find lat/lon keys if nested
    # Keep as-is; calling code will coerce types and fill missing columns
    return df

# -------------------------
# Historique des prix (DVF) — tentative via micro-API cquest
# -------------------------
def get_price_history(lat: float, lon: float, radius_m: int = 100) -> List[Dict[str, Any]]:
    """
    Tente de récupérer l'historique des transactions DVF proches d'un point.
    Utilise l'API publique cquest (micro-API) si disponible :
      http://api.cquest.org/dvf?lat=...&lon=...&dist=...
    Retourne une liste de transactions {date_mutation, valeur_fonciere, type_local, surface_relle_bati, adresse (si dispo)}.
    Si l'API n'est pas disponible, retourne [].
    """
    try:
        url = "http://api.cquest.org/dvf"
        params = {"lat": lat, "lon": lon, "dist": radius_m}
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        js = r.json()
        # plusieurs micro-apis renvoient 'resultats' ou 'records' ou direct list
        records = js.get("resultats") or js.get("records") or js.get("rows") or js.get("data") or js.get("results") or js
        # Convert to list of dicts if necessary
        out = []
        if isinstance(records, list):
            for rec in records:
                # mapping best-effort
                try:
                    out.append({
                        "date_mutation": rec.get("date_mutation") or rec.get("date_mut"),
                        "valeur_fonciere": rec.get("valeur_fonciere") or rec.get("valeur"),
                        "type_local": rec.get("type_local"),
                        "surface_relle_bati": rec.get("surface_relle_bati") or rec.get("surface"),
                        "adresse": rec.get("adresse") or rec.get("adresse_rep"),
                    })
                except Exception:
                    continue
        return out
    except Exception:
        return []
