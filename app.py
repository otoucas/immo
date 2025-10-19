import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import requests
import pandas as pd

from utils import (
    save_filter,
    load_filters,
    delete_saved_filter,
    geocode_city,
    compute_barycenter,
    filter_ademe_data_by_radius,
    fetch_ademe_all,
    get_dvf_data,
    get_postalcode_geojson
)

st.set_page_config(page_title="Carte DPE + DVF", layout="wide")

st.title("🏠 Carte interactive DPE / GES + DVF + Calques postaux")

# ----------------------------
# Sidebar
# ----------------------------
st.sidebar.header("🎛️ Filtres")
cities_input = st.sidebar.text_input("Villes (séparées par virgule)")
radius = st.sidebar.number_input("Rayon (km)", min_value=0.0, step=1.0, value=0.0)
surface_min = st.sidebar.number_input("Surface min (m²)", min_value=0.0, step=5.0, value=0.0)
surface_max = st.sidebar.number_input("Surface max (m²)", min_value=0.0, step=5.0, value=500.0)
dpe_classes = ["A", "B", "C", "D", "E", "F", "G"]
dpe_selected = st.sidebar.multiselect("Classe DPE", dpe_classes, default=dpe_classes)
ges_selected = st.sidebar.multiselect("Classe GES", dpe_classes, default=dpe_classes)
map_type = st.sidebar.selectbox("Type de carte", ["Classique", "Satellite"])
show_postal_layer = st.sidebar.checkbox("Afficher les contours des codes postaux", value=True)

# Gestion des filtres sauvegardés
st.sidebar.markdown("#### Sauvegarde")
saved_filters = load_filters()
selected_save = st.sidebar.selectbox("Filtres enregistrés", ["Aucun"] + list(saved_filters.keys()))
if selected_save != "Aucun":
    fdata = saved_filters[selected_save]
    st.sidebar.json(fdata)
    if st.sidebar.button("🗑️ Supprimer ce filtre"):
        delete_saved_filter(selected_save)
        st.sidebar.success(f"Filtre '{selected_save}' supprimé")
new_filter_name = st.sidebar.text_input("Nom du filtre à enregistrer")
if st.sidebar.button("💾 Enregistrer ce filtre"):
    save_filter(new_filter_name, {
        "cities": cities_input,
        "radius": radius,
        "surface_min": surface_min,
        "surface_max": surface_max,
        "dpe": dpe_selected,
        "ges": ges_selected,
    })
    st.sidebar.success(f"Filtre '{new_filter_name}' enregistré !")

launch = st.sidebar.button("🚀 Lancer la recherche")

# ----------------------------
# Carte
# ----------------------------
tiles = "OpenStreetMap" if map_type == "Classique" else "Esri.WorldImagery"
m = folium.Map(location=[46.6, 2.4], zoom_start=6, tiles=tiles)

if launch:
    cities = [c.strip() for c in cities_input.replace(",", ";").split(";") if c.strip()]
    if not cities:
        st.warning("Merci d’indiquer au moins une ville.")
        st.stop()

    bary = compute_barycenter(cities)
    if bary:
        m.location = bary
        m.zoom_start = 12

    # Codes postaux
    code_postaux = []
    for city in cities:
        url = f"https://api-adresse.data.gouv.fr/search/?q={city}&type=municipality"
        r = requests.get(url, timeout=10)
        if r.status_code == 200 and r.json().get("features"):
            cp = r.json()["features"][0]["properties"]["postcode"]
            if cp:
                code_postaux.append(cp)

df = fetch_ademe_all(code_postaux)

# --- Sécurisation : création des colonnes manquantes ---
for col in ["classe_consommation_energie", "classe_estimation_ges", "surface_habitable_logement"]:
    if col not in df.columns:
        df[col] = None

# --- Application des filtres seulement si les colonnes existent ---
if "classe_consommation_energie" in df.columns:
    df = df[df["classe_consommation_energie"].isin(dpe_selected)]

if "classe_estimation_ges" in df.columns:
    df = df[df["classe_estimation_ges"].isin(ges_selected)]

if "surface_habitable_logement" in df.columns:
    df = df[
        (df["surface_habitable_logement"] >= surface_min)
        & (df["surface_habitable_logement"] <= surface_max)
    ]

    # Calque contours postaux
    if show_postal_layer and code_postaux:
        geojson_data = get_postalcode_geojson(code_postaux)
        if geojson_data:
            folium.GeoJson(
                geojson_data,
                name="Contours postaux",
                style_function=lambda x: {
                    "fillColor": "#00000000",
                    "color": "#ff7800",
                    "weight": 2,
                    "opacity": 0.7
                },
                tooltip=folium.GeoJsonTooltip(fields=["nom", "codePostal"], aliases=["Commune", "Code postal"])
            ).add_to(m)

    if df.empty:
        st.warning("Aucun résultat trouvé.")
    else:
        st.success(f"{len(df)} enregistrements ADEME chargés.")
    else:
        marker_cluster = MarkerCluster().add_to(m)
        for _, row in df.iterrows():
            dvf_html = ""
            dvf_data = get_dvf_data(row.get("code_postal", ""), voie=row.get("adresse_nom_voie", ""))
            if dvf_data:
                dvf_html = "<hr><b>Historique DVF :</b><br>"
                for v in dvf_data:
                    prix_m2 = (
                        round(v["valeur_fonciere"] / v["surface"], 0)
                        if v["surface"] and v["valeur_fonciere"]
                        else "?"
                    )
                    dvf_html += f"{v['date']} — {v['type']} : {prix_m2} €/m²<br>"
            else:
                dvf_html = "<i>Pas de ventes DVF récentes</i>"

            popup = f"""
            <b>{row.get('adresse_nom_voie','?')}</b><br>
            DPE: {row.get('classe_consommation_energie','?')}<br>
            GES: {row.get('classe_estimation_ges','?')}<br>
            Surface: {row.get('surface_habitable_logement','?')} m²<br>
            {dvf_html}
            """
            folium.Marker(
                location=[row["latitude"], row["longitude"]],
                popup=popup,
                icon=folium.Icon(color="blue", icon="home", prefix="fa")
            ).add_to(marker_cluster)

    folium.LayerControl().add_to(m)

st_folium(m, width=1200, height=700)

# ----------------------------
# Tableau de données
# ----------------------------
if launch and not df.empty:
    st.subheader("📋 Résultats détaillés")
    display_cols = [
        "adresse_nom_voie", "code_postal", "commune",
        "surface_habitable_logement", "nombre_batiments",
        "classe_consommation_energie", "classe_estimation_ges"
    ]
    st.dataframe(df[display_cols])
    csv = df[display_cols].to_csv(index=False)
    st.download_button("⬇️ Export CSV", csv, "resultats_dpe.csv", "text/csv")
