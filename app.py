import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

from utils import geocode_city, parse_leboncoin_html, fetch_ademe_all, distance_km
from filters.storage import save_filter, load_filters, delete_filter

# Configuration de la page
st.set_page_config(page_title="Recherche DPE interactive", layout="wide")
st.title("🏡 Analyse DPE - Vue géographique et filtres dynamiques")

# --- Chargement / sauvegarde des filtres ---
with st.sidebar:
    st.header("🎛️ Filtres")

    saved_filters = load_filters()
    filter_name = st.text_input("Nom du jeu de filtres")

    col1, col2 = st.columns(2)
    if col1.button("💾 Sauver filtres") and filter_name:
        save_filter(filter_name, st.session_state)
        st.success(f"Filtres sauvegardés sous le nom : {filter_name}")

    if col2.button("🗑️ Supprimer") and filter_name:
        delete_filter(filter_name)
        st.success(f"Filtres supprimés : {filter_name}")

    if saved_filters:
        selected_filter = st.selectbox("Charger un jeu de filtres", [""] + list(saved_filters.keys()))
        if selected_filter:
            st.session_state.update(saved_filters[selected_filter])
            st.success(f"Filtres chargés : {selected_filter}")

# --- Source des données ---
source_choice = st.radio("🔍 Source de recherche", ["Page Leboncoin", "Open Data ADEME"], horizontal=True)

# -------------------------------
# SOURCE : Leboncoin ou ADEME
# -------------------------------
if source_choice == "Page Leboncoin":
    url = st.text_input("Collez l'URL de la page Leboncoin :")
    lebon_infos = None
    df = pd.DataFrame()  # par défaut vide

    if st.button("Analyser l'annonce LeBoncoin"):
        if not url:
            st.warning("Collez une URL ou le HTML de l'annonce.")
        else:
            # parse_leboncoin_html doit renvoyer un dict (ex: {'surface':45, 'ville':'Paris', 'code_postal':'75010', 'dpe':'D', 'ges':'C'})
            try:
                lebon_infos = parse_leboncoin_html(url)
            except Exception as e:
                st.error(f"Erreur lors de l'analyse LeBonCoin : {e}")
                lebon_infos = None

            if not lebon_infos:
                st.warning("Aucune information extraite depuis la page. Essayez d'uploader le HTML ou vérifier l'URL.")
            else:
                st.success("Infos extraites :")
                st.json(lebon_infos)

                # --- Option A : afficher les infos extraites en simple tableau
                df = pd.DataFrame([lebon_infos])

                # --- Option B (conseillée) : lancer recherche ADEME automatiquement selon ville/CP/surface
                # Si on a au moins une ville ou code_postal, on peut interroger ADEME
                q = lebon_infos.get("ville") or lebon_infos.get("code_postal") or ""
                if q:
                    st.info("Lancement d'une recherche ADEME basée sur les informations extraites...")
                    # utilise la pagination par défaut (toutes pages) ou adapter en param
                    raw_rows = fetch_ademe_all(q=q, page_mode_all=True, max_pages=None)
                    if raw_rows:
                        df_ademe = pd.DataFrame(raw_rows)
                        # garder uniquement résultats géolocalisés
                        if "latitude" in df_ademe.columns and "longitude" in df_ademe.columns:
                            df_ademe = df_ademe.dropna(subset=["latitude", "longitude"])
                        else:
                            st.warning("Les résultats ADEME n'ont pas de coordonnées.")
                        # appliquer filtres simples extraits depuis la/leboncoin
                        # surface
                        s = lebon_infos.get("surface")
                        if s and "surface_habitable_logement" in df_ademe.columns:
                            df_ademe = df_ademe[(df_ademe["surface_habitable_logement"] >= max(0, s-10)) &
                                                (df_ademe["surface_habitable_logement"] <= s+10)]
                        # dpe/ges
                        dpe = lebon_infos.get("dpe")
                        if dpe and "classe_consommation_energie" in df_ademe.columns:
                            df_ademe = df_ademe[df_ademe["classe_consommation_energie"] == dpe]
                        ges = lebon_infos.get("ges")
                        if ges and "classe_estimation_ges" in df_ademe.columns:
                            df_ademe = df_ademe[df_ademe["classe_estimation_ges"] == ges]

                        if not df_ademe.empty:
                            # normaliser colonnes manquantes (optionnel)
                            # créer colonnes manquantes avec "?" pour le tableau/popup
                            wanted = [
                                "adresse_numero_voie","adresse_nom_voie","code_postal","commune",
                                "classe_consommation_energie","date_consommation_energie",
                                "classe_estimation_ges","date_estimation_ges",
                                "surface_habitable_logement","nombre_batiments","latitude","longitude"
                            ]
                            for c in wanted:
                                if c not in df_ademe.columns:
                                    df_ademe[c] = "?"
                            st.session_state.df_results = df_ademe.reset_index(drop=True)
                            st.success(f"{len(df_ademe)} résultats ADEME récupérés et stockés.")
                            df = st.session_state.df_results  # pour affichage immédiat
                        else:
                            st.warning("Aucun résultat ADEME après application des filtres extraits.")
                    else:
                        st.warning("Aucun résultat récupéré depuis l'API ADEME.")
                # si pas de q, on se contente d'afficher les infos extraites dans df (single-row)
    # fin analyse LBC

else:
    # -------------------------------
    # Recherche via ADEME (manuelle)
    # -------------------------------
    ville = st.text_input("Ville de recherche", st.session_state.get("ville", ""))
    nb_pages = st.number_input("Nombre de pages à récupérer", 1, 50, st.session_state.get("nb_pages", 5))

    # Surface min/max
    col1, col2 = st.columns(2)
    with col1:
        smin = st.number_input("Surface minimale (m²)", min_value=0, value=st.session_state.get("surface_min", 0), step=5)
    with col2:
        smax = st.number_input("Surface maximale (m²)", min_value=0, value=st.session_state.get("surface_max", 200), step=5)

    # Rayon
    rayon = st.number_input("Rayon (km)", min_value=0, value=st.session_state.get("rayon_km", 10), step=1)

    if st.button("🔎 Lancer la recherche ADEME"):
        if not (ville or st.session_state.get("code_postal")):
            st.warning("Saisissez une ville ou un code postal pour lancer la recherche.")
            df = pd.DataFrame()
        else:
            q = ville or st.session_state.get("code_postal", "")
            raw_rows = fetch_ademe_all(q=q, page_mode_all=(pagination_mode=="Toutes les pages"), max_pages=max_pages)
            if not raw_rows:
                st.warning("Aucun résultat ADEME trouvé pour cette requête.")
                df = pd.DataFrame()
            else:
                df = pd.DataFrame(raw_rows)
                if "latitude" in df.columns and "longitude" in df.columns:
                    df = df.dropna(subset=["latitude","longitude"])
                # application des filtres manuels
                if "surface_habitable_logement" in df.columns:
                    df = df[(df["surface_habitable_logement"] >= smin) & (df["surface_habitable_logement"] <= smax)]
                # filtrage par rayon (si coords dispo)
                if 'latitude' in df.columns and 'longitude' in df.columns and (st.session_state.get("clicked_lat") or ville):
                    # si ville -> géocode, sinon utilise clicked coords
                    if ville:
                        coords = geocode_city(ville)
                        if coords:
                            latc, lonc = coords
                        else:
                            latc, lonc = None, None
                    else:
                        latc, lonc = st.session_state.get("clicked_lat"), st.session_state.get("clicked_lon")
                    if latc and lonc and rayon > 0:
                        df["distance"] = df.apply(lambda r: distance_km(latc, lonc, r["latitude"], r["longitude"]), axis=1)
                        df = df[df["distance"] <= rayon]
                st.session_state.df_results = df.reset_index(drop=True)
    else:
        df = pd.DataFrame()

# --- Carte interactive ---
if not df.empty:
    st.subheader("🗺️ Carte des résultats")

    center_lat = df["latitude"].mean()
    center_lon = df["longitude"].mean()
    m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles="OpenStreetMap")

    # Couches supplémentaires
    folium.TileLayer("CartoDB positron", name="Clair").add_to(m)
    folium.TileLayer("CartoDB dark_matter", name="Sombre").add_to(m)
    folium.TileLayer(
        tiles="https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google Satellite",
        name="Satellite",
        max_zoom=20,
        subdomains=["mt0", "mt1", "mt2", "mt3"]
    ).add_to(m)

    marker_cluster = MarkerCluster().add_to(m)

    for _, r in df.iterrows():
        popup_html = f"""
        <b>{r.get('adresse_nom_voie', 'Adresse inconnue')}</b><br>
        Commune : {r.get('commune', '?')} ({r.get('code_postal', '')})<br>
        Surface : {r.get('surface_habitable_logement', '?')} m²<br>
        Bâtiments : {r.get('nombre_batiments', '?')}<br>
        DPE : {r.get('classe_consommation_energie', '?')}<br>
        GES : {r.get('classe_estimation_ges', '?')}<br>
        Date DPE : {r.get('date_etablissement_dpe', '?')}
        """
        folium.Marker(
            location=[r.get("latitude", 0), r.get("longitude", 0)],
            popup=folium.Popup(popup_html, max_width=250)
        ).add_to(marker_cluster)

    folium.LayerControl().add_to(m)
    map_state = st_folium(m, width=1200, height=600)

    # --- Tableau des résultats ---
    st.subheader("📋 Résultats détaillés")

    display_cols = [
        "adresse_nom_voie",
        "code_postal",
        "commune",
        "classe_consommation_energie",
        "classe_estimation_ges",
        "surface_habitable_logement",
        "nombre_batiments",
        "date_etablissement_dpe",
        "latitude",
        "longitude"
    ]
    display_cols = [c for c in display_cols if c in df.columns]
    display_df = df[display_cols].copy()

    st.dataframe(display_df, use_container_width=True)

else:
    st.info("Aucun résultat à afficher. Lancez une recherche pour voir les données.")
