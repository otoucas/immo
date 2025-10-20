# app.py
# Streamlit app for DPE-GES Finder

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

# Initialisation de l'état
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
    if st.button("➕ Ajouter"):
        if new_city and new_city.strip():
            city_clean = new_city.strip()
            if city_clean not in st.session_state.filters["cities"]:
                st.session_state.filters["cities"].append(city_clean)
with col_clear:
    if st.button("🗑️ Vider la liste"):
        st.session_state.filters["cities"] = []

# affichage des villes ajoutées
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

# ---- DPE / GES ----
st.sidebar.subheader("Classes DPE")
dpe_opts = ["A", "B", "C", "D", "E", "F", "G"]
sel_dpe = st.sidebar.multiselect("Choisir les classes DPE :", dpe_opts)

st.sidebar.subheader("Classes GES")
ges_opts = ["A", "B", "C", "D", "E", "F", "G"]
sel_ges = st.sidebar.multiselect("Choisir les classes GES :", ges_opts)

# ---- ACTIONS ----
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

if apply_btn:
    st.session_state.filters["min_surface"] = int(min_surf) if min_surf > 0 else None
    st.session_state.filters["max_surface"] = int(max_surf) if max_surf > 0 else None
    st.session_state.filters["dpe_classes"] = sel_dpe
    st.session_state.filters["ges_classes"] = sel_ges

# ─────────────────────────────────────────────
# MAIN – Carte + Tableau
# ─────────────────────────────────────────────

st.title("🔎 DPE-GES Finder (Open Data)")
st.caption(
    "Recherchez des logements par villes et surfaces, "
    "visualisez les résultats sur carte et tableau."
)

left, right = st.columns([3, 4], gap="large")

# Valeurs par défaut
empty_extent = {"center_lat": 46.6, "center_lon": 2.6, "zoom_like": 5.5, "bbox": None}
empty_df = pd.DataFrame(
    columns=[
        "full_address",
        "city",
        "lat",
        "lon",
        "dpe",
        "ges",
        "surface",
        "date_dpe",
        "row_id",
        "dvf",
        "dvf_count",
    ]
)

geo = []
extent = empty_extent
dpe_df = empty_df.copy()

# ---- Recherche si des villes existent ----
if st.session_state.filters["cities"]:
    with st.spinner("Géocodage des villes…"):
        geo = geocode_cities(st.session_state.filters["cities"])
        if geo:
            extent = compute_cities_extent(geo)

    with st.spinner("Récupération des DPE depuis l'ADEME…"):
        dpe_df = fetch_dpe(
            cities=geo,
            min_surface=st.session_state.filters["min_surface"],
            max_surface=st.session_state.filters["max_surface"],
            limit=settings.DEFAULT_RESULT_LIMIT,
        )

        # Application filtres DPE / GES
        if st.session_state.filters["dpe_classes"]:
            dpe_df = dpe_df[dpe_df["dpe"].isin(st.session_state.filters["dpe_classes"])]
        if st.session_state.filters["ges_classes"]:
            dpe_df = dpe_df[dpe_df["ges"].isin(st.session_state.filters["ges_classes"])]

    if not dpe_df.empty:
        dpe_df["row_id"] = dpe_df.index.astype(str)
    else:
        dpe_df = empty_df.copy()

    # ---- Enrichissement DVF optionnel ----
    with st.expander("Options d'enrichissement DVF (valeurs foncières)"):
        enrich_dvf = st.checkbox("Joindre les infos DVF par adresse", value=True)
        dvf_limit = st.slider("Max adresses DVF à interroger", 10, 200, 50, 10)

    if enrich_dvf and not dpe_df.empty:
        with st.spinner("Interrogation DVF…"):
            unique_addresses = (
                dpe_df["full_address"].dropna().drop_duplicates().head(dvf_limit).tolist()
            )
            dvf_data = fetch_dvf_for_addresses(unique_addresses)
            dpe_df["dvf_count"] = dpe_df["full_address"].map(lambda a: len(dvf_data.get(a, [])))
            dpe_df["dvf"] = dpe_df["full_address"].map(lambda a: dvf_data.get(a, []))
    else:
        dpe_df["dvf_count"] = 0
        dpe_df["dvf"] = [[] for _ in range(len(dpe_df))]

else:
    st.info("Aucune ville n’a encore été sélectionnée. Ajoutez-en au moins une pour lancer une recherche.")

# ---- Affichage permanent carte + tableau ----
with left:
    selected_row_id = st.session_state.get("selected_row_id")
    render_map(df=dpe_df, extent=extent, selected_row_id=selected_row_id)

with right:
    selected_row_id = render_results_table(dpe_df)
    if selected_row_id is not None:
        st.session_state["selected_row_id"] = selected_row_id

# ---- Statut ----
if not dpe_df.empty:
    st.success(f"{len(dpe_df)} logements affichés.")
else:
    st.caption("Aucun résultat correspondant pour les filtres actuels (carte et tableau visibles).")
