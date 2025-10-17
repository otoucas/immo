import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from utils import geocode_city, parse_leboncoin_html, fetch_ademe_all, distance_km
from filters.storage import save_filter, load_filters, delete_filter

st.set_page_config(page_title="Recherche DPE interactive", layout="wide")
st.title("🏠 Recherche interactive DPE (Open Data France)")

# Colonnes affichées dans la carte et le tableau
display_cols = [
    "adresse_numero_voie",
    "adresse_nom_voie",
    "code_postal",
    "commune",
    "classe_consommation_energie",
    "date_consommation_energie",
    "classe_estimation_ges",
    "date_estimation_ges",
    "surface_habitable_logement",
    "nombre_batiments",
    "latitude",
    "longitude",
]

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

st.sidebar.subheader("Surface habitable (m²)")
surface_min = st.sidebar.number_input("Min", 0, 1000, value=st.session_state.get("surface_min", 0))
surface_max = st.sidebar.number_input("Max", 0, 1000, value=st.session_state.get("surface_max", 200))

st.sidebar.subheader("Rayon de recherche (km)")
rayon_km = st.sidebar.number_input("Rayon autour du centre", 0, 100, value=st.session_state.get("rayon_km", 10))

code_postaux_input = st.sidebar.text_input("Code(s) postal(aux)", st.session_state.get("code_postal",""))
ville_input = st.sidebar.text_input("Ville", st.session_state.get("ville",""))

center_mode = st.sidebar.selectbox("Mode de centre :", ["Centre officiel (ville)", "Cliquer sur la carte"])
pagination_mode = st.sidebar.selectbox("Mode pagination :", ["Toutes les pages", "Limiter"])
max_pages = st.sidebar.number_input("Max pages", 1, 50, 5) if pagination_mode != "Toutes les pages" else None

# --- Sauvegarde / chargement filtres ---
st.sidebar.markdown("---")
st.sidebar.subheader("💾 Sauvegarde / chargement filtres")
saved_filters = load_filters()
filter_names = list(saved_filters.keys())
filter_select = st.sidebar.selectbox("Filtres sauvegardés", ["---"]+filter_names)

col1, col2 = st.sidebar.columns(2)
with col1:
    if st.button("Charger filtre") and filter_select != "---":
        st.session_state.update(saved_filters[filter_select])
        st.experimental_rerun()
with col2:
    if st.button("Supprimer filtre") and filter_select != "---":
        delete_filter(filter_select)
        st.experimental_rerun()

new_filter_name = st.sidebar.text_input("Nom nouveau filtre")
if st.sidebar.button("Enregistrer filtre") and new_filter_name:
    save_filter(new_filter_name, {
        "classe_energie": classe_energie_sel,
        "classe_ges": classe_ges_sel,
        "surface_min": surface_min,
        "surface_max": surface_max,
        "code_postal": code_postaux_input,
        "ville": ville_input,
        "rayon_km": rayon_km
    })
    st.sidebar.success(f"Filtre '{new_filter_name}' sauvegardé!")

# --- Filtres actifs et suppression individuelle ---
st.sidebar.markdown("---")
st.sidebar.subheader("Filtres actifs")
active_filters = []

if classe_energie_sel:
    active_filters.append(f"DPE: {', '.join(classe_energie_sel)}")
if classe_ges_sel:
    active_filters.append(f"GES: {', '.join(classe_ges_sel)}")
if surface_min != 0 or surface_max != 200:
    active_filters.append(f"Surface: {surface_min}-{surface_max} m²")
if code_postaux_input:
    active_filters.append(f"Code postal: {code_postaux_input}")
if ville_input:
    active_filters.append(f"Ville: {ville_input}")
if rayon_km != 10:
    active_filters.append(f"Rayon: {rayon_km} km")

for f in active_filters:
    col1, col2 = st.sidebar.columns([3,1])
    col1.write(f)
    if col2.button("❌", key=f):
        if "DPE" in f:
            classe_energie_sel.clear()
        elif "GES" in f:
            classe_ges_sel.clear()
        elif "Surface" in f:
            surface_min, surface_max = 0, 200
        elif "Code postal" in f:
            code_postaux_input = ""
        elif "Ville" in f:
            ville_input = ""
        elif "Rayon" in f:
            rayon_km = 10
        st.experimental_rerun()

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
        df = df[(df["surface_habitable_logement"] >= surface_min) & (df["surface_habitable_logement"] <= surface_max)]

    # Filtrage par rayon
    if center_lat and "latitude" in df.columns:
        df["dist"] = df.apply(lambda r: distance_km(center_lat, center_lon, r["latitude"], r["longitude"]), axis=1)
        df = df[df["dist"] <= rayon_km]

    # --- Remplir colonnes manquantes pour tableau ---
    display_cols = ["adresse_numero_voie","adresse_nom_voie","code_postal","commune",
                    "classe_consommation_energie","date_consommation_energie",
                    "classe_estimation_ges","date_estimation_ges",
                    "surface_habitable_logement","nombre_batiments","latitude","longitude"]
    for col in display_cols:
        if col not in df.columns:
            df[col] = "?"
    
    st.session_state.df_results = df
    st.success(f"{len(df)} résultats trouvés")

# --- Affichage carte + popup + tiles sécurisés ---
if not st.session_state.df_results.empty:
    df = st.session_state.df_results
    latc, lonc = df["latitude"].mean(), df["longitude"].mean()
    if st.session_state.selected_marker:
        latc, lonc = st.session_state.selected_marker

    m = folium.Map(location=[latc, lonc], zoom_start=12)
    folium.TileLayer('OpenStreetMap', name='Plan').add_to(m)
    folium.TileLayer('Esri.WorldImagery', name='Satellite').add_to(m)
    folium.LayerControl().add_to(m)

    mc = MarkerCluster().add_to(m)

    for _, r in df.iterrows():
        adresse = ""
        if r.get("adresse_numero_voie") != "?":
            adresse += f"{r['adresse_numero_voie']} "
        if r.get("adresse_nom_voie") != "?":
            adresse += f"{r['adresse_nom_voie']}, "
        if r.get("code_postal") != "?":
            adresse += f"{r['code_postal']} "
        if r.get("commune") != "?":
            adresse += f"{r['commune']}"

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

        folium.Marker([r["latitude"], r["longitude"]], popup=popup_html).add_to(mc)

    st.subheader("Carte des résultats")
    st_folium(m, width=1000, height=600)

# --- Tableau interactif ---
st.subheader("Tableau des résultats")
display_df = df[display_cols].copy()

# Permet la sélection d'une ligne pour recentrer la carte
st.markdown("🖱️ Cliquez sur une ligne pour centrer la carte sur l’adresse correspondante :")

# On utilise st.dataframe au lieu de st.data_editor pour un affichage pur
selected_row = st.dataframe(display_df, use_container_width=True)

# On ajoute un sélecteur par index (plus stable)
selected_index = st.selectbox("Choisir une ligne à centrer :", options=display_df.index, format_func=lambda i: f"{display_df.loc[i, 'adresse_nom_voie']} - {display_df.loc[i, 'commune']}" if 'adresse_nom_voie' in display_df.columns else f"Ligne {i+1}")

if st.button("📍 Recentrer sur cette adresse"):
    row = display_df.loc[selected_index]
    if "latitude" in row and "longitude" in row:
        st.session_state.selected_marker = (row["latitude"], row["longitude"])
        st.experimental_rerun()

    # Export CSV
    st.download_button(
        "Exporter CSV",
        display_df.to_csv(index=False).encode("utf-8"),
        "resultats_dpe.csv",
        "text/csv"
    )

