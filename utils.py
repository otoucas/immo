import requests
import pandas as pd
import json
import os
import re
from math import radians, sin, cos, sqrt, atan2
from bs4 import BeautifulSoup

# ----------------------------
# Sauvegarde / chargement filtres
# ----------------------------
FILTER_FILE = "saved_filters.json"

def save_filters(filters: dict):
    try:
        with open(FILTER_FILE, "w", encoding="utf-8") as f:
            json.dump(filters, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erreur de sauvegarde : {e}")

def load_filters() -> dict:
    if os.path.exists(FILTER_FILE):
        try:
            with open(FILTER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

# ----------------------------
# Géocodage et distance
# ----------------------------
def geocode_city(ville):
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={ville}&format=json&limit=1"
        r = requests.get(url, headers={"User-Agent": "immo-app"})
        r.raise_for_status()
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except:
        return None

def distance_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))

# ----------------------------
# Extraction Leboncoin
# ----------------------------
def parse_leboncoin_html(url):
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    data = {}
    title = soup.find("h1")
    if title:
        data["titre"] = title.text.strip()

    price_tag = soup.find(string=re.compile("€"))
    if price_tag:
        data["prix"] = re.sub(r"[^\d]", "", price_tag)

    surf = soup.find(string=re.compile("m²"))
    if surf:
        try:
            data["surface"] = int(re.search(r"(\d+)\s*m²", surf).group(1))
        except:
            pass

    loc = soup.find(string=re.compile(r"\d{5}"))
    if loc:
        data["code_postal"] = re.search(r"(\d{5})", loc).group(1)
        data["ville"] = loc.split(data["code_postal"])[0].strip(" ,")

    return data

# ----------------------------
# Recherche ADEME
# ----------------------------
def fetch_ademe_all(q, pages=3):
    url = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-france/records"
    all_rows = []
    max_pages = pages if pages else 1000  # Si pages=None → récupère beaucoup
    for page in range(1, max_pages + 1):
        params = {"q": q, "size": 100, "page": page}
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
        if pages and page >= pages:
            break
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
