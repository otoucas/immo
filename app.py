import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

from utils import geocode_city, parse_leboncoin_html, fetch_ademe_all, distance_km
from filters.storage import save_filter, load_filters, delete_filter

# Configuration de la page
st.set_page_config(page_title="Recherche DPE interactive", layout="wide")
st.title("🏡 Analyse DPE - Vue géographique et filtres dynamiques")

# --- Chargement / sauvegarde des filtres ---
with st.sidebar:
    st.header("🎛️ Filtres")

    saved_filters = load_filters()
    filter_name = st.text_input("Nom du jeu de filtres")

    col1, col2 = st.columns(2)
    if col1.button("💾 Sauver filtres") and filter_name:
        save_filter(filter_name, st.session_state)
        st.success(f"Filtres sauvegardés sous le nom : {filter_name}")

    if col2.button("🗑️ Supprimer") and filter_name:
        delete_filter(filter_name)
        st.success(f"Filtres supprimés : {filter_name}")

    if saved_filters:
        selected_filter = st.selectbox("Charger un jeu de filtres", [""] + list(saved_filters.keys()))
        if selected_filter:
            st.session_state.update(saved_filters[selected_filter])
            st.success(f"Filtres chargés : {selected_filter}")

# --- Source des données ---
source_choice = st.radio("🔍 Source de recherche", ["Page Leboncoin", "Open Data ADEME"], horizontal=True)

if source_choice == "Page Leboncoin":
    url = st.text_input("Collez l'URL de la page Leboncoin :")
    if url:
        df = parse_leboncoin_html(url)
    else:
        df = pd.DataFrame()
else:
    # Filtres de localisation
    ville = st.text_input("Ville de recherche", st.session_state.get("ville", ""))
    nb_pages = st.number_input("Nombre de pages à récupérer", 1, 50, st.session_state.get("nb_pages", 5))

    # Filtres de surface
    col1, col2 = st.columns(2)
    with col1:
        smin = st.number_input("Surface minimale (m²)", min_value=0, value=0, step=10)
    with col2:
        smax = st.number_input("Surface maximale (m²)", min_value=0, value=500, step=10)

    # Filtre de rayon
    rayon = st.number_input("Rayon (km)", min_value=0, value=10, step=1)

    if st.button("🔎 Lancer la recherche"):
        coords = geocode_city(ville)
        if coords:
            lat, lon = coords
            df = fetch_ademe_all(ville, pages=nb_pages)
            df = df[(df["surface_habitable_logement"] >= smin) & (df["surface_habitable_logement"] <= smax)]
            df["distance"] = df.apply(
                lambda r: distance_km(lat, lon, r.get("latitude", lat), r.get("longitude", lon)), axis=1
            )
            df = df[df["distance"] <= rayon]
        else:
            st.error("Ville non trouvée.")
            df = pd.DataFrame()
    else:
        df = pd.DataFrame()

# --- Carte interactive ---
if not df.empty:
    st.subheader("🗺️ Carte des résultats")

    center_lat = df["latitude"].mean()
    center_lon = df["longitude"].mean()
    m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles="OpenStreetMap")

    # Couches supplémentaires
    folium.TileLayer("CartoDB positron", name="Clair").add_to(m)
    folium.TileLayer("CartoDB dark_matter", name="Sombre").add_to(m)
    folium.TileLayer(
        tiles="https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google Satellite",
        name="Satellite",
        max_zoom=20,
        subdomains=["mt0", "mt1", "mt2", "mt3"]
    ).add_to(m)

    marker_cluster = MarkerCluster().add_to(m)

    for _, r in df.iterrows():
        popup_html = f"""
        <b>{r.get('adresse_nom_voie', 'Adresse inconnue')}</b><br>
        Commune : {r.get('commune', '?')} ({r.get('code_postal', '')})<br>
        Surface : {r.get('surface_habitable_logement', '?')} m²<br>
        Bâtiments : {r.get('nombre_batiments', '?')}<br>
        DPE : {r.get('classe_consommation_energie', '?')}<br>
        GES : {r.get('classe_estimation_ges', '?')}<br>
        Date DPE : {r.get('date_etablissement_dpe', '?')}
        """
        folium.Marker(
            location=[r.get("latitude", 0), r.get("longitude", 0)],
            popup=folium.Popup(popup_html, max_width=250)
        ).add_to(marker_cluster)

    folium.LayerControl().add_to(m)
    map_state = st_folium(m, width=1200, height=600)

    # --- Tableau des résultats ---
    st.subheader("📋 Résultats détaillés")

    display_cols = [
        "adresse_nom_voie",
        "code_postal",
        "commune",
        "classe_consommation_energie",
        "classe_estimation_ges",
        "surface_habitable_logement",
        "nombre_batiments",
        "date_etablissement_dpe",
        "latitude",
        "longitude"
    ]
    display_cols = [c for c in display_cols if c in df.columns]
    display_df = df[display_cols].copy()

    st.dataframe(display_df, use_container_width=True)

else:
    st.info("Aucun résultat à afficher. Lancez une recherche pour voir les données.")
