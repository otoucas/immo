import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import pandas as pd

from core.data_ademe import fetch_ademe_all
from core.data_dvf import get_dvf_data
from core.geodata import (
    compute_barycenter,
    filter_ademe_data_by_radius,
    geocode_city,
    get_postal_codes_in_radius,
)
from core.postal_layers import get_postalcode_geojson


def render_main_interface():
    st.title("🏠 Carte interactive DPE / GES + DVF")

    # -------------------------------------------------------
    # SIDEBAR : FILTRES
    # -------------------------------------------------------
    st.sidebar.header("🎛️ Filtres de recherche")

    # --- Villes dynamiques ---
    if "villes" not in st.session_state:
        st.session_state["villes"] = []

    st.sidebar.markdown("#### Ajouter une ville")
    with st.sidebar.form("form_ajout_ville"):
        new_ville = st.text_input("Nom de la ville")
        submit_ville = st.form_submit_button("Ajouter")

    if submit_ville and new_ville:
        g = geocode_city(new_ville)
        if g:
            ville_label = f"{new_ville.title()} ({g.get('code_postal','?')})"
            if ville_label not in st.session_state["villes"]:
                st.session_state["villes"].append(ville_label)
                st.session_state["repere_coords"] = (g["lat"], g["lon"])
                st.sidebar.success(f"{ville_label} ajoutée ✅")
        else:
            st.sidebar.warning("Ville introuvable.")

    # --- Liste des villes actives ---
    if st.session_state["villes"]:
        st.sidebar.markdown("#### Villes sélectionnées :")
        villes_to_remove = []
        for v in st.session_state["villes"]:
            col1, col2 = st.sidebar.columns([4, 1])
            col1.write(v)
            if col2.button("🗑️", key=f"rm_{v}"):
                villes_to_remove.append(v)

        for v in villes_to_remove:
            st.session_state["villes"].remove(v)

    # Rayon : uniquement si une seule ville
    if len(st.session_state["villes"]) == 1:
        radius = st.sidebar.number_input(
            "Rayon (km)",
            min_value=0.0,
            step=1.0,
            value=st.session_state.get("radius", 0.0),
            key="radius",
        )
    else:
        radius = 0.0

    # --- Surface habitable ---
    st.sidebar.markdown("#### Surface habitable (m²)")
    col_min, col_max = st.sidebar.columns(2)
    surface_min = col_min.number_input(
        "Min", min_value=0.0, step=5.0, value=st.session_state.get("surface_min", 0.0), key="surface_min"
    )
    surface_max = col_max.number_input(
        "Max", min_value=0.0, step=5.0, value=st.session_state.get("surface_max", 500.0), key="surface_max"
    )

    # --- DPE / GES lettres à cocher ---
    st.sidebar.markdown("#### Classes DPE")
    dpe_selected = [c for c in "ABCDEFG" if st.sidebar.checkbox(c, value=True, key=f"dpe_{c}")]
    st.sidebar.markdown("#### Classes GES")
    ges_selected = [c for c in "ABCDEFG" if st.sidebar.checkbox(c, value=True, key=f"ges_{c}")]

    # --- Options de carte ---
    map_type = st.sidebar.selectbox("Type de carte", ["Classique", "Satellite"])
    show_postal_layer = st.sidebar.checkbox("Afficher les contours des codes postaux", value=True)
    show_cadastre = st.sidebar.checkbox("Afficher les parcelles cadastrales (WMS)", value=False)

    launch = st.sidebar.button("🚀 Lancer la recherche")

    # -------------------------------------------------------
    # PRÉPARATION DE LA CARTE
    # -------------------------------------------------------
    tiles = "OpenStreetMap" if map_type == "Classique" else "Esri.WorldImagery"
    villes_coords = []

    for v in st.session_state["villes"]:
        nom = v.split("(")[0].strip()
        g = geocode_city(nom)
        if g:
            villes_coords.append((g["lat"], g["lon"]))

    # --- Centre automatique ---
    if len(villes_coords) == 1:
        map_center, zoom = villes_coords[0], 12
    elif len(villes_coords) > 1:
        lat = sum(c[0] for c in villes_coords) / len(villes_coords)
        lon = sum(c[1] for c in villes_coords) / len(villes_coords)
        map_center, zoom = (lat, lon), 9
    else:
        map_center, zoom = [46.6, 2.4], 6

    m = folium.Map(location=map_center, zoom_start=zoom, tiles=tiles)

    # --- Repères automatiques ---
    for c, v in zip(villes_coords, st.session_state["villes"]):
        folium.Marker(location=c, tooltip=v, icon=folium.Icon(color="red", icon="flag")).add_to(m)

    # --- Cercle du rayon ---
    if radius > 0 and villes_coords:
        folium.Circle(
            location=villes_coords[0],
            radius=radius * 1000,
            color="#3388ff",
            fill=True,
            fill_opacity=0.2,
            popup=f"Rayon de {radius} km",
        ).add_to(m)

    st.markdown("### 🗺️ Carte de recherche")
    map_click = st_folium(m, width=1200, height=550)

    # -------------------------------------------------------
    # RECHERCHE ADEME
    # -------------------------------------------------------
    if launch:
        villes = [v.split("(")[0].strip() for v in st.session_state["villes"]]
        bary = compute_barycenter(villes) if villes else None

        if not bary:
            st.warning("Aucune ville valide sélectionnée.")
            st.stop()

        code_postaux = []
        for v in villes:
            g = geocode_city(v)
            if g and g["code_postal"]:
                code_postaux.append(g["code_postal"])

        if radius > 0:
            cp_rayon = get_postal_codes_in_radius(bary, radius)
            code_postaux.extend(cp_rayon)

        code_postaux = sorted(set(code_postaux))
        st.markdown("#### 📍 Codes postaux concernés :")
        st.write(", ".join(code_postaux) or "Aucun")

        # --- Récupération des données ADEME ---
        df = fetch_ademe_all(code_postaux)
        if df.empty:
            st.warning("Aucun résultat trouvé.")
        else:
            if "classe_consommation_energie" in df:
                df = df[df["classe_consommation_energie"].isin(dpe_selected)]
            if "classe_estimation_ges" in df:
                df = df[df["classe_estimation_ges"].isin(ges_selected)]
            if "surface_habitable_logement" in df:
                df = df[
                    (df["surface_habitable_logement"] >= surface_min)
                    & (df["surface_habitable_logement"] <= surface_max)
                ]
            if radius > 0:
                df = filter_ademe_data_by_radius(df, bary[0], bary[1], radius)

        # --- Carte et marqueurs ---
        if not df.empty:
            cluster = MarkerCluster().add_to(m)
            for _, r in df.iterrows():
                popup = f"""
                <b>{r.get('adresse_nom_voie','?')}</b><br>
                DPE: {r.get('classe_consommation_energie','?')}<br>
                GES: {r.get('classe_estimation_ges','?')}<br>
                Surface: {r.get('surface_habitable_logement','?')} m²<br>
                """
                folium.Marker(
                    location=[r["latitude"], r["longitude"]],
                    popup=popup,
                    icon=folium.Icon(color="blue", icon="home"),
                ).add_to(cluster)

            if show_postal_layer and code_postaux:
                geojson = get_postalcode_geojson(code_postaux)
                if geojson:
                    folium.GeoJson(
                        geojson,
                        name="Contours postaux",
                        style_function=lambda x: {"color": "#ff6600", "weight": 2, "opacity": 0.6},
                    ).add_to(m)

            if show_cadastre:
                folium.raster_layers.WmsTileLayer(
                    url="https://wxs.ign.fr/cadastre/geoportail/r/wms",
                    layers="CADASTRALPARCELS.PARCELS",
                    name="Cadastre",
                    fmt="image/png",
                    transparent=True,
                    opacity=0.6,
                    attribution="© IGN Cadastre",
                ).add_to(m)

            folium.LayerControl().add_to(m)
            st_folium(m, width=1200, height=600)

        # --- Tableau des résultats ---
        st.markdown("### 📋 Résultats DPE")
        display_cols = [
            "adresse_nom_voie",
            "code_postal",
            "commune",
            "surface_habitable_logement",
            "nombre_batiments",
            "classe_consommation_energie",
            "classe_estimation_ges",
        ]
        for c in display_cols:
            if c not in df.columns:
                df[c] = ""

        st.dataframe(df[display_cols].head(500))  # afficher au moins les titres
        st.download_button("⬇️ Export CSV", df[display_cols].to_csv(index=False), "resultats_dpe.csv")
