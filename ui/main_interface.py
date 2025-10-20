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
    st.markdown(
        "Ajoutez une ou plusieurs villes, filtrez selon les classes DPE / GES et visualisez les résultats sur la carte."
    )

    # -------------------------------------------------------
    # VARIABLES DE SESSION
    # -------------------------------------------------------
    if "villes" not in st.session_state:
        st.session_state["villes"] = []

    # Données initiales
    df = pd.DataFrame()

    # -------------------------------------------------------
    # SIDEBAR : FILTRES
    # -------------------------------------------------------
    st.sidebar.header("🎛️ Filtres")

    # --- Ajout de ville ---
    st.sidebar.markdown("#### Ajouter une ville")
    with st.sidebar.form("form_ajout_ville"):
        new_ville = st.text_input("Nom de la ville")
        submit_ville = st.form_submit_button("Ajouter")

    if submit_ville and new_ville:
        g = geocode_city(new_ville)
        if g:
            label = f"{new_ville.title()} ({g.get('code_postal','?')})"
            if label not in st.session_state["villes"]:
                st.session_state["villes"].append(label)
                st.sidebar.success(f"{label} ajoutée ✅")
        else:
            st.sidebar.warning("Ville introuvable.")

    # --- Villes sélectionnées ---
    if st.session_state["villes"]:
        st.sidebar.markdown("#### Villes sélectionnées :")
        to_remove = []
        for v in st.session_state["villes"]:
            c1, c2 = st.sidebar.columns([4, 1])
            c1.write(v)
            if c2.button("🗑️", key=f"del_{v}"):
                to_remove.append(v)
        for v in to_remove:
            st.session_state["villes"].remove(v)

    # --- Rayon (si 1 ville) ---
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

    # --- Surface ---
    st.sidebar.markdown("#### Surface habitable (m²)")
    cmin, cmax = st.sidebar.columns(2)
    surface_min = cmin.number_input("Min", 0.0, step=5.0, value=st.session_state.get("surface_min", 0.0))
    surface_max = cmax.number_input("Max", 0.0, step=5.0, value=st.session_state.get("surface_max", 500.0))
    st.session_state["surface_min"] = surface_min
    st.session_state["surface_max"] = surface_max

    # --- DPE / GES lettres ---
    st.sidebar.markdown("#### Classes DPE")
    dpe_selected = [c for c in "ABCDEFG" if st.sidebar.checkbox(c, value=False, key=f"dpe_{c}")]
    st.sidebar.markdown("#### Classes GES")
    ges_selected = [c for c in "ABCDEFG" if st.sidebar.checkbox(c, value=False, key=f"ges_{c}")]

    # --- Carte ---
    map_type = st.sidebar.selectbox("Type de carte", ["Classique", "Satellite"])
    show_postal_layer = st.sidebar.checkbox("Contours codes postaux", True)
    show_cadastre = st.sidebar.checkbox("Parcelles cadastrales (IGN)", False)

    launch = st.sidebar.button("🚀 Lancer la recherche")

    # -------------------------------------------------------
    # CENTRAGE AUTOMATIQUE
    # -------------------------------------------------------
    tiles = "OpenStreetMap" if map_type == "Classique" else "Esri.WorldImagery"
    villes_coords = []

    for v in st.session_state["villes"]:
        nom = v.split("(")[0].strip()
        g = geocode_city(nom)
        if g:
            villes_coords.append((g["lat"], g["lon"]))

    if len(villes_coords) == 1:
        map_center, zoom = villes_coords[0], 12
    elif len(villes_coords) > 1:
        lat = sum(c[0] for c in villes_coords) / len(villes_coords)
        lon = sum(c[1] for c in villes_coords) / len(villes_coords)
        map_center, zoom = (lat, lon), 9
    else:
        map_center, zoom = [46.6, 2.4], 6

    # -------------------------------------------------------
    # AFFICHAGE DE LA CARTE
    # -------------------------------------------------------
    m = folium.Map(location=map_center, zoom_start=zoom, tiles=tiles)
    for c, v in zip(villes_coords, st.session_state["villes"]):
        folium.Marker(location=c, tooltip=v, icon=folium.Icon(color="red", icon="flag")).add_to(m)

    if radius > 0 and villes_coords:
        folium.Circle(
            location=villes_coords[0],
            radius=radius * 1000,
            color="#3388ff",
            fill=True,
            fill_opacity=0.2,
        ).add_to(m)

    st.markdown("### 🗺️ Carte de recherche")
    map_click = st_folium(m, width=1200, height=550)

    # -------------------------------------------------------
    # RECHERCHE
    # -------------------------------------------------------
    if launch:
        villes = [v.split("(")[0].strip() for v in st.session_state["villes"]]
        bary = compute_barycenter(villes) if villes else None

        if not bary:
            st.warning("Aucune ville valide sélectionnée.")
            return

        # Codes postaux des villes
        code_postaux = []
        for v in villes:
            g = geocode_city(v)
            if g and g["code_postal"]:
                code_postaux.append(g["code_postal"])

        # Codes postaux dans le rayon
        if radius > 0:
            rayon_cp = get_postal_codes_in_radius(bary, radius)
            if rayon_cp:
                code_postaux.extend(rayon_cp)
                st.info(f"📍 Codes postaux dans le rayon ({radius} km) : {', '.join(sorted(set(rayon_cp)))}")
            else:
                st.warning("Aucun code postal supplémentaire trouvé dans ce rayon.")

        code_postaux = sorted(set(code_postaux))

        # --- Données ADEME ---
        df = fetch_ademe_all(code_postaux)
        if df.empty:
            st.warning("Aucun résultat trouvé.")
        else:
            if "classe_consommation_energie" in df:
                df = df[df["classe_consommation_energie"].isin(dpe_selected)] if dpe_selected else df
            if "classe_estimation_ges" in df:
                df = df[df["classe_estimation_ges"].isin(ges_selected)] if ges_selected else df
            if "surface_habitable_logement" in df:
                df = df[
                    (df["surface_habitable_logement"] >= surface_min)
                    & (df["surface_habitable_logement"] <= surface_max)
                ]
            if radius > 0:
                df = filter_ademe_data_by_radius(df, bary[0], bary[1], radius)

            if df.empty:
                st.warning("Aucun logement ne correspond aux filtres.")
            else:
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

    # -------------------------------------------------------
    # TABLEAU DES RÉSULTATS
    # -------------------------------------------------------
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

    st.dataframe(df[display_cols].head(500))
    st.download_button("⬇️ Export CSV", df[display_cols].to_csv(index=False), "resultats_dpe.csv")
