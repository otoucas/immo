import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from utils import (
    parse_leboncoin_html,
    fetch_ademe_all,
    geocode_city,
    distance_km,
    load_filters,
    save_filters,
)

# ------------------------------------------------------------
# Configuration de l'application
# ------------------------------------------------------------
st.set_page_config(page_title="Immo Data Explorer", layout="wide")

st.title("🏠 Immo Data Explorer")
st.write("Analyse et visualisation de données immobilières (Leboncoin / ADEME).")

# ------------------------------------------------------------
# Barre latérale : paramètres et filtres
# ------------------------------------------------------------
st.sidebar.header("⚙️ Paramètres de recherche")

# Charger les filtres précédemment enregistrés
filters = load_filters()

source_choice = st.sidebar.radio("Source de données :", ["Page Leboncoin", "Open Data ADEME"], index=0)

# Paramètres communs
ville = st.sidebar.text_input("Ville", filters.get("ville", ""))
surface_min = st.sidebar.number_input("Surface min (m²)", 0, 500, filters.get("surface_min", 0), step=5)
surface_max = st.sidebar.number_input("Surface max (m²)", 0, 500, filters.get("surface_max", 200), step=5)
rayon_km = st.sidebar.number_input("Rayon de recherche (km)", 0, 100, filters.get("rayon_km", 10), step=1)
nb_pages = st.sidebar.number_input("Nombre de pages ADEME à récupérer", 1, 50, filters.get("nb_pages", 5), step=1)

# Boutons de gestion des filtres
colf1, colf2 = st.sidebar.columns(2)
if colf1.button("💾 Sauvegarder filtres"):
    save_filters({
        "ville": ville,
        "surface_min": surface_min,
        "surface_max": surface_max,
        "rayon_km": rayon_km,
        "nb_pages": nb_pages,
    })
    st.sidebar.success("Filtres enregistrés ✅")

if colf2.button("♻️ Recharger filtres"):
    filters = load_filters()
    st.sidebar.experimental_rerun()

st.sidebar.markdown("---")

# ------------------------------------------------------------
# Logique principale selon la source choisie
# ------------------------------------------------------------
df = pd.DataFrame()

if source_choice == "Page Leboncoin":
    url = st.text_input("Collez l'URL de la page Leboncoin :")
    if st.button("Analyser la page"):
        if not url:
            st.warning("Veuillez saisir une URL.")
        else:
            try:
                lebon_infos = parse_leboncoin_html(url)
            except Exception as e:
                st.error(f"Erreur lors de l'analyse : {e}")
                lebon_infos = None

            if not isinstance(lebon_infos, dict) or not lebon_infos:
                st.warning("Aucune donnée exploitable extraite.")
            else:
                st.success("✅ Données extraites :")
                st.json(lebon_infos)
                df = pd.DataFrame([lebon_infos])

                # Recherche complémentaire ADEME
                q = lebon_infos.get("ville") or lebon_infos.get("code_postal")
                if q:
                    try:
                        st.info("Recherche complémentaire ADEME…")
                        df_ademe = fetch_ademe_all(q=q)
                        if df_ademe is not None and not df_ademe.empty:
                            df = df_ademe
                            st.success(f"{len(df_ademe)} résultats trouvés via ADEME.")
                        else:
                            st.warning("Aucun résultat ADEME trouvé.")
                    except Exception as e:
                        st.error(f"Erreur ADEME : {e}")

else:
    if st.sidebar.button("🔎 Lancer la recherche ADEME"):
        if not ville:
            st.warning("Veuillez indiquer une ville.")
        else:
            try:
                coords = geocode_city(ville)
                if not coords:
                    st.error("Ville non trouvée.")
                else:
                    lat, lon = coords
                    df = fetch_ademe_all(ville, pages=nb_pages)
                    if df is not None and not df.empty:
                        if "surface_habitable_logement" in df.columns:
                            df = df[
                                (df["surface_habitable_logement"] >= surface_min)
                                & (df["surface_habitable_logement"] <= surface_max)
                            ]
                        if "latitude" in df.columns and "longitude" in df.columns:
                            df["distance"] = df.apply(
                                lambda r: distance_km(lat, lon, r["latitude"], r["longitude"]),
                                axis=1,
                            )
                            df = df[df["distance"] <= rayon_km]
                        st.success(f"{len(df)} résultats affichés.")
                    else:
                        st.warning("Aucun résultat trouvé.")
            except Exception as e:
                st.error(f"Erreur : {e}")

# ------------------------------------------------------------
# Affichage carte et table
# ------------------------------------------------------------
if not df.empty:
    display_cols = [c for c in df.columns if c.lower() not in ["id", "source"]]
    display_df = df[display_cols].copy()
    st.dataframe(display_df)

    if {"latitude", "longitude"}.issubset(df.columns):
        m = folium.Map(location=[df["latitude"].mean(), df["longitude"].mean()], zoom_start=10)
        folium.TileLayer("Stamen Terrain", attr="Stamen Terrain").add_to(m)
        for _, row in df.iterrows():
            folium.Marker(
                [row["latitude"], row["longitude"]],
                popup=f"{row.get('ville', '')} - {row.get('surface_habitable_logement', '?')} m²",
            ).add_to(m)
        st_folium(m, height=500)
else:
    st.info("Aucun résultat à afficher.")
