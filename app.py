# app.py
import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from utils import (
    geocode_city,
    fetch_ademe_all,
    distance_km,
    save_filter,
    load_filters,
    delete_filter,
    get_price_history,
)
import math

# ----------------------------
# Configuration
# ----------------------------
st.set_page_config(page_title="DPE Explorer", layout="wide")
st.title("🏠 DPE Explorer — Open Data ADEME + Historique DVF")

# ----------------------------
# Session state init
# ----------------------------
if "df_results" not in st.session_state:
    st.session_state.df_results = pd.DataFrame()
if "repere" not in st.session_state:
    st.session_state.repere = None  # (lat, lon)
if "selected_index" not in st.session_state:
    st.session_state.selected_index = None
if "saved_filters" not in st.session_state:
    st.session_state.saved_filters = load_filters() or {}

# ----------------------------
# Sidebar: filtres
# ----------------------------
st.sidebar.header("🔎 Filtres de recherche")

# villes (séparées par ; ou ,)
cities_input = st.sidebar.text_input("Ville(s) — séparer par ; ou ,", value="")

# type de carte
tile_choice = st.sidebar.radio("Type de carte", ["Classique (Plan)", "Satellite"], index=0)

# rayon (un seul)
rayon_km = st.sidebar.number_input("Rayon (km)", min_value=0, max_value=1000, value=10, step=1)

# surface min/max (cases + slider synchronisé)
st.sidebar.subheader("Surface habitable (m²)")
smin = st.sidebar.number_input("Surface min", min_value=0, max_value=10000, value=0, step=1)
smax = st.sidebar.number_input("Surface max", min_value=0, max_value=10000, value=300, step=1)
s_slider = st.sidebar.slider("Plage surface (visuelle)", 0, 10000, (smin, smax))
if (s_slider[0], s_slider[1]) != (smin, smax):
    smin, smax = s_slider

# DPE and GES filters
st.sidebar.subheader("Filtres énergie")
dpe_choices = st.sidebar.multiselect("Classe DPE", options=list("ABCDEFG"))
ges_choices = st.sidebar.multiselect("Classe GES", options=list("ABCDEFG"))

# Pagination ADEME: toutes les pages ou limiter
st.sidebar.markdown("---")
st.sidebar.subheader("Pagination ADEME")
pagination_mode = st.sidebar.selectbox("Récupération", ["Toutes les pages (par défaut)", "Limiter le nombre de pages"], index=0)
pages_limit = None
if pagination_mode != "Toutes les pages (par défaut)":
    pages_limit = st.sidebar.number_input("Nombre max de pages", min_value=1, max_value=1000, value=5, step=1)

# Save / load filters
st.sidebar.markdown("---")
st.sidebar.subheader("Sauvegarder / charger filtres (nommés)")
new_filter_name = st.sidebar.text_input("Nom du filtre à enregistrer")
col1, col2 = st.sidebar.columns(2)
if col1.button("Enregistrer filtre") and new_filter_name:
    to_save = {
        "cities_input": cities_input,
        "tile_choice": tile_choice,
        "rayon_km": rayon_km,
        "smin": smin,
        "smax": smax,
        "dpe_choices": dpe_choices,
        "ges_choices": ges_choices,
        "pagination_mode": pagination_mode,
        "pages_limit": pages_limit or 0
    }
    save_filter(new_filter_name, to_save)
    st.session_state.saved_filters = load_filters()
    st.sidebar.success(f"Filtre '{new_filter_name}' sauvegardé.")

saved_keys = [""] + sorted(list(st.session_state.saved_filters.keys()))
sel_saved = st.sidebar.selectbox("Filtres sauvegardés", saved_keys)
if sel_saved:
    c1, c2 = st.sidebar.columns(2)
    if c1.button("Charger"):
        f = st.session_state.saved_filters.get(sel_saved, {})
        # load values into session_state then rerun so UI updates
        st.session_state._load_filter = f
        st.experimental_rerun()
    if c2.button("Supprimer"):
        delete_filter(sel_saved)
        st.session_state.saved_filters = load_filters()
        st.sidebar.success(f"Filtre '{sel_saved}' supprimé.")

# If a filter was queued for load, apply to session_state and rerun to update widgets
if "_load_filter" in st.session_state:
    f = st.session_state.pop("_load_filter")
    # put values into session so they become defaults on rerun
    st.session_state._cities_input = f.get("cities_input", "")
    st.session_state._tile_choice = f.get("tile_choice", "Classique (Plan)")
    st.session_state._rayon_km = f.get("rayon_km", 10)
    st.session_state._smin = f.get("smin", 0)
    st.session_state._smax = f.get("smax", 300)
    st.session_state._dpe_choices = f.get("dpe_choices", [])
    st.session_state._ges_choices = f.get("ges_choices", [])
    st.session_state._pagination_mode = f.get("pagination_mode", "Toutes les pages (par défaut)")
    st.session_state._pages_limit = f.get("pages_limit", 0)
    st.experimental_rerun()

# Apply loaded session_state values to local variables (so widgets show them)
if "_cities_input" in st.session_state:
    cities_input = st.session_state.pop("_cities_input")
if "_tile_choice" in st.session_state:
    tile_choice = st.session_state.pop("_tile_choice")
if "_rayon_km" in st.session_state:
    rayon_km = st.session_state.pop("_rayon_km")
if "_smin" in st.session_state:
    smin = st.session_state.pop("_smin")
if "_smax" in st.session_state:
    smax = st.session_state.pop("_smax")
if "_dpe_choices" in st.session_state:
    dpe_choices = st.session_state.pop("_dpe_choices")
if "_ges_choices" in st.session_state:
    ges_choices = st.session_state.pop("_ges_choices")
if "_pagination_mode" in st.session_state:
    pagination_mode = st.session_state.pop("_pagination_mode")
if "_pages_limit" in st.session_state:
    pages_limit = st.session_state.pop("_pages_limit")

st.sidebar.markdown("---")
# Button to run search
run_search = st.sidebar.button("🔎 Lancer la recherche")

# ----------------------------
# Function: compute barycenter of cities list
# ----------------------------
def compute_barycenter(cities_list: List[str]) -> Optional[Tuple[float, float]]:
    coords = []
    for c in cities_list:
        g = geocode_city(c)
        if g:
            coords.append(g)
    if not coords:
        return None
    return (sum([x[0] for x in coords]) / len(coords), sum([x[1] for x in coords]) / len(coords))

# ----------------------------
# Perform search when requested
# ----------------------------
if run_search:
    cities = [c.strip() for c in cities_input.replace(",", ";").split(";") if c.strip()]
    if not cities:
        st.sidebar.error("Indique au moins une ville.")
    else:
        bary = compute_barycenter(cities)
        if not bary:
            st.sidebar.error("Impossible de géocoder les villes fournies.")
        else:
            avg_lat, avg_lon = bary
            pages_param = None if pagination_mode.startswith("Toutes") else (pages_limit or 5)
            q = " ".join(cities)
            with st.spinner("Récupération ADEME (cela peut prendre un peu de temps)…"):
                raw = fetch_ademe_all(q=q, pages=pages_param, page_size=300)
            if raw is None or raw.empty:
                st.session_state.df_results = pd.DataFrame()
                st.sidebar.warning("Aucun résultat ADEME trouvé.")
            else:
                df = raw.copy()
                expected = [
                    "adresse_numero_voie","adresse_nom_voie","code_postal","commune",
                    "surface_habitable_logement","nombre_batiments",
                    "classe_consommation_energie","date_consommation_energie",
                    "classe_estimation_ges","date_estimation_ges",
                    "latitude","longitude"
                ]
                for col in expected:
                    if col not in df.columns:
                        df[col] = "?"
                # numeric conversions
                df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
                df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
                df = df.dropna(subset=["latitude","longitude"])
                df["surface_habitable_logement"] = pd.to_numeric(df["surface_habitable_logement"], errors="coerce")
                # apply surface filter
                df = df[(df["surface_habitable_logement"].fillna(-1) >= smin) & (df["surface_habitable_logement"].fillna(-1) <= smax)]
                # apply DPE/GES filters
                if dpe_choices:
                    df = df[df["classe_consommation_energie"].isin(dpe_choices)]
                if ges_choices:
                    df = df[df["classe_estimation_ges"].isin(ges_choices)]
                # radius: use repere if set, else barycenter
                center = st.session_state.repere if st.session_state.repere else (avg_lat, avg_lon)
                if rayon_km and float(rayon_km) > 0:
                    df["__dist"] = df.apply(lambda r: distance_km(center[0], center[1], float(r["latitude"]), float(r["longitude"])), axis=1)
                    df = df[df["__dist"] <= float(rayon_km)]
                    df = df.drop(columns=["__dist"], errors="ignore")
                st.session_state.df_results = df.reset_index(drop=True)
                st.success(f"{len(st.session_state.df_results)} résultats après application des filtres.")

# ----------------------------
# Main area: map (always visible) + table below
# ----------------------------
st.subheader("🗺 Carte — cliquez pour définir le repère central (utilisé pour le rayon)")

# Compute map center: repere if set otherwise barycenter of input cities, otherwise France center
cities_for_center = [c.strip() for c in cities_input.replace(",", ";").split(";") if c.strip()]
bary = compute_barycenter(cities_for_center)
if st.session_state.repere:
    map_center = st.session_state.repere
elif bary:
    map_center = bary
else:
    map_center = (46.6, 2.4)

# Build folium map
tiles = "OpenStreetMap" if tile_choice.startswith("Classique") else None
m = folium.Map(location=map_center, zoom_start=12, tiles=None)
folium.TileLayer("OpenStreetMap", name="Plan").add_to(m)
folium.TileLayer("Esri.WorldImagery", name="Satellite").add_to(m)
folium.LayerControl().add_to(m)

# Show repere if exists
if st.session_state.repere:
    folium.Marker(location=st.session_state.repere, popup="Repère (centre)", icon=folium.Icon(color="red", icon="star")).add_to(m)

# Plot results markers clustered
df_show = st.session_state.df_results.copy() if not st.session_state.df_results.empty else pd.DataFrame()
mc = MarkerCluster().add_to(m)

# If user selected an index to center & open popup, we'll track it
sel_to_open = None
if st.session_state.selected_index is not None:
    try:
        sel_to_open = int(st.session_state.selected_index)
        # keep it until consumed by rendering below
    except Exception:
        sel_to_open = None

for idx, row in df_show.iterrows():
    adresse = " ".join([str(x) for x in [row.get("adresse_numero_voie","?"), row.get("adresse_nom_voie","?")] if x and x != "?"])
    adresse_full = f"{adresse}, {row.get('code_postal','?')} {row.get('commune','?')}"
    # price history (best-effort)
    price_hist = []
    try:
        price_hist = get_price_history(float(row["latitude"]), float(row["longitude"]), radius_m=200)
    except Exception:
        price_hist = []
    price_html = ""
    if price_hist:
        price_html += "<b>Historique des ventes (prox.)</b><br>"
        for ph in price_hist[:6]:
            date = ph.get("date_mutation", "?")
            val = ph.get("valeur_fonciere", "?")
            surf = ph.get("surface_relle_bati", "?")
            price_html += f"{date}: {val} € ({surf} m²)<br>"
    else:
        price_html = "<i>Pas d'historique de ventes disponible</i><br>"

    popup_html = (
        f"<b>Adresse :</b> {adresse_full}<br>"
        f"<b>Surface :</b> {row.get('surface_habitable_logement','?')} m²<br>"
        f"<b>Nb bâtiments :</b> {row.get('nombre_batiments','?')}<br>"
        f"<b>DPE :</b> {row.get('classe_consommation_energie','?')} (date: {row.get('date_consommation_energie','?')})<br>"
        f"<b>GES :</b> {row.get('classe_estimation_ges','?')} (date: {row.get('date_estimation_ges','?')})<br>"
        f"{price_html}"
    )
    # If this is the selected index, open popup and center map
    if sel_to_open is not None and sel_to_open == int(idx):
        popup = folium.Popup(popup_html, max_width=400)
        folium.Marker([row["latitude"], row["longitude"]], popup=popup, icon=folium.Icon(color="blue")).add_to(mc)
        # center map here and zoom
        m.location = [row["latitude"], row["longitude"]]
        m.zoom_start = 17
        # consume the selection
        st.session_state.selected_index = None
    else:
        popup = folium.Popup(popup_html, max_width=400)
        folium.Marker([row["latitude"], row["longitude"]], popup=popup).add_to(mc)

# Show the map and capture clicks to set repere
map_result = st_folium(m, width=1000, height=650, returned_objects=["last_clicked"])
if map_result and map_result.get("last_clicked"):
    latc = map_result["last_clicked"]["lat"]
    lonc = map_result["last_clicked"]["lng"]
    st.session_state.repere = (latc, lonc)
    st.experimental_rerun()

# ----------------------------
# Tableau des résultats (toujours visible)
# ----------------------------
st.subheader("📋 Tableau des résultats")
display_cols = [
    "adresse_numero_voie","adresse_nom_voie","code_postal","commune",
    "surface_habitable_logement","nombre_batiments",
    "classe_consommation_energie","date_consommation_energie",
    "classe_estimation_ges","date_estimation_ges","latitude","longitude"
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

    # allow user to pick a row index to center & open popup
    sel_idx = st.number_input("Index à centrer / ouvrir popup", min_value=0, max_value=max(0, len(df_table)-1), value=0, step=1)
    if st.button("📍 Centrer & ouvrir popup"):
        st.session_state.selected_index = int(sel_idx)
        st.experimental_rerun()

# ----------------------------
# Export CSV
# ----------------------------
st.sidebar.markdown("---")
if not st.session_state.df_results.empty:
    csv = st.session_state.df_results.to_csv(index=False).encode("utf-8")
    st.sidebar.download_button("📥 Exporter CSV", csv, "resultats_dpe.csv", "text/csv")
else:
    st.sidebar.write("Aucun résultat à exporter.")
