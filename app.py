import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from utils import geocode_city, parse_leboncoin_html, fetch_ademe_all, distance_km
from filters.storage import save_filter, load_filters, delete_filter

st.set_page_config(page_title="Recherche DPE interactive", layout="wide")
st.title("🏠 Recherche interactive DPE (Open Data France)")

# --- Initialisation session_state ---
if 'df_results' not in st.session_state:
    st.session_state.df_results = pd.DataFrame()
if 'clicked_lat' not in st.session_state:
    st.session_state.clicked_lat = None
if 'clicked_lon' not in st.session_state:
    st.session_state.clicked_lon = None
if 'selected_marker' not in st.session_state:
    st.session_state.selected_marker = None

# --- Sidebar : filtres ---
st.sidebar.header("Filtres principaux")
classe_energie_sel = st.sidebar.multiselect("Classe énergie (DPE)", list("ABCDEFG"), st.session_state.get("classe_energie", []))
classe_ges_sel = st.sidebar.multiselect("Classe GES", list("ABCDEFG"), st.session_state.get("classe_ges", []))
surface_slider = st.sidebar.slider("Surface (m²)", 0, 500, (st.session_state.get("surface_min",0), st.session_state.get("surface_max",200)))
code_postaux_input = st.sidebar.text_input("Code(s) postal(aux)", st.session_state.get("code_postal",""))
ville_input = st.sidebar.text_input("Ville", st.session_state.get("ville",""))
rayon_km = st.sidebar.slider("Rayon de recherche (km)", 1, 50, 10)

center_mode = st.sidebar.selectbox("Mode de centre :", ["Centre officiel (ville)", "Cliquer sur la carte"])
pagination_mode = st.sidebar.selectbox("Mode pagination :", ["Toutes les pages", "Limiter"])
max_pages = st.sidebar.number_input("Max pages", 1, 50, 5) if pagination_mode != "Toutes les pages" else None

# --- Carte pour sélection si mode 'Cliquer' ---
st.subheader("Sélection du centre sur la carte (si mode 'Cliquer')")
if center_mode == "Cliquer sur la carte":
    m_click = folium.Map(location=[46.6, 2.4], zoom_start=6)
    map_data = st_folium(m_click, height=300)
    if map_data and map_data["last_clicked"]:
        st.session_state.clicked_lat = map_data["last_clicked"]["lat"]
        st.session_state.clicked_lon = map_data["last_clicked"]["lng"]
        st.success(f"Centre sélectionné : {st.session_state.clicked_lat:.4f}, {st.session_state.clicked_lon:.4f}")

# --- Lancer recherche ---
if st.sidebar.button("🔎 Lancer la recherche"):

    smin, smax = surface_slider
    center_lat, center_lon = None, None

    if center_mode=="Cliquer" and st.session_state.clicked_lat:
        center_lat, center_lon = st.session_state.clicked_lat, st.session_state.clicked_lon
    elif center_mode=="Centre officiel (ville)" and ville_input:
        center_lat, center_lon = geocode_city(ville_input)

    q = ville_input or code_postaux_input
    raw_rows = fetch_ademe_all(q, page_mode_all=(pagination_mode=="Toutes les pages"), max_pages=max_pages)
    if not raw_rows:
        st.warning("Aucun résultat trouvé.")
        st.session_state.df_results = pd.DataFrame()
        st.stop()

    df = pd.DataFrame(raw_rows)
    df = df.dropna(subset=["latitude","longitude"])

    # --- Filtrage ---
    if "classe_consommation_energie" in df.columns and classe_energie_sel:
        df = df[df["classe_consommation_energie"].isin(classe_energie_sel)]
    if "classe_estimation_ges" in df.columns and classe_ges_sel:
        df = df[df["classe_estimation_ges"].isin(classe_ges_sel)]
    if "surface_habitable_logement" in df.columns:
        df = df[(df["surface_habitable_logement"] >= smin) & (df["surface_habitable_logement"] <= smax)]

    # Filtrage par rayon
    if center_lat and "latitude" in df.columns:
        df["dist"] = df.apply(lambda r: distance_km(center_lat, center_lon, r["latitude"], r["longitude"]), axis=1)
        df = df[df["dist"] <= rayon_km]

    st.session_state.df_results = df
    st.success(f"{len(df)} résultats trouvés")

# --- Affichage carte + popup + satellite + LayerControl ---
if not st.session_state.df_results.empty:
    df = st.session_state.df_results
    latc, lonc = df["latitude"].mean(), df["longitude"].mean()
    # Choisir le centre selon ligne sélectionnée
    if st.session_state.selected_marker:
        latc, lonc = st.session_state.selected_marker

    m = folium.Map(location=[latc, lonc], zoom_start=12)
    # Tiles pour choisir vue
    folium.TileLayer('OpenStreetMap').add_to(m)
    folium.TileLayer('Stamen Terrain').add_to(m)
    folium.TileLayer('Stamen Toner').add_to(m)
    folium.TileLayer('Esri.WorldImagery').add_to(m)
    folium.LayerControl().add_to(m)

    mc = MarkerCluster().add_to(m)

    for _, r in df.iterrows():
        # Adresse complète
        adresse = ""
        if r.get("adresse_numero_voie"):
            adresse += f"{r['adresse_numero_voie']} "
        if r.get("adresse_nom_voie"):
            adresse += f"{r['adresse_nom_voie']}, "
        if r.get("code_postal"):
            adresse += f"{r['code_postal']} "
        if r.get("commune"):
            adresse += f"{r['commune']}"

        # DPE / GES / surface / nb bâtiments / dates
        dpe = r.get("classe_consommation_energie", "?")
        dpe_date = r.get("date_consommation_energie", "?")
        ges = r.get("classe_estimation_ges", "?")
        ges_date = r.get("date_estimation_ges", "?")
        surface = r.get("surface_habitable_logement", "?")
        nb_batiments = r.get("nombre_batiments", "?")

        popup_html = (
            f"<b>Adresse :</b> {adresse}<br>"
            f"<b>DPE :</b> {dpe} (date: {dpe_date})<br>"
            f"<b>GES :</b> {ges} (date: {ges_date})<br>"
            f"<b>Surface habitable :</b> {surface} m²<br>"
            f"<b>Nombre de bâtiments :</b> {nb_batiments}"
        )

        folium.Marker(
            [r["latitude"], r["longitude"]],
            popup=popup_html
        ).add_to(mc)

    st.subheader("Carte des résultats")
    st_folium(m, width=1000, height=600)

    # --- Tableau interactif ---
    st.subheader("Tableau des résultats")
    # Colonnes à afficher dans le tableau
    display_cols = ["adresse_numero_voie","adresse_nom_voie","code_postal","commune",
                    "classe_consommation_energie","date_consommation_energie",
                    "classe_estimation_ges","date_estimation_ges",
                    "surface_habitable_logement","nombre_batiments","latitude","longitude"]
    display_df = df[display_cols].copy()

    selected_row_idx = st.data_editor(display_df, use_container_width=True, num_rows="dynamic", key="table_selection")
    
    # Centrer carte sur la ligne sélectionnée
    if selected_row_idx is not None and len(selected_row_idx) > 0:
        # Récupérer première ligne sélectionnée
        row = display_df.iloc[selected_row_idx[0]]
        st.session_state.selected_marker = (row["latitude"], row["longitude"])
        st.experimental_rerun()

    # Export CSV
    st.download_button(
        "Exporter CSV",
        df.to_csv(index=False).encode("utf-8"),
        "resultats_dpe.csv",
        "text/csv"
    )
