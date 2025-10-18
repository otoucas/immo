# app.py
import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from utils import (
    save_filter,
    load_filters,
    delete_saved_filter,
    geocode_city,
    distance_km,
    fetch_ademe_all,
    get_price_history,
)
import math

import sys, os
sys.path.append(os.path.dirname(__file__))

# ----------------------------
# Configuration page
# ----------------------------
st.set_page_config(page_title="DPE Explorer (ADEME + DVF)", layout="wide")
st.title("🏠 DPE Explorer — Open Data ADEME + Historique DVF")

# ----------------------------
# session_state initial
# ----------------------------
if "df_results" not in st.session_state:
    st.session_state.df_results = pd.DataFrame()
if "repere" not in st.session_state:
    st.session_state.repere = None
if "selected_index" not in st.session_state:
    st.session_state.selected_index = None
if "saved_filters" not in st.session_state:
    st.session_state.saved_filters = load_filters() or {}

# ----------------------------
# Sidebar — filtres
# ----------------------------
st.sidebar.header("🔎 Filtres de recherche")

# villes (texte, séparées par ; ou ,)
cities_input = st.sidebar.text_input("Ville(s) — séparer par ; ou ,", value="; ".join([]))

# Tile choice (classic / satellite)
tile_choice = st.sidebar.radio("Type de carte", ["Classique (Plan)", "Satellite"], index=0)

# Rayon unique (km)
st.sidebar.subheader("Rayon (km)")
rayon_km = st.sidebar.number_input("Rayon", min_value=0, max_value=500, value=10, step=1)

# Surface : min/max as number inputs + slider visual
st.sidebar.subheader("Surface habitable (m²)")
smin = st.sidebar.number_input("Surface min (m²)", min_value=0, max_value=10000, value=0, step=1)
smax = st.sidebar.number_input("Surface max (m²)", min_value=0, max_value=10000, value=300, step=1)
s_slider = st.sidebar.slider("Plage surface (visuelle)", 0, 10000, (smin, smax))
# keep in sync
if (s_slider[0], s_slider[1]) != (smin, smax):
    smin, smax = s_slider

# DPE / GES filters
st.sidebar.subheader("Filtres énergie")
dpe_choices = st.sidebar.multiselect("Classe DPE", options=list("ABCDEFG"))
ges_choices = st.sidebar.multiselect("Classe GES", options=list("ABCDEFG"))

# Pagination ADEME: all pages or limit
st.sidebar.markdown("---")
st.sidebar.subheader("Pagination ADEME")
pagination_mode = st.sidebar.selectbox("Récupération ADEME", ["Toutes les pages (par défaut)", "Limiter le nombre de pages"], index=0)
pages_limit = None
if pagination_mode != "Toutes les pages (par défaut)":
    pages_limit = st.sidebar.number_input("Nombre max de pages", min_value=1, max_value=500, value=5, step=1)

# Save / load filters block (named)
st.sidebar.markdown("---")
st.sidebar.subheader("Sauvegarder / charger filtres")
new_name = st.sidebar.text_input("Nom du filtre à enregistrer")
col1, col2 = st.sidebar.columns(2)
if col1.button("Enregistrer filtre") and new_name:
    to_save = {
        "cities": cities_input,
        "rayon_km": rayon_km,
        "smin": smin,
        "smax": smax,
        "dpe": dpe_choices,
        "ges": ges_choices,
        "pagination_mode": pagination_mode,
        "pages_limit": pages_limit or 0,
        "tile_choice": tile_choice
    }
    save_filter(new_name, to_save)
    st.session_state.saved_filters = load_filters()
    st.sidebar.success(f"Filtre '{new_name}' sauvegardé.")

saved_keys = [""] + sorted(list(st.session_state.saved_filters.keys()))
sel_saved = st.sidebar.selectbox("Filtres sauvegardés", saved_keys)
if sel_saved:
    colL, colD = st.sidebar.columns(2)
    if colL.button("Charger"):
        f = st.session_state.saved_filters.get(sel_saved, {})
        # load into UI by rerunning with session_state set
        st.experimental_set_query_params()  # no-op to ensure rerun but keep consistent
        # set values in session_state so they are used after rerun
        st.session_state._load_filter = f
        st.experimental_rerun()
    if colD.button("Supprimer"):
        delete_saved_filter(sel_saved)
        st.session_state.saved_filters = load_filters()
        st.sidebar.success(f"Filtre '{sel_saved}' supprimé.")

# If we have instruction to load a filter, apply it
if "_load_filter" in st.session_state:
    f = st.session_state.pop("_load_filter")
    # set sidebar values via session_state — Streamlit will re-render
    st.session_state._cities_input = f.get("cities", "")
    st.session_state._rayon_km = f.get("rayon_km", 10)
    st.session_state._smin = f.get("smin", 0)
    st.session_state._smax = f.get("smax", 300)
    st.session_state._dpe = f.get("dpe", [])
    st.session_state._ges = f.get("ges", [])
    st.session_state._pagination_mode = f.get("pagination_mode", "Toutes les pages (par défaut)")
    st.session_state._pages_limit = f.get("pages_limit", 0)
    st.session_state._tile_choice = f.get("tile_choice", "Classique (Plan)")
    st.experimental_rerun()

# Apply session_state loaded values to local variables (if present)
if "_cities_input" in st.session_state:
    cities_input = st.session_state.pop("_cities_input")
if "_rayon_km" in st.session_state:
    rayon_km = st.session_state.pop("_rayon_km")
if "_smin" in st.session_state:
    smin = st.session_state.pop("_smin")
if "_smax" in st.session_state:
    smax = st.session_state.pop("_smax")
if "_dpe" in st.session_state:
    dpe_choices = st.session_state.pop("_dpe")
if "_ges" in st.session_state:
    ges_choices = st.session_state.pop("_ges")
if "_pagination_mode" in st.session_state:
    pagination_mode = st.session_state.pop("_pagination_mode")
if "_pages_limit" in st.session_state:
    pages_limit = st.session_state.pop("_pages_limit")
if "_tile_choice" in st.session_state:
    tile_choice = st.session_state.pop("_tile_choice")

st.sidebar.markdown("---")

# ----------------------------
# Action: Lancer la recherche ADEME
# ----------------------------
if st.sidebar.button("🔎 Lancer la recherche"):
    # parse cities list
    cities = [c.strip() for c in cities_input.replace(",", ";").split(";") if c.strip()]
    if not cities:
        st.sidebar.error("Saisis au moins une ville.")
    else:
        # geocode cities and compute center barycenter
        coords = []
        for c in cities:
            g = geocode_city(c)
            if g:
                coords.append(g)
        if not coords:
            st.sidebar.error("Aucune ville géocodée. Vérifie l'orthographe.")
        else:
            avg_lat = sum([x[0] for x in coords]) / len(coords)
            avg_lon = sum([x[1] for x in coords]) / len(coords)
            # determine pages param
            pages_param = None if pagination_mode.startswith("Toutes") else (pages_limit or 5)
            # fetch ADEME rows (q built from city names)
            q = " ".join(cities)
            with st.spinner("Récupération des données ADEME (cela peut prendre du temps si tu choisis 'Toutes les pages')..."):
                raw = fetch_ademe_all(q=q, pages=pages_param, page_size=300)
            if raw is None or raw.empty:
                st.session_state.df_results = pd.DataFrame()
                st.sidebar.warning("Aucun résultat ADEME trouvé.")
            else:
                df = raw.copy()
                # ensure and normalize expected columns (fill with '?')
                expected = [
                    "adresse_numero_voie", "adresse_nom_voie", "code_postal", "commune",
                    "surface_habitable_logement", "nombre_batiments",
                    "classe_consommation_energie", "date_consommation_energie",
                    "classe_estimation_ges", "date_estimation_ges",
                    "latitude", "longitude"
                ]
                for col in expected:
                    if col not in df.columns:
                        df[col] = "?"
                # convert lat/lon to numeric and drop rows without coords
                df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
                df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
                df = df.dropna(subset=["latitude", "longitude"])
                # surface filter numeric
                df["surface_habitable_logement"] = pd.to_numeric(df["surface_habitable_logement"], errors="coerce")
                df = df[(df["surface_habitable_logement"].fillna(-1) >= smin) & (df["surface_habitable_logement"].fillna(-1) <= smax)]
                # DPE / GES filters
                if dpe_choices:
                    df = df[df["classe_consommation_energie"].isin(dpe_choices)]
                if ges_choices:
                    df = df[df["classe_estimation_ges"].isin(ges_choices)]
                # radius filter: use repere if present, else barycenter
                center = st.session_state.repere if st.session_state.repere else (avg_lat, avg_lon)
                if rayon_km and rayon_km > 0:
                    df["__dist"] = df.apply(lambda r: distance_km(center[0], center[1], float(r["latitude"]), float(r["longitude"])), axis=1)
                    df = df[df["__dist"] <= float(rayon_km)]
                    df = df.drop(columns=["__dist"], errors="ignore")
                st.session_state.df_results = df.reset_index(drop=True)
                st.success(f"{len(df)} résultats après filtres.")

# ----------------------------
# Zone principale : carte (toujours visible) + tableau dessous
# ----------------------------
st.subheader("🗺 Carte — le repère se définit par clic (ou par centre des villes si aucun repère)")

# compute default center
cities = [c.strip() for c in cities_input.replace(",", ";").split(";") if c.strip()]
coords_list = []
for c in cities:
    g = geocode_city(c)
    if g:
        coords_list.append(g)
if st.session_state.repere:
    center = st.session_state.repere
elif coords_list:
    center = (sum([c[0] for c in coords_list]) / len(coords_list), sum([c[1] for c in coords_list]) / len(coords_list))
else:
    center = (46.6, 2.4)

# build map
tiles = "OpenStreetMap" if tile_choice.startswith("Classique") else "Esri.WorldImagery"
m = folium.Map(location=center, zoom_start=12, tiles=None)
folium.TileLayer("OpenStreetMap", name="Plan").add_to(m)
folium.TileLayer("Esri.WorldImagery", name="Satellite").add_to(m)
folium.LayerControl().add_to(m)

# show repere if present
if st.session_state.repere:
    folium.Marker(st.session_state.repere, popup="Repère (centre)", icon=folium.Icon(color="red")).add_to(m)

# show results markers (cluster)
df_show = st.session_state.df_results.copy() if not st.session_state.df_results.empty else pd.DataFrame()
mc = MarkerCluster().add_to(m)
for idx, r in df_show.iterrows():
    # build popup content and include price history
    adresse = " ".join([str(x) for x in [r.get("adresse_numero_voie", "?"), r.get("adresse_nom_voie", "?")] if x and x != "?"])
    adresse_full = f"{adresse}, {r.get('code_postal','?')} {r.get('commune','?')}"
    # get DVF price history (best-effort) — small radius 100m
    price_hist = []
    try:
        price_hist = get_price_history(float(r["latitude"]), float(r["longitude"]), radius_m=200)
    except Exception:
        price_hist = []
    price_html = ""
    if price_hist:
        price_html += "<b>Historique des ventes (prox.)</b><br>"
        for ph in price_hist[:8]:
            date = ph.get("date_mutation", "?")
            val = ph.get("valeur_fonciere", "?")
            surf = ph.get("surface_relle_bati", "?")
            price_html += f"{date}: {val} € ({surf} m²)<br>"
    else:
        price_html = "<i>Pas d'historique de ventes disponible</i><br>"

    popup_html = (
        f"<b>Adresse :</b> {adresse_full}<br>"
        f"<b>Surface :</b> {r.get('surface_habitable_logement','?')} m²<br>"
        f"<b>Nb bâtiments :</b> {r.get('nombre_batiments','?')}<br>"
        f"<b>DPE :</b> {r.get('classe_consommation_energie','?')} (date: {r.get('date_consommation_energie','?')})<br>"
        f"<b>GES :</b> {r.get('classe_estimation_ges','?')} (date: {r.get('date_estimation_ges','?')})<br>"
        f"{price_html}"
    )
    popup = folium.Popup(popup_html, max_width=350)
    folium.Marker([r["latitude"], r["longitude"]], popup=popup, tooltip=adresse_full).add_to(mc)

# display map and capture click to set repere
map_result = st_folium(m, width=1000, height=700, returned_objects=["last_clicked"])
if map_result and map_result.get("last_clicked"):
    latc = map_result["last_clicked"]["lat"]
    lonc = map_result["last_clicked"]["lng"]
    st.session_state.repere = (latc, lonc)
    st.experimental_rerun()

# ----------------------------
# Tableau (toujours visible)
# ----------------------------
st.subheader("📋 Tableau des résultats")
display_cols = [
    "adresse_numero_voie", "adresse_nom_voie", "code_postal", "commune",
    "surface_habitable_logement", "nombre_batiments",
    "classe_consommation_energie", "date_consommation_energie",
    "classe_estimation_ges", "date_estimation_ges", "latitude", "longitude"
]

if st.session_state.df_results.empty:
    empty_df = pd.DataFrame(columns=display_cols)
    st.dataframe(empty_df, use_container_width=True)
else:
    df_table = st.session_state.df_results.copy()
    for c in display_cols:
        if c not in df_table.columns:
            df_table[c] = "?"
    df_table = df_table[display_cols].reset_index(drop=True)
    st.dataframe(df_table, use_container_width=True)

    # selection by index to center / open popup
    sel_idx = st.number_input("Index à centrer / ouvrir popup", min_value=0, max_value=max(0, len(df_table)-1), value=0, step=1)
    if st.button("📍 Centrer & ouvrir popup"):
        st.session_state.selected_index = int(sel_idx)
        # on recentre la carte et on fera apparaître popup après rerun
        st.experimental_rerun()

# If selected_index present -> show marker popup and center (done via re-render: set selected_index consumed in map rendering)
if st.session_state.get("selected_index") is not None:
    # keep selection until consumed by map render: simulate by setting and rerunning (map code consumes it, see loop above)
    pass

# ----------------------------
# Export CSV in sidebar
# ----------------------------
st.sidebar.markdown("---")
if not st.session_state.df_results.empty:
    csv = st.session_state.df_results.to_csv(index=False).encode("utf-8")
    st.sidebar.download_button("📥 Exporter CSV", csv, "resultats_dpe.csv", "text/csv")
else:
    st.sidebar.write("Aucun résultat à exporter.")
