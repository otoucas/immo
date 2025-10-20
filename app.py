import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import pandas as pd
import requests

from utils import (
    save_filter,
    load_filters,
    delete_saved_filter,
    geocode_city,
    compute_barycenter,
    filter_ademe_data_by_radius,
    fetch_ademe_all,
    get_dvf_data,
    get_postalcode_geojson,
    get_postal_codes_in_radius,
)

# -------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------
st.set_page_config(page_title="Carte DPE + DVF + Cadastre", layout="wide")
st.title("🏠 Carte DPE / GES + DVF + Calques postaux & cadastraux + Repère manuel")

# -------------------------------------------------------
# SIDEBAR : FILTRES
# -------------------------------------------------------
st.sidebar.header("🎛️ Filtres de recherche")

# --- Villes ---
villes_input = st.sidebar.text_input(
    "Villes (séparées par des virgules)",
    placeholder="Ex : Lyon, Grenoble, Annecy"
)
villes = [v.strip() for v in villes_input.split(",") if v.strip()]

# --- Rayon ---
radius = st.sidebar.number_input("Rayon (km)", min_value=0.0, step=1.0, value=0.0)

# --- Surface ---
surface_min = st.sidebar.number_input("Surface min (m²)", min_value=0.0, step=5.0, value=0.0)
surface_max = st.sidebar.number_input("Surface max (m²)", min_value=0.0, step=5.0, value=500.0)

# --- DPE & GES ---
dpe_classes = ["A", "B", "C", "D", "E", "F", "G"]
dpe_selected = st.sidebar.multiselect("Classe DPE", dpe_classes, default=dpe_classes)
ges_selected = st.sidebar.multiselect("Classe GES", dpe_classes, default=dpe_classes)

# --- Calques ---
map_type = st.sidebar.selectbox("Type de carte", ["Classique", "Satellite"])
show_postal_layer = st.sidebar.checkbox("Afficher les contours des codes postaux", value=True)
show_cadastre = st.sidebar.checkbox("Afficher les parcelles cadastrales (WMS)", value=False)

# --- Sauvegarde / Chargement filtres ---
st.sidebar.markdown("#### 💾 Sauvegarde des filtres")
saved_filters = load_filters()
selected_save = st.sidebar.selectbox("Filtres enregistrés", ["Aucun"] + list(saved_filters.keys()))

if selected_save != "Aucun":
    fdata = saved_filters[selected_save]
    st.sidebar.json(fdata)
    if st.sidebar.button("🗑️ Supprimer ce filtre"):
        delete_saved_filter(selected_save)
        st.sidebar.success(f"Filtre '{selected_save}' supprimé ✅")

new_filter_name = st.sidebar.text_input("Nom du filtre à enregistrer")
if st.sidebar.button("💾 Enregistrer ce filtre"):
    save_filter(new_filter_name, {
        "villes": villes,
        "radius": radius,
        "surface_min": surface_min,
        "surface_max": surface_max,
        "dpe": dpe_selected,
        "ges": ges_selected,
        "map_type": map_type,
        "show_postal_layer": show_postal_layer,
        "show_cadastre": show_cadastre
    })
    st.sidebar.success(f"Filtre '{new_filter_name}' enregistré ✅")

launch = st.sidebar.button("🚀 Lancer la recherche")

# -------------------------------------------------------
# INITIALISATION DE LA CARTE
# -------------------------------------------------------
tiles = "OpenStreetMap" if map_type == "Classique" else "Esri.WorldImagery"
repere_coords = st.session_state.get("repere_coords", None)
zoom_level = st.session_state.get("zoom_level", 6)
map_center = repere_coords if repere_coords else [46.6, 2.4]

m = folium.Map(location=map_center, zoom_start=zoom_level, tiles=tiles)

# --- Repère existant ---
if repere_coords:
    folium.Marker(
        location=repere_coords,
        tooltip="📍 Repère manuel",
        icon=folium.Icon(color="red", icon="flag")
    ).add_to(m)

    # Cercle de rayon
    if radius > 0:
        folium.Circle(
            location=repere_coords,
            radius=radius * 1000,
            color="#3186cc",
            fill=True,
            fill_color="#3186cc",
            fill_opacity=0.2,
            popup=f"Rayon de {radius} km"
        ).add_to(m)

# -------------------------------------------------------
# INTERACTION : CLIC SUR LA CARTE
# -------------------------------------------------------
st.markdown("### 🖱️ Cliquez sur la carte pour définir un repère de recherche")
st.info("Le repère servira de centre pour le rayon, les codes postaux et la recherche ADEME/DVF.")

map_click = st_folium(m, width=1200, height=550)
if map_click and map_click.get("last_clicked"):
    lat = map_click["last_clicked"]["lat"]
    lon = map_click["last_clicked"]["lng"]
    st.session_state["repere_coords"] = (lat, lon)
    st.session_state["zoom_level"] = 12  # ✅ zoom automatique sur clic
    st.success(f"Repère défini à ({round(lat,4)}, {round(lon,4)}) ✅")

# -------------------------------------------------------
# RECHERCHE
# -------------------------------------------------------
if launch:
    bary = None
    if villes:
        bary = compute_barycenter(villes)

    if repere_coords:
        bary = repere_coords
        st.info(f"📍 Recherche centrée sur le repère ({round(bary[0],4)}, {round(bary[1],4)})")
    elif not bary:
        st.warning("Aucune ville ni repère valide. Veuillez définir un point de recherche.")
        st.stop()

    # Codes postaux depuis les villes
    code_postaux = []
    for city in villes:
        url = f"https://api-adresse.data.gouv.fr/search/?q={city}&type=municipality"
        r = requests.get(url, timeout=10)
        if r.status_code == 200 and r.json().get("features"):
            cp = r.json()["features"][0]["properties"]["postcode"]
            if cp:
                code_postaux.append(cp)

    # Codes postaux dans le rayon
    if radius > 0 and bary:
        rayon_cp = get_postal_codes_in_radius(bary, radius)
        code_postaux.extend(rayon_cp)

    code_postaux = sorted(list(set(code_postaux)))

    # --- Filtres actifs ---
    st.subheader("🎯 Filtres appliqués")
    with st.expander("Voir le détail des filtres actifs", expanded=True):
        st.markdown(f"**Villes :** {', '.join(villes) if villes else 'aucune'}")
        st.markdown(f"**Repère :** {bary if bary else 'non défini'}")
        st.markdown(f"**Codes postaux concernés :** {', '.join(code_postaux) if code_postaux else 'aucun'}")
        st.markdown(f"**Rayon :** {radius} km")
        st.markdown(f"**Surface :** {surface_min} – {surface_max} m²")
        st.markdown(f"**DPE :** {', '.join(dpe_selected)} / **GES :** {', '.join(ges_selected)}")

    # --- Données ADEME ---
    df = fetch_ademe_all(code_postaux)
    for col in ["classe_consommation_energie", "classe_estimation_ges", "surface_habitable_logement"]:
        if col not in df.columns:
            df[col] = None

    if "classe_consommation_energie" in df.columns:
        df = df[df["classe_consommation_energie"].isin(dpe_selected)]
    if "classe_estimation_ges" in df.columns:
        df = df[df["classe_estimation_ges"].isin(ges_selected)]
    if "surface_habitable_logement" in df.columns:
        df = df[
            (df["surface_habitable_logement"] >= surface_min)
            & (df["surface_habitable_logement"] <= surface_max)
        ]

    if radius > 0 and bary:
        df = filter_ademe_data_by_radius(df, bary[0], bary[1], radius)

    if df.empty:
        st.warning("Aucun résultat trouvé pour ces critères.")
    else:
        st.success(f"{len(df)} enregistrements ADEME trouvés ✅")

        # --- Calque contours postaux ---
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
                        "opacity": 0.7,
                    },
                    tooltip=folium.GeoJsonTooltip(
                        fields=["nom", "codePostal"],
                        aliases=["Commune", "Code postal"],
                    ),
                ).add_to(m)

        # --- Calque cadastral (WMS) ---
        if show_cadastre:
            folium.raster_layers.WmsTileLayer(
                url="https://wxs.ign.fr/cadastre/geoportail/r/wms",
                layers="CADASTRALPARCELS.PARCELS",
                name="Parcelles cadastrales",
                fmt="image/png",
                transparent=True,
                opacity=0.6,
                attribution="© IGN Cadastre",
            ).add_to(m)

        # --- Marqueurs DPE + DVF ---
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
                icon=folium.Icon(color="blue", icon="home", prefix="fa"),
            ).add_to(marker_cluster)

        folium.LayerControl().add_to(m)

# -------------------------------------------------------
# AFFICHAGE FINAL
# -------------------------------------------------------
st_folium(m, width=1200, height=700)

if launch and "df" in locals() and not df.empty:
    st.subheader("📋 Résultats détaillés")
    display_cols = [
        "adresse_nom_voie", "code_postal", "commune",
        "surface_habitable_logement", "nombre_batiments",
        "classe_consommation_energie", "classe_estimation_ges"
    ]
    existing_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(df[existing_cols])
    csv = df[existing_cols].to_csv(index=False)
    st.download_button("⬇️ Export CSV", csv, "resultats_dpe.csv", "text/csv")
