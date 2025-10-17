"""
Streamlit app - Recherche d'adresses via l'API DPE (ADEME)
Version : simplifiée + import LeBonCoin + pagination (toutes pages ou X pages) +
choix du centre : centre géographique officiel (par défaut) ou point cliquable sur la carte.
"""

import json
import requests
import streamlit as st
from streamlit_folium import st_folium
import folium
from bs4 import BeautifulSoup
import pandas as pd
from io import BytesIO
from math import radians, cos, sin, sqrt, atan2
import re
import time

# ----------------------------
# Utilitaires
# ----------------------------
def distance_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def safe_float(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default

def normalize_ademe_row(r):
    # extractor tolerant to different key names
    adresse = r.get("adresse") or r.get("adresse_complete") or r.get("adresse_logement") or ""
    cp = str(r.get("code_postal") or r.get("code_postal_commune") or "")
    commune = r.get("nom_commune") or r.get("commune") or ""
    lat = safe_float(r.get("latitude") or r.get("lat"))
    lon = safe_float(r.get("longitude") or r.get("lon"))
    dpe = (r.get("classe_consommation_energie") or r.get("classe_energie") or r.get("dpe") or None)
    ges = (r.get("classe_estimation_ges") or r.get("classe_ges") or r.get("ges") or None)
    surface = safe_float(r.get("surface_habitable_logement") or r.get("surface") or r.get("surface_m2"))
    numero = r.get("numero_dpe") or r.get("id") or r.get("numero") or ""
    return {
        "adresse": adresse,
        "code_postal": cp,
        "commune": commune,
        "latitude": lat,
        "longitude": lon,
        "dpe": dpe,
        "ges": ges,
        "surface": surface,
        "numero_dpe": numero,
        "raw": r
    }

def extract_from_leboncoin_html(html_text):
    """Extrait surface, DPE, GES, CP, ville depuis le HTML (heuristique)."""
    soup = BeautifulSoup(html_text, "html.parser")
    text = soup.get_text(" ", strip=True)
    # surface : look for e.g. "45 m²" or "45m²"
    s = re.search(r"(\d{1,4})\s?m²", text)
    dpe = re.search(r"\bDPE[:\s]*([A-G])\b", text, re.IGNORECASE)
    ges = re.search(r"\bGES[:\s]*([A-G])\b", text, re.IGNORECASE)
    # code postal: first 5-digit group that looks like a french CP
    cp = None
    cps = re.findall(r"\b(0[1-9]\d{3}|[1-9]\d{4})\b", text)
    if cps:
        cp = cps[0]
    # try to find "CP + city" pattern
    ville = None
    if cp:
        m = re.search(r"\b" + re.escape(cp) + r"\b[,\s\-]*([A-Za-zÀ-ÿ\-\s]{2,50})", text)
        if m:
            ville = m.group(1).strip()
    return {
        "surface": int(s.group(1)) if s else None,
        "dpe": dpe.group(1).upper() if dpe else None,
        "ges": ges.group(1).upper() if ges else None,
        "code_postal": cp,
        "ville": ville
    }

# ----------------------------
# Configuration Streamlit
# ----------------------------
st.set_page_config(page_title="Recherche DPE (ADEME) - Simplifiée", layout="wide", page_icon="🏠")
st.title("🏠 Recherche DPE - version simplifiée")
st.markdown("Import LeBonCoin → remplir les filtres → recherche ADEME (pagination configurable).")

# ----------------------------
# Session defaults
# ----------------------------
if "saved_filters" not in st.session_state:
    st.session_state["saved_filters"] = {}

# ----------------------------
# Sidebar : filtres condensés
# ----------------------------
with st.sidebar:
    st.header("Filtres / Import")

    # Import LeBonCoin
    st.subheader("Importer une annonce LeBonCoin")
    import_source = st.radio("Source", ["Coller l'URL", "Uploader le HTML"], index=0)
    lebon_url = ""
    lebon_infos = None
    if import_source == "Coller l'URL":
        lebon_url = st.text_input("URL LeBonCoin", placeholder="https://www.leboncoin.fr/...")
        if lebon_url:
            if st.button("Extraire depuis l'URL"):
                try:
                    headers = {"User-Agent": "dpe-search-app/1.0 (+contact@example.com)"}
                    r = requests.get(lebon_url, headers=headers, timeout=12)
                    r.raise_for_status()
                    lebon_infos = extract_from_leboncoin_html(r.text)
                    st.success("Infos extraites depuis l'URL")
                except Exception as e:
                    st.error(f"Erreur téléchargement : {e}")
    else:
        uploaded = st.file_uploader("Fichier HTML", type=["html", "htm"])
        if uploaded is not None:
            if st.button("Analyser le fichier"):
                try:
                    html = uploaded.read().decode("utf-8", errors="ignore")
                    lebon_infos = extract_from_leboncoin_html(html)
                    st.success("Infos extraites depuis le fichier HTML")
                except Exception as e:
                    st.error(f"Erreur lecture fichier : {e}")

    if lebon_infos:
        st.json(lebon_infos)
        if st.button("Appliquer ces infos aux filtres"):
            # apply to inputs below by storing into st.session_state keys
            if lebon_infos.get("surface"):
                s = lebon_infos["surface"]
                st.session_state["surface_min"] = max(0, s - 10)
                st.session_state["surface_max"] = s + 10
            if lebon_infos.get("dpe"):
                st.session_state["classe_energie_sel"] = [lebon_infos["dpe"]]
            if lebon_infos.get("ges"):
                st.session_state["classe_ges_sel"] = [lebon_infos["ges"]]
            if lebon_infos.get("code_postal"):
                st.session_state["code_postaux_input"] = lebon_infos["code_postal"]
            if lebon_infos.get("ville"):
                st.session_state["ville_input"] = lebon_infos["ville"]
            st.success("Filtres pré-remplis (regarde à main droite).")

    st.markdown("---")

    # DPE/GES/Surface/CP
    st.subheader("Filtres principaux")
    classe_energie_sel = st.multiselect("Classe énergie (DPE)", options=list("ABCDEFG"), default=st.session_state.get("classe_energie_sel", []))
    classe_ges_sel = st.multiselect("Classe GES", options=list("ABCDEFG"), default=st.session_state.get("classe_ges_sel", []))
    surface_min, surface_max = st.slider("Surface habitable (m²)", min_value=0, max_value=500, value=st.session_state.get("surface_min_max", (0,500)) if False else (st.session_state.get("surface_min",0), st.session_state.get("surface_max",500)), step=5, key="surface_slider")
    code_postaux_input = st.text_input("Codes postaux (séparés par virgule)", value=st.session_state.get("code_postaux_input",""))

    st.markdown("---")
    st.subheader("Zone géographique / rayon")
    # center choice: default official center
    center_mode = st.selectbox("Point central", ["Centre officiel (ville)", "Cliquer sur la carte"], index=0)
    ville_input = st.text_input("Ville (pour centre officiel)", value=st.session_state.get("ville_input",""))
    rayon_km = st.slider("Rayon (km)", min_value=1, max_value=100, value=st.session_state.get("rayon_km", 10), step=1)

    st.markdown("---")
    st.subheader("Pagination ADEME")
    pagination_mode = st.radio("Récupération des pages", ["Toutes les pages (par défaut)", "Nombre de pages max"], index=0)
    max_pages = None
    if pagination_mode.startswith("Nombre"):
        max_pages = st.number_input("Max pages", min_value=1, max_value=50, value=5, step=1)

    st.markdown("---")
    st.subheader("Sauvegarde filtres")
    save_name = st.text_input("Nom sauvegarde", value="")
    if st.button("💾 Sauvegarder filtres dans la session"):
        key = save_name.strip() or f"sauvegarde_{len(st.session_state['saved_filters'])+1}"
        st.session_state["saved_filters"][key] = {
            "classe_energie_sel": classe_energie_sel,
            "classe_ges_sel": classe_ges_sel,
            "surface_min": surface_min,
            "surface_max": surface_max,
            "code_postaux_input": code_postaux_input,
            "center_mode": center_mode,
            "ville_input": ville_input,
            "rayon_km": rayon_km,
            "pagination_mode": pagination_mode,
            "max_pages": max_pages
        }
        st.success(f"Sauvegardé sous : {key}")

    if st.session_state["saved_filters"]:
        if st.button("Télécharger sauvegardes (.json)"):
            b = BytesIO()
            b.write(json.dumps(st.session_state["saved_filters"], ensure_ascii=False, indent=2).encode("utf-8"))
            b.seek(0)
            st.download_button("Télécharger JSON", b, file_name="dpe_filters_saved.json", mime="application/json")

        sel = st.selectbox("Charger sauvegarde existante", [""] + list(st.session_state["saved_filters"].keys()))
        if sel:
            data = st.session_state["saved_filters"][sel]
            # apply to session keys and widgets
            st.session_state["classe_energie_sel"] = data.get("classe_energie_sel", [])
            st.session_state["classe_ges_sel"] = data.get("classe_ges_sel", [])
            st.session_state["surface_min"] = data.get("surface_min", 0)
            st.session_state["surface_max"] = data.get("surface_max", 500)
            st.session_state["code_postaux_input"] = data.get("code_postaux_input", "")
            st.session_state["ville_input"] = data.get("ville_input", "")
            st.session_state["rayon_km"] = data.get("rayon_km", 10)
            st.experimental_rerun()

# ----------------------------
# Main area : carte + contrôles de recherche
# ----------------------------
st.markdown("### Carte & Résultats")
col_map, col_right = st.columns([2,1])

with col_map:
    # initial map center (France) if no city provided
    start_lat, start_lon = 46.5, 2.2

    # if centre officiel and ville provided, geocode via Nominatim
    center_lat = None
    center_lon = None
    if center_mode == "Centre officiel (ville)" and ville_input:
        try:
            geocode_url = "https://nominatim.openstreetmap.org/search"
            headers = {"User-Agent": "dpe-search-app/1.0 (+contact@example.com)"}
            resp = requests.get(geocode_url, params={"q": ville_input, "format": "json", "limit": 1}, headers=headers, timeout=10)
            if resp.ok and resp.json():
                data = resp.json()[0]
                center_lat = float(data["lat"])
                center_lon = float(data["lon"])
                start_lat, start_lon = center_lat, center_lon
        except Exception as e:
            st.warning(f"Géocodage ville échoué : {e}")

    m = folium.Map(location=[start_lat, start_lon], zoom_start=11)
    # if we have a center defined, show a marker
    if center_lat and center_lon:
        folium.Marker([center_lat, center_lon], popup=f"Centre : {ville_input}", icon=folium.Icon(color="green")).add_to(m)

    # allow user to click to choose center if selected
    st.markdown("Clique sur la carte pour choisir un point central (si 'Cliquer sur la carte' est sélectionné).")
    map_return = st_folium(m, width=900, height=500)

    clicked = map_return.get("last_clicked") if isinstance(map_return, dict) else None
    clicked_lat = clicked.get("lat") if clicked else None
    clicked_lon = clicked.get("lng") if clicked else None

with col_right:
    st.markdown("### Lancer la recherche")
    run = st.button("🔎 Lancer la recherche (ADEME)")
    st.markdown("Filtrez, puis cliquez ici. Le résultat s'affichera ci-dessous avec carte et tableau.")

# ----------------------------
# Fonction pour interroger ADEME avec pagination
# ----------------------------
def fetch_ademe_all(q, page_mode_all=True, max_pages=None, page_size=300, pause_between=0.2):
    """
    Récupère les pages de l'API ADEME.
    - page_mode_all True => récupère jusqu'à épuisement
    - sinon récupère max_pages
    On tente une pagination simple via 'page'+'size'.
    """
    base = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-france/lines"
    results = []
    page = 1
    while True:
        params = {"q": q, "size": page_size, "page": page}
        try:
            r = requests.get(base, params=params, timeout=30)
            r.raise_for_status()
            js = r.json()
        except Exception as e:
            st.warning(f"Erreur requête ADEME (page {page}) : {e}")
            break

        # detect results list robustly
        res = js.get("results") or js.get("data") or js.get("hits") or []
        # sometimes wrapped
        if isinstance(res, dict):
            # pick first list value if any
            found = None
            for v in res.values():
                if isinstance(v, list):
                    found = v
                    break
            if found is not None:
                res = found
        if not isinstance(res, list):
            res = []

        if not res:
            break
        results.extend(res)

        # stop conditions
        if (not page_mode_all) and max_pages is not None and page >= int(max_pages):
            break
        # safety: stop if returned less than page_size
        if len(res) < page_size:
            break

        page += 1
        # gentle pause to avoid hammering API
        time.sleep(pause_between)
    return results

# ----------------------------
# Lancement de la recherche
# ----------------------------
if run:
    # Build filters from sidebar widgets (reading session_state to allow pre-filled from import)
    classe_energie_sel = st.session_state.get("classe_energie_sel", []) or st.sidebar.session_state.get("classe_energie_sel", []) or []
    # But also try to read current widget values (safer to read via get on keys used)
    # We'll fallback to widget variables: (we named them earlier)
    try:
        # surface from widget
        smin, smax = st.session_state.get("surface_slider", (0,500))
    except Exception:
        smin, smax = (0,500)
    classe_energie_sel = st.session_state.get("classe_energie_sel", []) or st.session_state.get("classe_energie_sel", []) or classe_energie_sel
    classe_ges_sel = st.session_state.get("classe_ges_sel", []) or []
    code_postaux_input = st.session_state.get("code_postaux_input", "") or code_postaux_input

    # override with current visible widget values when present
    # (these keys exist as created earlier)
    try:
        classe_energie_sel = st.session_state.get("classe_energie_sel", classe_energie_sel)
    except Exception:
        pass
    try:
        classe_ges_sel = st.session_state.get("classe_ges_sel", classe_ges_sel)
    except Exception:
        pass
    try:
        code_postaux_input = st.session_state.get("code_postaux_input", code_postaux_input)
    except Exception:
        pass
    try:
        smin, smax = st.session_state.get("surface_slider", (smin, smax))
    except Exception:
        pass

    # choose central point:
    if center_mode == "Cliquer sur la carte" and clicked_lat and clicked_lon:
        center_lat_use, center_lon_use = clicked_lat, clicked_lon
    elif center_mode == "Centre officiel (ville)" and ville_input:
        # we attempted geocode earlier; try again if missing
        try:
            geocode_url = "https://nominatim.openstreetmap.org/search"
            headers = {"User-Agent": "dpe-search-app/1.0 (+contact@example.com)"}
            resp = requests.get(geocode_url, params={"q": ville_input, "format": "json", "limit": 1}, headers=headers, timeout=10)
            if resp.ok and resp.json():
                d = resp.json()[0]
                center_lat_use = float(d["lat"])
                center_lon_use = float(d["lon"])
            else:
                center_lat_use, center_lon_use = None, None
        except Exception:
            center_lat_use, center_lon_use = None, None
    else:
        center_lat_use, center_lon_use = None, None

    # Prepare ADEME query q: we don't force user text; build a query likely to return relevant rows.
    # We will query by commune (ville) if provided, otherwise by code postaux, otherwise broad query that may return many items.
    q_parts = []
    if ville_input:
        q_parts.append(ville_input)
    if code_postaux_input:
        q_parts.append(code_postaux_input)
    # fallback: if no textual filter, use empty string to get the dataset (but API may require q)
    q = " ".join(q_parts) if q_parts else ""

    # Pagination choices
    page_mode_all = (pagination_mode == "Toutes les pages (par défaut)")
    max_pages_val = None
    if not page_mode_all and max_pages:
        max_pages_val = int(max_pages)

    st.info("Interrogation API ADEME (cela peut prendre quelques secondes selon le nombre de pages).")
    raw_rows = fetch_ademe_all(q=q, page_mode_all=page_mode_all, max_pages=max_pages_val, page_size=300)

    st.info(f"{len(raw_rows)} entrées brutes récupérées depuis ADEME (avant normalisation).")

    # Normalize rows
    normalized = [normalize_ademe_row(r) for r in raw_rows]

    # Apply filters
    filtered = normalized

    # DPE & GES
    if classe_energie_sel:
        filtered = [f for f in filtered if (f.get("dpe") in classe_energie_sel)]
    if classe_ges_sel:
        filtered = [f for f in filtered if (f.get("ges") in classe_ges_sel)]

    # Surface
    try:
        smin_val, smax_val = smin, smax
        filtered = [f for f in filtered if (f.get("surface") is not None and smin_val <= f["surface"] <= smax_val)]
    except Exception:
        pass

    # Codes postaux
    cps = [c.strip() for c in (code_postaux_input or "").split(",") if c.strip()]
    if cps:
        filtered = [f for f in filtered if str(f.get("code_postal","")) in cps]

    # Geographic radius
    if center_lat_use is not None and center_lon_use is not None:
        rad = rayon_km
        before = len(filtered)
        tmp = []
        for f in filtered:
            latf = f.get("latitude"); lonf = f.get("longitude")
            if latf is None or lonf is None:
                continue
            try:
                if distance_km(center_lat_use, center_lon_use, float(latf), float(lonf)) <= float(rad):
                    tmp.append(f)
            except Exception:
                continue
        filtered = tmp
        st.info(f"Après filtrage géographique : {len(filtered)} résultats (avant {before}).")

    # Final display
    if not filtered:
        st.warning("Aucun résultat après application des filtres.")
    else:
        st.success(f"{len(filtered)} résultat(s) trouvés.")

        # Map of results
        points = [(f["latitude"], f["longitude"], f["adresse"], f["code_postal"], f["commune"], f["dpe"], f["ges"]) 
                  for f in filtered if f["latitude"] is not None and f["longitude"] is not None]
        if points:
            latm = sum(p[0] for p in points) / len(points)
            lonm = sum(p[1] for p in points) / len(points)
            map2 = folium.Map(location=[latm, lonm], zoom_start=12)
            for lat, lon, adr, cp, com, dpe, ges in points:
                popup = f"<b>{adr}</b><br>{cp} {com}<br>DPE: <b>{dpe}</b> | GES: <b>{ges}</b>"
                folium.Marker([lat, lon], popup=popup).add_to(map2)
            if center_lat_use and center_lon_use:
                folium.Circle(radius=float(rayon_km)*1000, location=[center_lat_use, center_lon_use], color="red", fill=False).add_to(map2)
            st.subheader("Carte - résultats")
            st_folium(map2, width=900, height=450)
        else:
            st.info("Aucune coordonnée disponible pour les résultats filtrés.")

        # Dataframe + export
        st.subheader("Tableau récapitulatif")
        df = pd.DataFrame([{
            "adresse": f["adresse"],
            "code_postal": f["code_postal"],
            "commune": f["commune"],
            "dpe": f["dpe"],
            "ges": f["ges"],
            "surface": f["surface"],
            "latitude": f["latitude"],
            "longitude": f["longitude"],
            "numero_dpe": f["numero_dpe"]
        } for f in filtered])
        st.dataframe(df, use_container_width=True)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Exporter CSV", data=csv, file_name="dpe_filtered_results.csv", mime="text/csv")
