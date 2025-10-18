import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import pandas as pd
import json
import os
from utils import geocode_city, fetch_ademe_all

# ----------------------------
# Configuration de la page
# ----------------------------
st.set_page_config(page_title="Carte DPE ADEME", layout="wide")

# ----------------------------
# Sidebar - Filtres
# ----------------------------
st.sidebar.header("⚙️ Filtres et options")

# Ville(s)
cities_input = st.sidebar.text_input("Ville(s) (séparées par ; ou ,)", "Lyon")

# Rayon
col_r1, col_r2 = st.sidebar.columns(2)
rayon_min = col_r1.number_input("Rayon min (km)", min_value=0, value=0)
rayon_max = col_r2.number_input("Rayon max (km)", min_value=0, value=10)

# Surface
col_s1, col_s2 = st.sidebar.columns(2)
surface_min = col_s1.number_input("Surface min (m²)", min_value=0, value=50)
surface_max = col_s2.number_input("Surface max (m²)", min_value=0, value=300)

# Filtres DPE et GES
col_dpe, col_ges = st.sidebar.columns(2)
dpe_filter = col_dpe.multiselect("Classe DPE", ["A", "B", "C", "D", "E", "F", "G"])
ges_filter = col_ges.multiselect("Classe GES", ["A", "B", "C", "D", "E", "F", "G"])

# Sauvegarde / chargement des filtres
save_dir = "saved_filters"
os.makedirs(save_dir, exist_ok=True)
filters_file = os.path.join(save_dir, "filters.json")

col_save, col_load, col_del = st.sidebar.columns(3)
if col_save.button("💾 Sauvegarder"):
    filters = {
        "cities_input": cities_input,
        "rayon_min": rayon_min,
        "rayon_max": rayon_max,
        "surface_min": surface_min,
        "surface_max": surface_max,
        "dpe_filter": dpe_filter,
        "ges_filter": ges_filter
    }
    with open(filters_file, "w") as f:
        json.dump(filters, f)
    st.sidebar.success("Filtres sauvegardés ✅")

if col_load.button("📂 Charger") and os.path.exists(filters_file):
    with open(filters_file, "r") as f:
        filters = json.load(f)
    cities_input = filters.get("cities_input", cities_input)
    rayon_min = filters.get("rayon_min", rayon_min)
    rayon_max = filters.get("rayon_max", rayon_max)
    surface_min = filters.get("surface_min", surface_min)
    surface_max = filters.get("surface_max", surface_max)
    dpe_filter = filters.get("dpe_filter", dpe_filter)
    ges_filter = filters.get("ges_filter", ges_filter)
    st.sidebar.success("Filtres chargés ✅")

if col_del.button("🗑️ Supprimer") and os.path.exists(filters_file):
    os.remove(filters_file)
    st.sidebar.warning("Filtres supprimés ❌")

# ----------------------------
# Extraction des villes
# ----------------------------
parts = [c.strip() for c in cities_input.replace(",", ";").split(";") if c.strip()]
city_coords = []
for c in parts:
    coords = geocode_city(c)
    if coords:
        city_coords.append((c, coords))

if not city_coords:
    st.error("Aucune ville valide trouvée.")
    st.stop()

# Calcul du centre de la carte
avg_lat = sum(c[1][0] for c in city_coords) / len(city_coords)
avg_lon = sum(c[1][1] for c in city_coords) / len(city_coords)

# ----------------------------
# Carte principale
# ----------------------------
m = folium.Map(location=[avg_lat, avg_lon], zoom_start=11, tiles="OpenStreetMap")

# Options de carte
folium.TileLayer("Stamen Terrain", attr="Stamen").add_to(m)
folium.TileLayer("Esri.WorldImagery", attr="Esri").add_to(m)
folium.LayerControl().add_to(m)

# Ajout des repères de villes
for name, (lat, lon) in city_coords:
    folium.Marker(
        [lat, lon],
        popup=f"<b>{name}</b>",
        tooltip=f"Centre : {name}",
        icon=folium.Icon(color="blue")
    ).add_to(m)

# Repère utilisateur sauvegardé
if "repere" not in st.session_state:
    st.session_state["repere"] = None

st.sidebar.write("---")
st.sidebar.subheader("📍 Repère central")
if st.session_state["repere"]:
    lat, lon = st.session_state["repere"]
    st.sidebar.write(f"Latitude : **{lat:.5f}**, Longitude : **{lon:.5f}**")
else:
    st.sidebar.write("Aucun repère défini (cliquez sur la carte pour en ajouter)")

st.sidebar.write("---")
st.sidebar.info("Cliquez sur la carte pour définir un repère central pour la recherche.")

# Affichage initial de la carte pour capturer le clic
st_data = st_folium(m, width=1300, height=600)
if st_data and st_data.get("last_clicked"):
    lat, lon = st_data["last_clicked"]["lat"], st_data["last_clicked"]["lng"]
    st.session_state["repere"] = (lat, lon)
    st.success(f"Nouveau repère défini : {lat:.5f}, {lon:.5f}")

# ----------------------------
# Bouton pour lancer la recherche ADEME
# ----------------------------
if st.sidebar.button("🚀 Lancer la recherche ADEME"):
    with st.spinner("Chargement des données ADEME..."):
        # Utilise le repère s’il est défini, sinon la moyenne des villes
        center_lat, center_lon = (
            st.session_state["repere"] if st.session_state["repere"] else (avg_lat, avg_lon)
        )
        df = fetch_ademe_all([(cities_input, (center_lat, center_lon))], rayon_max)

    if df.empty:
        st.warning("Aucun résultat trouvé pour ces critères.")
    else:
        # Filtrage des résultats
        if dpe_filter:
            df = df[df["classe_consommation_energie"].isin(dpe_filter)]
        if ges_filter:
            df = df[df["classe_estimation_ges"].isin(ges_filter)]
        df = df[
            (df["surface_habitable_logement"] >= surface_min) &
            (df["surface_habitable_logement"] <= surface_max)
        ]

        # Carte des résultats
        m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="OpenStreetMap")
        folium.TileLayer("Stamen Terrain", attr="Stamen").add_to(m)
        folium.TileLayer("Esri.WorldImagery", attr="Esri").add_to(m)
        folium.LayerControl().add_to(m)

        # Ajout du repère central
        folium.Marker(
            [center_lat, center_lon],
            popup="Repère central",
            icon=folium.Icon(color="red", icon="star")
        ).add_to(m)

        cluster = MarkerCluster().add_to(m)
        for _, r in df.iterrows():
            popup_html = f"""
            <b>{r.get('adresse_nom_voie', 'Adresse inconnue')}</b><br>
            Surface : {r.get('surface_habitable_logement', '?')} m²<br>
            Bâtiments : {r.get('nombre_batiments', '?')}<br>
            DPE : {r.get('classe_consommation_energie', '?')}<br>
            GES : {r.get('classe_estimation_ges', '?')}<br>
            Date : {r.get('date_dpe', '?')}
            """
            folium.Marker(
                [r["latitude"], r["longitude"]],
                popup=popup_html,
                tooltip=r.get("adresse_nom_voie", "Adresse inconnue"),
                icon=folium.Icon(color="green", icon="home")
            ).add_to(cluster)

        st_folium(m, width=1300, height=650)

        # Tableau des résultats
        display_cols = [
            "adresse_nom_voie",
            "surface_habitable_logement",
            "nombre_batiments",
            "classe_consommation_energie",
            "classe_estimation_ges",
            "date_dpe"
        ]
        df_display = df[display_cols].copy()
        st.dataframe(df_display, use_container_width=True)

        # Export CSV
        csv = df_display.to_csv(index=False).encode("utf-8")
        st.download_button("📦 Exporter en CSV", csv, "resultats_ademe.csv", "text/csv")
else:
    st.info("Utilisez la barre latérale pour définir vos critères et lancer la recherche.")
