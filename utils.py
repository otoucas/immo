import requests
import re
from math import radians, cos, sin, sqrt, atan2
import streamlit as st

# --- Géocodage ---
def geocode_city(ville):
    try:
        url = "https://nominatim.openstreetmap.org/search"
        headers = {"User-Agent": "dpe-search-app/1.0 (+contact@example.com)"}
        resp = requests.get(
            url,
            params={"q": ville, "format": "json", "limit": 1},
            headers=headers,
            timeout=10
        )
        if resp.ok and resp.json():
            d = resp.json()[0]
            return float(d["lat"]), float(d["lon"])
    except Exception:
        pass
    return None, None

# --- Distance ---
def distance_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

# --- Extraction LeBonCoin ---
def parse_leboncoin_html(html_text):
    infos = {}
    try:
        surface = re.search(r"(\d+)\s?m²", html_text)
        ville = re.search(r"(?i)(?:à|sur)\s+([A-Za-zÀ-ÖØ-öø-ÿ\- ]+)\s?(?:\(|,|<|$)", html_text)
        codep = re.search(r"\b(\d{5})\b", html_text)
        dpe = re.search(r"[dD][pP][eE]\s*[:\-]?\s*([A-G])", html_text)
        ges = re.search(r"[gG][eE][sS]\s*[:\-]?\s*([A-G])", html_text)
        if surface:
            infos["surface_min"], infos["surface_max"] = int(surface.group(1)) - 10, int(surface.group(1)) + 10
        if ville:
            infos["ville"] = ville.group(1).strip().title()
        if codep:
            infos["code_postal"] = codep.group(1)
        if dpe:
            infos["classe_energie"] = [dpe.group(1).upper()]
        if ges:
            infos["classe_ges"] = [ges.group(1).upper()]
    except Exception:
        pass
    return infos

# --- Pagination ADEME avec barre de progression ---
def fetch_ademe_all(q="", page_mode_all=True, max_pages=None, page_size=300):
    base = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-france/lines"
    all_rows = []
    page = 1
    if page_mode_all:
        st.info("⏳ Récupération de toutes les pages ADEME (cela peut prendre quelques minutes)…")
    else:
        st.info(f"⏳ Récupération des {max_pages} premières pages ADEME…")
    
    progress_bar = st.progress(0)
    
    while True:
        params = {"q": q, "size": page_size, "page": page}
        try:
            resp = requests.get(base, params=params, timeout=15)
            if not resp.ok:
                break
            data = resp.json()
            rows = data.get("results", [])
            if not rows:
                break
            all_rows.extend(rows)
            if page_mode_all:
                if page % 10 == 0:
                    progress_bar.progress(min(page*5, 100))
            else:
                progress_bar.progress(int(page/max_pages*100))
            page += 1
            if not page_mode_all and max_pages and page > max_pages:
                break
        except Exception as e:
            st.warning(f"Erreur récupération page {page}: {e}")
            break
    progress_bar.progress(100)
    return all_rows
