# app.py
# Streamlit app for DPE-GES Finder (carte et tableau permanents, filtres réactifs)

import pandas as pd
import streamlit as st

from config import settings
from services.geocoding import geocode_cities, compute_cities_extent
from services.dpe_service import fetch_dpe
from services.dvf_service import fetch_dvf_for_addresses
from ui.map_view import render_map
from ui.results_table import render_results_table

st.set_page_config(page_title="DPE-GES Finder", layout="wide")

# ─────────────────────────────────────────────
# SIDEBAR – Filtres
# ─────────────────────────────────────────────

st.sidebar.title("Filtres")

# Initialisation des filtres persistants
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

new_city = st.sidebar.text_input("Ajouter une ville", value="", placeholder="Ex : Lyon")
col_add, col_clear = st.sidebar.columns([1, 1])
with col_add:
    if st.button("➕ Ajouter", use_container_width=True):
        if new_city and new_city.strip():
            city_clean = new_city.strip()
            if city_clean not in st.session_state.filters["cities"]:
                st.session_state.filters["cities"].append(city_clean)
with col_clear:
    if st.button("🗑️ Vider la liste", use_container_width=True):
        st.session_state.filters["cities"] = []

if st.session_state.filters["cities"]:
    st.sidebar.write("**Villes sélectionnées :**")
    for v in st.session_state.filters["cities"]:
        st.sidebar.markdown(f"- {v}")
else:
    st.sidebar.caption("Aucune ville ajoutée.")

# ---- SURFACE ----
st.sidebar.subheader("Surface habitable (m²)")
col_a, col_b = st.sidebar.columns(2)
with col_a:
    min_surf = st.number_input("Min", min_value=0, value=0, step=1)
with col_b:
    max_surf = st.number_input("Max", min_value=0, value=0, step=1)
st.session_state.filters_
