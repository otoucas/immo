import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from utils import geocode_city, parse_leboncoin_html, fetch_ademe_all, distance_km
from filters.storage import save_filter, load_filters, delete_filter

st.set_page_config(page_title="Recherche DPE interactive", layout="wide")
st.title("🏠 Recherche interactive DPE (Open Data France)")

# --- Sidebar : Filtres & LeBonCoin ---
st.sidebar.header("Filtres et import LeBonCoin")
lbc_url = st.sidebar.text_input("Collez URL ou HTML LeBonCoin")
if st.sidebar.button("Analyser l’annonce"):
    infos = parse_leboncoin_html(lbc_url)
    st.session_state.update(infos)
    st.sidebar.json(infos)

# --- Sidebar : filtres principaux ---
classe_energie_sel = st.sidebar.multiselect("Classe énergie (DPE)", list("ABCDEFG"), st.session_state.get("classe_energie", []))
classe_ges_sel = st.sidebar.multiselect("Classe GES", list("ABCDEFG"), st.session_state.get("classe_ges", []))
surface_slider = st.sidebar.slider("Surface (m²)", 0, 500, (st.session_state.get("surface_min",0), st.session_state.get("surface_max",200)))
code_postaux_input = st.sidebar.text_input("Code(s) postal(aux)", st.session_state.get("code_postal",""))
ville_input = st.sidebar.text_input("Ville", st.session_state.get("ville",""))
rayon_km = st.sidebar.slider("Rayon de recherche (km)", 1, 50, 10)

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
        "classe_energie_sel": classe_energie_sel,
        "classe_ges_sel": classe_ges_sel,
        "surface_min": surface_slider[0],
        "surface_max": surface_slider[1],
        "code_postaux_input": code_postaux_input,
        "ville": ville_input,
        "rayon_km": rayon_km
    })
    st.sidebar.success(f"Filtre '{new_filter_name}' sauvegardé!")

# --- Carte pour sélection si mode 'Cliquer'
clicked_lat, clicked_lon = None, None
if center_mode == "Cliquer sur la carte":
    st.subheader("Sélection du centre")
    m = folium.Map(location=[46.6,2.4], zoom_start=6)
    map_data = st_folium(m, height=400)
    if map_data and map_data["last_clicked"]:
        clicked_lat, clicked_lon = map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]
        st.success(f"Centre sélectionné : {clicked_lat:.4f},{clicked_lon:.4f}")

# --- Lancer recherche ---
run = st.sidebar.button("🔎 Lancer la recherche")
if run:
    smin, smax = surface_slider
    center_lat, center_lon = None, None
    if center_mode=="Cliquer" and clicked_lat:
        center_lat, center_lon = clicked_lat, clicked_lon
    elif center_mode=="Centre officiel (ville)" and ville_input:
        center_lat, center_lon = geocode_city(ville_input)

    q = ville_input or code_postaux_input
    raw_rows = fetch_ademe_all(q, page_mode_all=(pagination_mode=="Toutes les pages"), max_pages=max_pages)
    if not raw_rows:
        st.warning("Aucun résultat trouvé.")
        st.stop()

    df = pd.DataFrame(raw_rows)
    df = df.dropna(subset=["latitude","longitude"])

    # --- Filtrage sécurisé ---
    if "classe_consommation_energie" in df.columns and classe_energie_sel:
        df = df[df["classe_consommation_energie"].isin(classe_energie_sel)]
    if "classe_estimation_ges" in df.columns and classe_ges_sel:
        df = df[df["classe_estimation_ges"].isin(classe_ges_sel)]
    if "surface_habitable_logement" in df.columns:
        df = df[(df["surface_habitable_logement"] >= smin) & (df["surface_habitable_logement"] <= smax)]
    else:
        st.warning("⚠️ La donnée 'surface_habitable_logement' n'est pas disponible pour ces résultats.")

    # Filtrage par rayon
    if center_lat and "latitude" in df.columns:
        df["dist"] = df.apply(lambda r: distance_km(center_lat, center_lon, r["latitude"], r["longitude"]), axis=1)
        df = df[df["dist"] <= rayon_km]

    st.success(f"{len(df)} résultats trouvés")

    # Carte centrée automatiquement
    if not df.empty:
        latc, lonc = df["latitude"].mean(), df["longitude"].mean()
        m = folium.Map(location=[latc, lonc], zoom_start=12)
        mc = MarkerCluster().add_to(m)
        for _, r in df.iterrows():
            folium.Marker(
                [r["latitude"], r["longitude"]],
                popup=(
                    f"{r.get('adresse_nom_voie','?')}<br>"
                    f"DPE: {r.get('classe_consommation_energie','?')} / "
                    f"GES: {r.get('classe_estimation_ges','?')}<br>"
                    f"Surface: {r.get('surface_habitable_logement','?')} m²"
                )
            ).add_to(mc)
        st.subheader("Carte des résultats")
        st_folium(m, width=1000, height=600)

    st.download_button(
        "Exporter CSV",
        df.to_csv(index=False).encode("utf-8"),
        "resultats_dpe.csv",
        "text/csv"
    )
