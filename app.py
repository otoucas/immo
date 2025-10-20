# app.py
# Streamlit app entrypoint

import json
import math
from typing import List, Dict, Any

import pandas as pd
import streamlit as st

from config import settings
from services.geocoding import geocode_cities, compute_cities_extent
from services.dpe_service import fetch_dpe
from services.dvf_service import fetch_dvf_for_addresses
from ui.map_view import render_map
from ui.results_table import render_results_table
from utils.filters import active_filters_summary, clear_all_filters, remove_filter

st.set_page_config(page_title="DPE‑GES Finder", layout="wide")

# --- Sidebar (filters) ---
st.sidebar.title("Filtres")

# État persistant des filtres
if "filters" not in st.session_state:
    st.session_state.filters = {
        "cities": [],
        "min_surface": None,
        "max_surface": None,
        "dpe_classes": [],
        "ges_classes": [],
    }

# ---- CHOIX DES VILLES ----
st.sidebar.subheader("Villes d'intérêt")

# champ de saisie d'une ville à ajouter
new_city = st.sidebar.text_input(
    "Ajouter une ville",
    value="",
    placeholder="Ex: Belley",)

col_add, col_clear = st.sidebar.columns([1, 1])
with col_add:
    if st.button("➕ Ajouter"):
        if new_city and new_city.strip():
            city_clean = new_city.strip()
            if city_clean not in st.session_state.filters["cities"]:
                st.session_state.filters["cities"].append(city_clean)
with col_clear:
    if st.button("🗑️ Vider la liste"):
        st.session_state.filters["cities"] = []

# affichage des villes ajoutées avec leur code postal (récupéré via BAN)
if st.session_state.filters["cities"]:
    st.sidebar.write("**Villes sélectionnées :**")
    for v in st.session_state.filters["cities"]:
        st.sidebar.markdown(f"- {v}")
else:
    st.sidebar.caption("Aucune ville ajoutée.")

# ---- FILTRES SURFACE ----
st.sidebar.subheader("Surface habitable (m²)")
col_a, col_b = st.sidebar.columns(2)
with col_a:
    min_surf = st.number_input("Min", min_value=0, value=0, step=1)
with col_b:
    max_surf = st.number_input("Max", min_value=0, value=0, step=1)

# ---- FILTRES DPE/GES ----
st.sidebar.subheader("Classes DPE")
dpe_opts = ["A", "B", "C", "D", "E", "F", "G"]
sel_dpe = st.sidebar.multiselect("Choisir les classes DPE à inclure :", dpe_opts)

st.sidebar.subheader("Classes GES")
ges_opts = ["A", "B", "C", "D", "E", "F", "G"]
sel_ges = st.sidebar.multiselect("Choisir les classes GES à inclure :", ges_opts)

# ---- BOUTONS ACTION ----
apply_btn = st.sidebar.button("🔍 Lancer la recherche", type="primary")
reset_btn = st.sidebar.button("🧹 Réinitialiser les filtres")

if reset_btn:
    st.session_state.filters = {
        "cities": [],
        "min_surface": None,
        "max_surface": None,
        "dpe_classes": [],
        "ges_classes": [],
    }

# ---- MISE À JOUR DES FILTRES ----

# Apply filters to state when user clicks search
if apply_btn:
    st.session_state.filters["cities"] = parsed_cities
    st.session_state.filters["min_surface"] = int(min_surf) if min_surf > 0 else None
    st.session_state.filters["max_surface"] = int(max_surf) if max_surf > 0 else None
    st.session_state.filters["dpe_classes"] = sel_dpe
    st.session_state.filters["ges_classes"] = sel_ges

# Show active filters as removable chips (buttons)
st.sidebar.subheader("Filtres actifs")
chips = active_filters_summary(st.session_state.filters)
for chip_key, chip_label in chips:
    if st.sidebar.button(f"❌ {chip_label}"):
        remove_filter(st.session_state, chip_key)

# --- Main layout ---
st.title("🔎 DPE‑GES Finder (Open Data)")
st.caption(
    "Recherchez des logements par villes et surfaces, visualisez les résultats sur carte et tableau."
)

left, right = st.columns([3, 4], gap="large")

if not st.session_state.filters["cities"]:
    st.info("Aucun filtre actif. Renseignez au moins une ville puis lancez la recherche.")
    st.stop()

# Geocode cities and compute extent
with st.spinner("Géocodage des villes…"):
    geo = geocode_cities(st.session_state.filters["cities"])  # List of {city, lat, lon, insee, bbox}

if len(geo) == 0:
    st.warning("Aucune ville trouvée. Vérifiez l'orthographe.")
    st.stop()

extent = compute_cities_extent(geo)

# Fetch DPE data
with st.spinner("Récupération des DPE depuis l'ADEME…"):
    dpe_df = fetch_dpe(
        cities=geo,
        min_surface=st.session_state.filters["min_surface"],
        max_surface=st.session_state.filters["max_surface"],
        limit=settings.DEFAULT_RESULT_LIMIT,
    )

    # Application des filtres DPE / GES
    if st.session_state.filters["dpe_classes"]:
        dpe_df = dpe_df[dpe_df["dpe"].isin(st.session_state.filters["dpe_classes"])]
    if st.session_state.filters["ges_classes"]:
        dpe_df = dpe_df[dpe_df["ges"].isin(st.session_state.filters["ges_classes"])]

if dpe_df.empty:
    st.warning("Aucun résultat DPE ne correspond à vos critères.")
    st.stop()

# Add a stable unique key for map selection
dpe_df["row_id"] = dpe_df.index.astype(str)

# Fetch DVF (optional, matched on full address). This can be slow, so limit addresses
with st.expander("Options d'enrichissement DVF (valeurs foncières)"):
    enrich_dvf = st.checkbox("Joindre les infos DVF par adresse", value=True)
    dvf_limit = st.slider("Max adresses DVF à interroger", 10, 200, 50, 10)

dvf_data: Dict[str, Any] = {}
if enrich_dvf:
    with st.spinner("Interrogation DVF…"):
        unique_addresses = (
            dpe_df["full_address"].dropna().drop_duplicates().head(dvf_limit).tolist()
        )
        dvf_data = fetch_dvf_for_addresses(unique_addresses)

# Merge DVF data back (simple indicator and a json blob)
if dvf_data:
    dpe_df["dvf_count"] = dpe_df["full_address"].map(lambda a: len(dvf_data.get(a, [])))
    dpe_df["dvf"] = dpe_df["full_address"].map(lambda a: dvf_data.get(a, []))
else:
    dpe_df["dvf_count"] = 0
    dpe_df["dvf"] = [[] for _ in range(len(dpe_df))]

# UI: map + table synchronized
with left:
    selected_row_id = st.session_state.get("selected_row_id")
    render_map(
        df=dpe_df,
        extent=extent,
        selected_row_id=selected_row_id,
    )

with right:
    selected_row_id = render_results_table(dpe_df)
    if selected_row_id is not None:
        st.session_state["selected_row_id"] = selected_row_id

st.success(f"{len(dpe_df)} logements affichés.")
