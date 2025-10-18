import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from typing import List, Tuple, Optional
from utils import (
    geocode_city,
    fetch_ademe_all,
    save_filter,
    load_filters,
    delete_saved_filter,
    compute_barycenter,
    export_csv,
)

st.set_page_config(page_title="Analyse DPE Interactive", layout="wide")

# -------------------------------------------------------
# Sidebar - Filtres
# -------------------------------------------------------
st.sidebar.header("⚙️ Filtres de recherche")

cities_input = st.sidebar.text_input("Villes (séparées par ;) :", "Lyon; Villeurbanne")
rayon_km = st.sidebar.number_input("Rayon (km autour du repère)", min_value=1, max_value=100, value=10)

surface_min = st.sidebar.number_input("Surface habitable min (m²)", 0)
surface_max = st.sidebar.number_input("Surface habitable max (m²)", 1000)

dpe_sel = st.sidebar.multiselect("Classes DPE", list("ABCDEFG"))
ges_sel = st.sidebar.multiselect("Classes GES", list("ABCDEFG"))

map_style = st.sidebar.radio("Type de carte", ["Classique", "Satellite"])

# Sauvegarde / chargement des filtres
st.sidebar.subheader("💾 Sauvegardes de filtres")
filter_name = st.sidebar.text_input("Nom de la sauvegarde")

col1, col2, col3 = st.sidebar.columns(3)
with col1:
    if st.button("💾 Sauver"):
        save_filter(filter_name, {
            "cities": cities_input,
            "rayon_km": rayon_km,
            "surface_min": surface_min,
            "surface_max": surface_max,
            "dpe_sel": dpe_sel,
            "ges_sel": ges_sel,
        })
with col2:
    if st.button("📂 Charger"):
        data = load_filters()
        if filter_name in data:
            f = data[filter_name]
            st.session_state.update(f)
            st.sidebar.success(f"Filtres '{filter_name}' chargés.")
with col3:
    if st.button("🗑️ Supprimer"):
        delete_saved_filter(filter_name)

saved_filters = list(load_filters().keys())
if saved_filters:
    st.sidebar.write("Sauvegardes disponibles :")
    for name in saved_filters:
        st.sidebar.markdown(f"- {name}")

# -------------------------------------------------------
# Traitement
# -------------------------------------------------------
cities_list = [c.strip() for c in cities_input.replace(",", ";").split(";") if c.strip()]

if st.sidebar.button("🔍 Lancer la recherche"):
    st.session_state["search_launched"] = True
else:
    st.session_state.setdefault("search_launched", False)

# Affichage principal
st.title("🏠 Carte interactive des DPE")
st.markdown("Les résultats s’affichent ci-dessous dès qu’une recherche est effectuée.")

# Carte vide si pas encore de recherche
if not st.session_state["search_launched"]:
    st.warning("➡️ Lancez une recherche depuis le panneau latéral pour afficher les résultats.")
    m = folium.Map(location=[46.6, 2.4], zoom_start=6)
    st_folium(m, height=500)
    st.stop()

# -------------------------------------------------------
# Chargement des données ADEME
# -------------------------------------------------------
with st.spinner("Chargement des données ADEME..."):
    df = fetch_ademe_all(cities_list)

if df.empty:
    st.error("Aucun résultat trouvé pour ces critères.")
    st.stop()

# Application des filtres
if surface_min or surface_max:
    df = df[(df["surface_habitable_logement"] >= surface_min) &
            (df["surface_habitable_logement"] <= surface_max)]

if dpe_sel:
    df = df[df["classe_consommation_energie"].isin(dpe_sel)]
if ges_sel:
    df = df[df["classe_estimation_ges"].isin(ges_sel)]

if df.empty:
    st.warning("Aucun bien ne correspond aux filtres appliqués.")
    st.stop()

# -------------------------------------------------------
# Carte interactive
# -------------------------------------------------------
center = compute_barycenter(cities_list)
tiles = "OpenStreetMap" if map_style == "Classique" else "Esri.WorldImagery"
m = folium.Map(location=center, zoom_start=12, tiles=tiles)

marker_cluster = MarkerCluster().add_to(m)

for _, r in df.iterrows():
    popup_html = f"""
    <b>Adresse :</b> {r.get('adresse_nom_voie', '?')}<br>
    <b>DPE :</b> {r.get('classe_consommation_energie', '?')}<br>
    <b>GES :</b> {r.get('classe_estimation_ges', '?')}<br>
    <b>Date DPE :</b> {r.get('date_realisation_dpe', '?')}<br>
    <b>Surface :</b> {r.get('surface_habitable_logement', '?')} m²<br>
    <b>Nombre de bâtiments :</b> {r.get('nombre_batiment', '?')}
    """
    folium.Marker(
        location=[r["latitude"], r["longitude"]],
        popup=popup_html,
        icon=folium.Icon(color="blue", icon="home", prefix="fa")
    ).add_to(marker_cluster)

st_data = st_folium(m, height=550, width=1000)

# -------------------------------------------------------
# Tableau des résultats
# -------------------------------------------------------
st.subheader("📋 Résultats détaillés")
display_cols = [
    "adresse_nom_voie",
    "surface_habitable_logement",
    "nombre_batiment",
    "classe_consommation_energie",
    "classe_estimation_ges",
    "date_realisation_dpe",
]
display_df = df[display_cols].rename(columns={
    "adresse_nom_voie": "Adresse",
    "surface_habitable_logement": "Surface (m²)",
    "nombre_batiment": "Bâtiments",
    "classe_consommation_energie": "DPE",
    "classe_estimation_ges": "GES",
    "date_realisation_dpe": "Date DPE",
})
selected = st.dataframe(display_df, use_container_width=True)

# Export CSV
if st.button("💾 Exporter les résultats en CSV"):
    export_csv(display_df)
    st.success("Fichier CSV exporté avec succès !")
