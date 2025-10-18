# app.py
import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from utils import (
    geocode_city,
    fetch_ademe_all,
    distance_km,
    save_filters,
    load_filters,
    delete_filter,
)

# ----------------------------
# Configuration page
# ----------------------------
st.set_page_config(page_title="DPE Explorer", layout="wide")
st.title("🏠 DPE Explorer — recherche et cartographie (Open Data France)")

# ----------------------------
# Variables persistantes
# ----------------------------
if "df_results" not in st.session_state:
    st.session_state.df_results = pd.DataFrame()
if "repere" not in st.session_state:
    st.session_state.repere = None  # (lat, lon) ou None
if "selected_row" not in st.session_state:
    st.session_state.selected_row = None
if "cities" not in st.session_state:
    st.session_state.cities = []  # liste de villes choisies (strings)
if "filters_saved" not in st.session_state:
    st.session_state.filters_saved = load_filters() or {}

# ----------------------------
# Sidebar : filtres (détaillés)
# ----------------------------
st.sidebar.header("🔎 Filtres de recherche")

# villes : champ texte multiple (séparées par ; ou ,)
cities_input = st.sidebar.text_input("Ville(s) (séparer par ; ou ,)", value="; ".join(st.session_state.cities) if st.session_state.cities else "")
if st.sidebar.button("Valider villes"):
    # normaliser la liste
    parts = [c.strip() for c in re_split := cities_input.replace(",", ";").split(";") if c.strip()]
    st.session_state.cities = parts
    st.experimental_rerun()

# centre selection : repere or villes center
center_choice = st.sidebar.selectbox("Centre du rayon", ["Repère (cliquer sur la carte)", "Centre(s) géographique(s) des ville(s)"], index=1)

# DPE / GES filters
dpe_choices = st.sidebar.multiselect("Classe DPE (consommation)", options=list("ABCDEFG"), default=[])
ges_choices = st.sidebar.multiselect("Classe GES", options=list("ABCDEFG"), default=[])

# Surface : slider + number inputs (synchronisés)
st.sidebar.subheader("Surface habitable (m²)")
s_min = st.sidebar.number_input("Min surface (m²)", min_value=0, max_value=5000, value=0, key="surface_min_input")
s_max = st.sidebar.number_input("Max surface (m²)", min_value=0, max_value=5000, value=200, key="surface_max_input")
# aussi un slider (visuel)
s_slider = st.sidebar.slider("Plage surface", 0, 5000, (s_min, s_max), key="surface_slider")
# Keep inputs synced
if (s_slider[0], s_slider[1]) != (s_min, s_max):
    st.session_state.surface_min_input = s_slider[0]
    st.session_state.surface_max_input = s_slider[1]

# Rayon : number input and slider
st.sidebar.subheader("Rayon (km)")
rayon_km = st.sidebar.number_input("Rayon (km)", min_value=0, max_value=500, value=10, key="rayon_input")
rayon_slider = st.sidebar.slider("Rayon visuel (km)", 0, 500, int(rayon_km), key="rayon_slider")
if rayon_slider != rayon_km:
    st.session_state.rayon_input = rayon_slider

# Pagination ADEME : toutes les pages ou nombre
st.sidebar.markdown("---")
st.sidebar.subheader("Pagination ADEME")
pagination_mode = st.sidebar.selectbox("Récupération", ["Toutes les pages (par défaut)", "Limiter le nombre de pages"], index=0)
nb_pages = None
if pagination_mode != "Toutes les pages (par défaut)":
    nb_pages = st.sidebar.number_input("Nombre max de pages", min_value=1, max_value=200, value=5, step=1)

# Save/Load filters
st.sidebar.markdown("---")
st.sidebar.subheader("Sauvegarde des filtres")
new_filter_name = st.sidebar.text_input("Nom du filtre")
colA, colB = st.sidebar.columns(2)
if colA.button("Enregistrer filtre") and new_filter_name:
    to_save = {
        "cities": st.session_state.cities,
        "dpe_choices": dpe_choices,
        "ges_choices": ges_choices,
        "surface_min": st.session_state.surface_min_input,
        "surface_max": st.session_state.surface_max_input,
        "rayon_km": st.session_state.rayon_input,
        "center_choice": center_choice,
        "pagination_mode": pagination_mode,
        "nb_pages": nb_pages or 0
    }
    save_filters(new_filter_name, to_save)
    st.session_state.filters_saved = load_filters()
    st.sidebar.success("Filtre enregistré ✅")

saved = st.session_state.filters_saved or {}
saved_keys = [""] + list(saved.keys())
chosen_saved = st.sidebar.selectbox("Filtres sauvegardés", saved_keys)
if chosen_saved:
    if st.sidebar.button("Charger filtre"):
        f = saved[chosen_saved]
        st.session_state.cities = f.get("cities", [])
        st.session_state.surface_min_input = f.get("surface_min", 0)
        st.session_state.surface_max_input = f.get("surface_max", 200)
        st.session_state.rayon_input = f.get("rayon_km", 10)
        # set dpe/ges choices by reloading page (we can't directly set multiselect default values here)
        # workaround: store in session_state and re-run to let UI pick them up
        st.session_state._temp_load_dpe = f.get("dpe_choices", [])
        st.session_state._temp_load_ges = f.get("ges_choices", [])
        st.experimental_rerun()
if st.sidebar.button("Supprimer filtre sélectionné") and chosen_saved:
    delete_filter(chosen_saved)
    st.session_state.filters_saved = load_filters()
    st.sidebar.success("Filtre supprimé ✅")

# Set multiselect defaults from session_state temp if present
if "_temp_load_dpe" in st.session_state:
    dpe_choices = st.sidebar.multiselect("Classe DPE (consommation)", options=list("ABCDEFG"), default=st.session_state._temp_load_dpe)
    del st.session_state["_temp_load_dpe"]
if "_temp_load_ges" in st.session_state:
    ges_choices = st.sidebar.multiselect("Classe GES", options=list("ABCDEFG"), default=st.session_state._temp_load_ges)
    del st.session_state["_temp_load_ges"]

st.sidebar.markdown("---")
if st.sidebar.button("🔎 Lancer la recherche"):
    # Build query q string from cities or empty
    q = " ".join(st.session_state.cities) if st.session_state.cities else ""
    # Determine pages param
    pages_param = None if pagination_mode.startswith("Toutes") else int(nb_pages or 5)
    # Determine center coords
    center_coords = None
    if center_choice.startswith("Repère") and st.session_state.repere:
        center_coords = st.session_state.repere
    else:
        # average coordinates of selected cities
        coords_list = []
        for c in st.session_state.cities:
            g = geocode_city(c)
            if g:
                coords_list.append(g)
        if coords_list:
            avg_lat = sum([x[0] for x in coords_list]) / len(coords_list)
            avg_lon = sum([x[1] for x in coords_list]) / len(coords_list)
            center_coords = (avg_lat, avg_lon)
    # fetch ADEME
    try:
        raw = fetch_ademe_all(q=q, pages=pages_param)
        if raw is None or raw.empty:
            st.session_state.df_results = pd.DataFrame()
            st.warning("Aucun résultat ADEME pour la requête.")
        else:
            df = raw.copy()
            # ensure lat/lon columns exist or try alternative keys
            # standardize column names if necessary
            # fill missing expected columns with '?'
            expected = [
                "adresse_numero_voie",
                "adresse_nom_voie",
                "code_postal",
                "commune",
                "surface_habitable_logement",
                "nombre_batiments",
                "classe_consommation_energie",
                "date_consommation_energie",
                "classe_estimation_ges",
                "date_estimation_ges",
                "latitude",
                "longitude"
            ]
            for col in expected:
                if col not in df.columns:
                    df[col] = "?"
            # convert lat/lon to numeric where possible
            try:
                df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
                df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
            except Exception:
                pass
            # drop rows without coords
            if "latitude" in df.columns and "longitude" in df.columns:
                df = df.dropna(subset=["latitude", "longitude"])
            # apply surface filter
            smin = st.session_state.surface_min_input
            smax = st.session_state.surface_max_input
            if "surface_habitable_logement" in df.columns:
                df_filtered = df[
                    (pd.to_numeric(df["surface_habitable_logement"], errors="coerce").fillna(-1) >= smin) &
                    (pd.to_numeric(df["surface_habitable_logement"], errors="coerce").fillna(-1) <= smax)
                ]
            else:
                df_filtered = df
            # apply DPE / GES filters if any
            if dpe_choices:
                df_filtered = df_filtered[df_filtered["classe_consommation_energie"].isin(dpe_choices)]
            if ges_choices:
                df_filtered = df_filtered[df_filtered["classe_estimation_ges"].isin(ges_choices)]
            # apply radius if center defined
            if center_coords and rayon_km > 0:
                latc, lonc = center_coords
                df_filtered["__dist"] = df_filtered.apply(lambda r: distance_km(latc, lonc, float(r["latitude"]), float(r["longitude"])), axis=1)
                df_filtered = df_filtered[df_filtered["__dist"] <= rayon_km]
                df_filtered = df_filtered.drop(columns=["__dist"], errors='ignore')
            # store results
            st.session_state.df_results = df_filtered.reset_index(drop=True)
            st.success(f"{len(st.session_state.df_results)} résultats après application des filtres.")
    except Exception as e:
        st.error(f"Erreur durant la récupération ADEME : {e}")

# ----------------------------
# Zone principale : carte (toujours visible) et tableau
# ----------------------------
col_map, col_info = st.columns([3,1])
with col_map:
    st.subheader("🗺 Carte (cliquez pour placer le repère)")
    # compute initial center:
    if st.session_state.repere:
        map_center = st.session_state.repere
    else:
        # center on average of cities if any, else France center
        if st.session_state.cities:
            coords_list = [geocode_city(c) for c in st.session_state.cities]
            coords_list = [c for c in coords_list if c]
            if coords_list:
                map_center = (sum([c[0] for c in coords_list])/len(coords_list), sum([c[1] for c in coords_list])/len(coords_list))
            else:
                map_center = (46.6, 2.4)
        else:
            map_center = (46.6, 2.4)

    m = folium.Map(location=map_center, zoom_start=12)
    # Tiles: plan + satellite
    folium.TileLayer("OpenStreetMap", name="Plan").add_to(m)
    folium.TileLayer("Esri.WorldImagery", name="Satellite").add_to(m)
    folium.LayerControl().add_to(m)

    # If repere exists, show it as a distinctive marker
    if st.session_state.repere:
        folium.Marker(
            location=st.session_state.repere,
            icon=folium.Icon(color="red", icon="crosshairs", prefix='fa'),
            popup="Repère (centre possible)"
        ).add_to(m)

    # Plot results as markers (clustered)
    df_show = st.session_state.df_results.copy() if not st.session_state.df_results.empty else pd.DataFrame()
    mc = MarkerCluster().add_to(m)
    for idx, row in df_show.iterrows():
        # build popup html
        adresse = " ".join([str(x) for x in [row.get("adresse_numero_voie","?"), row.get("adresse_nom_voie","?")] if x and x != "?"])
        adresse = adresse + (", " + str(row.get("code_postal","?")) + " " + str(row.get("commune","?")) if row.get("commune","?") != "?" else "")
        popup_html = (
            f"<b>Adresse :</b> {adresse}<br>"
            f"<b>Surface :</b> {row.get('surface_habitable_logement','?')} m²<br>"
            f"<b>Nombre de bâtiments :</b> {row.get('nombre_batiments','?')}<br>"
            f"<b>DPE :</b> {row.get('classe_consommation_energie','?')} (date: {row.get('date_consommation_energie','?')})<br>"
            f"<b>GES :</b> {row.get('classe_estimation_ges','?')} (date: {row.get('date_estimation_ges','?')})"
        )
        # if this row is the selected one, show popup immediately
        show_flag = False
        if st.session_state.selected_row is not None and st.session_state.selected_row == int(idx):
            popup = folium.Popup(popup_html, max_width=300, show=True)
            folium.Marker([row["latitude"], row["longitude"]], popup=popup, icon=folium.Icon(color="blue")).add_to(mc)
            # Also center the map on this marker
            m.location = [row["latitude"], row["longitude"]]
            m.zoom_start = 16
            # reset selection after rendering so further clicks work
            st.session_state.selected_row = None
        else:
            popup = folium.Popup(popup_html, max_width=300, show=False)
            folium.Marker([row["latitude"], row["longitude"]], popup=popup).add_to(mc)

    # Capture clicks on the map to set the repere
    map_result = st_folium(m, height=700, returned_objects=["last_clicked"])
    if map_result and map_result.get("last_clicked"):
        lat_clicked = map_result["last_clicked"]["lat"]
        lon_clicked = map_result["last_clicked"]["lng"]
        st.session_state.repere = (lat_clicked, lon_clicked)
        st.experimental_rerun()

with col_info:
    st.subheader("Filtres actifs")
    # Show summary of active filters
    st.write("**Villes :**", ", ".join(st.session_state.cities) if st.session_state.cities else "Aucune")
    st.write("**Repère :**", f"{st.session_state.repere[0]:.5f}, {st.session_state.repere[1]:.5f}" if st.session_state.repere else "Aucun")
    st.write("**Surface :**", f"{st.session_state.surface_min_input} - {st.session_state.surface_max_input} m²")
    st.write("**Rayon :**", f"{st.session_state.rayon_input} km")
    st.write("**DPE :**", ", ".join(dpe_choices) if dpe_choices else "Tous")
    st.write("**GES :**", ", ".join(ges_choices) if ges_choices else "Tous")

# ----------------------------
# Tableau (toujours visible)
# ----------------------------
st.subheader("📋 Résultats")
# define display columns required
display_cols = [
    "adresse_numero_voie",
    "adresse_nom_voie",
    "code_postal",
    "commune",
    "surface_habitable_logement",
    "nombre_batiments",
    "classe_consommation_energie",
    "date_consommation_energie",
    "classe_estimation_ges",
    "date_estimation_ges",
    "latitude",
    "longitude",
]
# if no results yet: show only headers
if st.session_state.df_results.empty:
    empty_df = pd.DataFrame(columns=display_cols)
    st.dataframe(empty_df, use_container_width=True)
else:
    # ensure all columns exist, fill with default
    df_table = st.session_state.df_results.copy()
    for c in display_cols:
        if c not in df_table.columns:
            df_table[c] = "?"
    df_table = df_table[display_cols].reset_index(drop=True)
    # show table
    st.dataframe(df_table, use_container_width=True)
    # selection to center and show popup
    sel = st.number_input("Sélectionner l'index d'une ligne pour centrer/voir le popup (index affiché dans la première colonne)", min_value=0, max_value=max(0, len(df_table)-1), value=0, step=1)
    if st.button("📍 Centrer sur la ligne sélectionnée"):
        st.session_state.selected_row = int(sel)
        st.experimental_rerun()

# ----------------------------
# Export CSV
# ----------------------------
st.sidebar.markdown("---")
if not st.session_state.df_results.empty:
    csv = st.session_state.df_results.to_csv(index=False).encode("utf-8")
    st.sidebar.download_button("📥 Exporter CSV", csv, "resultats_dpe.csv", "text/csv")
else:
    st.sidebar.write("Aucun résultat à exporter.")
