import requests
import pandas as pd
import json
import re
import os
from math import radians, sin, cos, sqrt, atan2
from bs4 import BeautifulSoup

# ------------------------------------------------------------
# GESTION DES FILTRES (sauvegarde / chargement)
# ------------------------------------------------------------
FILTER_FILE = "saved_filters.json"

def save_filters(filters: dict):
    try:
        with open(FILTER_FILE, "w", encoding="utf-8") as f:
            json.dump(filters, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erreur de sauvegarde des filtres : {e}")

def load_filters() -> dict:
    if os.path.exists(FILTER_FILE):
        try:
            with open(FILTER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

# ------------------------------------------------------------
# OUTILS GÉOGRAPHIQUES
# ------------------------------------------------------------
def geocode_city(ville):
    """Retourne (lat, lon) pour une ville via Nominatim."""
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={ville}&format=json&limit=1"
        r = requests.get(url, headers={"User-Agent": "immo-app"})
        r.raise_for_status()
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        return None

def distance_km(lat1, lon1, lat2, lon2):
    """Calcule la distance (km) entre deux points."""
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))

# ------------------------------------------------------------
# EXTRACTION LEBONCOIN
# ------------------------------------------------------------
def parse_leboncoin_html(url):
    """Extrait des infos de base depuis une annonce LeBonCoin."""
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    data = {}
    # Titre
    title = soup.find("h1")
    if title:
        data["titre"] = title.text.strip()

    # Prix
    price_tag = soup.find(string=re.compile("€"))
    if price_tag:
        data["prix"] = re.sub(r"[^\d]", "", price_tag)

    # Surface
    surf = soup.find(string=re.compile("m²"))
    if surf:
        try:
            data["surface"] = int(re.search(r"(\d+)\s*m²", surf).group(1))
        except Exception:
            pass

    # Ville / CP
    loc = soup.find(string=re.compile(r"\d{5}"))
    if loc:
        data["code_postal"] = re.search(r"(\d{5})", loc).group(1)
        data["ville"] = loc.split(data["code_postal"])[0].strip(" ,")

    return data

# ------------------------------------------------------------
# RECHERCHE ADEME
# ------------------------------------------------------------
def fetch_ademe_all(q, pages=3):
    """Récupère les données Open Data ADEME (diagnostics DPE)."""
    url = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-france/records"
    all_rows = []
    for page in range(1, pages + 1):
        params = {
            "q": q,
            "size": 100,
            "page": page,
        }
        r = requests.get(url, params=params)
        if r.status_code != 200:
            break
        js = r.json()
        hits = js.get("results", [])
        if not hits:
            break
        for h in hits:
            fields = h.get("fields", {})
            all_rows.append(fields)
    if all_rows:
        return pd.DataFrame(all_rows)
    return pd.DataFrame()
