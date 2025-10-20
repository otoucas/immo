import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import pandas as pd
import requests

from core.data_ademe import fetch_ademe_all
from core.data_dvf import get_dvf_data
from core.geodata import compute_barycenter, filter_ademe_data_by_radius, geocode_city, get_postal_codes_in_radius
from core.postal_layers import get_postalcode_geojson
from utils.storage import save_filter, load_filters, delete_saved_filter


def render_main_interface():
    st.title("🏠 Carte interactive DPE / GES + DVF")
    st.markdown(
        "Saisissez des villes et explorez leurs diagnostics de performance énergétique (DPE) et historiques de ventes."
    )

    # -------------------------------------------------------
    # SIDEBAR : FILTRES
    # -------------------------------------------------------
    st.sidebar.header("🎛️ Filtres de recherche")

    # --- Villes dynamiques ---
    if "villes" not in st.session_state:
        st.session_state["villes"] = []

    new_ville = st.sidebar.text_input("Ajouter une ville (tapez Entrée)")
    if new_ville:
        g = geocode_city(new_ville)
        if g:
            ville_label = f"{new_ville.title()} ({g.get('code_postal','?')})"
            if ville_label not in st.session_state["villes"]:
                st.session_state["villes"].append(ville_label)
                st.session_state["repere_coords"] = (g["lat"], g["lon"])
                st.sidebar.success(f"{ville_label} ajoutée ✅")
        else:
            st.sidebar.warning("Ville introuvable.")
        st.rerun()

    # Liste des villes actives
    if st.session_state["villes"]:
        st.sidebar.markdown("#### Villes sélectionnées :")
        for v in st.session_state["villes"]:
            st.sidebar.write("•", v)
        if st.sidebar.button("❌ Effacer toutes les villes"):
            st.session_state["villes"] = []
            st.session_state.pop("repere_coords", None)
            st.rerun()

    # Rayon : uniquement si une seule ville
    if len(st.session_state["villes"]) == 1:
        radius = st.sidebar.number_input("Rayon (km)", min_value=0.0, step=1.0, value=0.0)
    else:
        radius = 0.0

    # Surface
    surface_min = st.sidebar.number_input("Surface min (m²)", min_value=0.0, step=5.0, value=0.0)
    surface_max = st.sidebar.number_input("Surface max (m²)", min_value=0.0, step=5.0, value=500.0)

    # DPE / GES → cases à cocher
    st.sidebar.markdown("#### Classes DPE")
    dpe_selected = [c for c in ["A", "B", "C", "D", "E", "F", "G"]
                    if st.sidebar.checkbox(c, value=True, key=f"dpe_{c}")]
    st.sidebar.markdown("#### Classes GES")
    ges_selected = [c for c in ["A", "B", "C", "D", "E", "F", "G"]
                    if st.sidebar.checkbox(c, value=True, key=f"ges_{c}")]

    map_type = st.sidebar.selectbox("Type de carte", ["Classique", "Satellite"])
    show_postal_layer = st.sidebar.checkbox("Afficher les contours des codes postaux", value=True)
    show_cadastre = st.sidebar.checkbox("Afficher les parcelles cadastrales (WMS)", value=False)

    launch = st.sidebar.button("🚀 Lancer la recherche")

    # -------------------------------------------------------
    # INITIALISATION DE LA CARTE
    # -------------------------------------------------------
    tiles = "OpenStreetMap" if map_type == "Classique" else "Esri.WorldImagery"

    villes_coords = []
    for v in st.session_state["villes"]:
        nom = v.split("(")[0].strip()
        g = geocode_city(nom)
        if g:
            villes_coords.append((g["lat"], g["lon"]))

    # Centre automatique
    if len(villes_coords) == 1:
        map_center = villes_coords[0]
        zoom_level = 12
    elif len(villes_coords) > 1:
        lat = sum(c[0] for c in villes_coords) / len(villes_coords)
        lon = sum(c[1] for c in villes_coords) / len(villes_coords)
        map_center = (lat, lon)
        zoom_level = 9
    else:
        map_center = [46.6, 2.4]
        zoom_level = 6

    m = folium.Map(location=map_center, zoom_start=zoom_level, tiles=tiles)

    # Repères automatiques
    for c, v in zip(villes_coords, st.session_state["villes"]):
        folium.Marker(location=c, tooltip=v, icon=folium.Icon(color="red", icon="flag")).add_to(m)

    # Cercle de rayon si applicable
    if radius > 0 and villes_coords:
        folium.Circle(
            location=villes_coords[0],
            radius=radius * 1000,
            color="#3186cc",
            fill=True,
            fill_color="#3186cc",
            fill_opacity=0.2,
            popup=f"Rayon de {radius} km"
        ).add_to(m)

    # Carte cliquable pour repère manuel
    st.markdown("### 🖱️ Cliquez sur la carte pour définir un repère manuel")
    map_click = st_folium(m, width=1200, height=550)
    if map_click and map_click.get("last_clicked"):
        lat = map_click["last_clicked"]["lat"]
        lon = map_click["last_clicked"]["lng"]
        st.session_state["repere_coords"] = (lat, lon)
        st.success(f"Repère défini à ({round(lat,4)}, {round(lon,4)}) ✅")

    # -------------------------------------------------------
    # LANCEMENT DE LA RECHERCHE
    # -------------------------------------------------------
    if launch:
        villes = [v.split("(")[0].strip() for v in st.session_state["villes"]]
        bary = compute_barycenter(villes) if villes else None

        if not bary:
            st.warning("Aucune ville valide sélectionnée.")
            st.stop()

        # Codes postaux liés aux villes
        code_postaux = []
        for v in villes:
            g = geocode_city(v)
            if g and g["code_postal"]:
                code_postaux.append(g["code_postal"])

        # Rayon → villes concernées
        if radius > 0:
            cp_rayon = get_postal_codes_in_radius(bary, radius)
            code_postaux.extend(cp_rayon)
            st.markdown("#### 🗺️ Villes concernées dans le rayon :")
            for cp in cp_rayon:
                st.write(f"- {cp}")

        code_postaux = sorted(list(set(code_postaux)))

        # Filtres actifs
        st.subheader("🎯 Filtres actifs")
        with st.expander("Voir les filtres", expanded=True):
            st.markdown(f"**Villes :** {', '.join(st.session_state['villes']) or 'aucune'}")
            st.markdown(f"**Rayon :** {radius} km")
            st.markdown(f"**Codes postaux :** {', '.join(code_postaux) or 'aucun'}")
            st.markdown(f"**Surface :** {surface_min}-{surface_max} m²")
            st.markdown(f"**DPE :** {', '.join(dpe_selected)} / **GES :** {', '.join(ges_selected)}")

        # Récupération des données ADEME
        df = fetch_ademe_all(code_postaux)
        if df.empty:
            st.warning("Aucun résultat trouvé.")
            return

        # Filtres
        df = df[
            df["classe_consommation_energie"].isin(dpe_selected)
            & df["classe_estimation_ges"].isin(ges_selected)
        ]
        df = df[
            (df["surface_habitable_logement"] >= surface_min)
            & (df["surface_habitable_logement"] <= surface_max)
        ]

        if radius > 0:
            df = filter_ademe_data_by_radius(df, bary[0], bary[1], radius)

        if df.empty:
            st.warning("Aucun résultat ne correspond aux filtres.")
            return

        # Calques contours postaux
        if show_postal_layer and code_postaux:
            geojson = get_postalcode_geojson(code_postaux)
            if geojson:
                folium.GeoJson(
                    geojson,
                    name="Contours postaux",
                    style_function=lambda x: {
                        "color": "#ff7800",
                        "weight": 2,
                        "opacity": 0.7,
                        "fillOpacity": 0.05
                    },
                    tooltip=folium.GeoJsonTooltip(fields=["nom", "codePostal"])
                ).add_to(m)

        # Couches cadastrales
        if show_cadastre:
            folium.raster_layers.WmsTileLayer(
                url="https://wxs.ign.fr/cadastre/geoportail/r/wms",
                layers="CADASTRALPARCELS.PARCELS",
                name="Cadastre",
                fmt="image/png",
                transparent=True,
                opacity=0.6,
                attribution="© IGN Cadastre"
            ).add_to(m)

        # Marqueurs + DVF
        cluster = MarkerCluster().add_to(m)
        for _, r in df.iterrows():
            dvf = get_dvf_data(r.get("code_postal", ""), voie=r.get("adresse_nom_voie", ""))
            dvf_html = "<hr><b>Historique DVF :</b><br>" if dvf else "<i>Pas de ventes DVF récentes</i>"
            for v in dvf:
                prix_m2 = (
                    round(v["valeur_fonciere"] / v["surface"], 0)
                    if v["surface"] and v["valeur_fonciere"]
                    else "?"
                )
                dvf_html += f"{v['date']} — {v['type']} : {prix_m2} €/m²<br>"

            popup = f"""
            <b>{r.get('adresse_nom_voie','?')}</b><br>
            DPE: {r.get('classe_consommation_energie','?')}<br>
            GES: {r.get('classe_estimation_ges','?')}<br>
            Surface: {r.get('surface_habitable_logement','?')} m²<br>
            {dvf_html}
            """
            folium.Marker(
                location=[r["latitude"], r["longitude"]],
                popup=popup,
                icon=folium.Icon(color="blue", icon="home", prefix="fa"),
            ).add_to(cluster)

        folium.LayerControl().add_to(m)
        st_folium(m, width=1200, height=700)

        # Tableau + export
        display_cols = [
            "adresse_nom_voie", "code_postal", "commune",
            "surface_habitable_logement", "nombre_batiments",
            "classe_consommation_energie", "classe_estimation_ges"
        ]
        existing_cols = [c for c in display_cols if c in df.columns]
        st.dataframe(df[existing_cols])
        st.download_button("⬇️ Export CSV", df[existing_cols].to_csv(index=False), "resultats_dpe.csv")
