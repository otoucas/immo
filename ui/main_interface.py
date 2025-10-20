# ui/main_interface.py
import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
import pandas as pd

from core.geodata import (
    geocode_city,
    get_postal_codes_from_radius,
)
from core.postal_layers import draw_postalcode_boundaries, draw_cadastre_layer
from core.data_ademe import fetch_ademe_all


def render_main_interface():
    st.title("🏡 Carte interactive DPE / DVF")

    # ------------------------------
    # SIDEBAR — filtres principaux
    # ------------------------------
    with st.sidebar:
        st.header("🎛️ Filtres de recherche")

        # --- Cases à cocher DPE et GES
        st.markdown("####")
        dpe_classes = ["A", "B", "C", "D", "E", "F", "G"]
        dpe_sel = [c for c in dpe_classes if st.checkbox(f"DPE {c}", key=f"dpe_{c}")]

        st.markdown("####")
        ges_classes = ["A", "B", "C", "D", "E", "F", "G"]
        ges_sel = [c for c in ges_classes if st.checkbox(f"GES {c}", key=f"ges_{c}")]

        # --- Surface habitable
        st.markdown("#### Surface habitable")
        smin = st.number_input("Surface min (m²)", min_value=0, value=0, step=5)
        smax = st.number_input("Surface max (m²)", min_value=0, value=500, step=5)

        # --- Choix des villes
        st.markdown("### 🏙️ Villes sélectionnées")
        if "villes" not in st.session_state:
            st.session_state["villes"] = []

        with st.form("form_ville"):
            nv = st.text_input("Ajouter une ville")
            submit_v = st.form_submit_button("Ajouter")

        if submit_v and nv:
            g = geocode_city(nv)
            if g:
                label = f"{nv.title()} ({g.get('code_postal', '?')})"
                if label not in st.session_state["villes"]:
                    st.session_state["villes"].append(label)
                    st.session_state["repere_coords"] = (g["lat"], g["lon"])
                    st.success(f"{label} ajoutée ✅")
            else:
                st.warning("Ville introuvable.")

        # Affiche les villes actuellement en mémoire
        if st.session_state["villes"]:
            for v in st.session_state["villes"]:
                st.write(f"- {v}")
            if st.button("🗑️ Effacer toutes les villes"):
                st.session_state["villes"] = []
                st.session_state.pop("repere_coords", None)
                st.session_state.pop("codes_postaux", None)

        # --- Rayon
        st.markdown("#### Rayon (km)")
        radius = st.number_input("Taille du rayon (km)", min_value=0, step=1)
        if st.button("✅ Valider le rayon"):
            coords = st.session_state.get("repere_coords")
            if coords:
                codes = get_postal_codes_from_radius(coords[0], coords[1], radius)
                st.session_state["codes_postaux"] = codes
                st.success(f"{len(codes)} codes postaux trouvés dans le rayon")

        # --- Bouton de recherche
        st.markdown("---")
        lancer_recherche = st.button("🔍 Lancer la recherche")

        # --- Gestion du cache
        st.markdown("### 🧠 Cache")
        if st.button("Effacer le cache"):
            st.cache_data.clear()
            st.success("Cache vidé ✅")

    # ------------------------------
    # CORPS — carte et résultats
    # ------------------------------
    st.subheader("🗺️ Carte des résultats")

    carte_type = st.radio("Type de carte", ["Classique", "Satellite"], horizontal=True)
    afficher_contours = st.checkbox("Afficher contours codes postaux", value=False)
    afficher_parcelles = st.checkbox("Afficher parcelles cadastrales", value=False)

    # Centrage
    villes = st.session_state.get("villes", [])
    lat_c, lon_c = (46.8, 2.4)
    if "repere_coords" in st.session_state:
        lat_c, lon_c = st.session_state["repere_coords"]

    tiles = "OpenStreetMap" if carte_type == "Classique" else "Esri.WorldImagery"
    m = folium.Map(location=[lat_c, lon_c], zoom_start=11, tiles=tiles)

    # ------------------------------
    # CHARGEMENT DES DONNÉES
    # ------------------------------
    df = pd.DataFrame()
    codes = st.session_state.get("codes_postaux", [])

    if codes:
        df = fetch_ademe_all(codes)

    # ------------------------------
    # COMPTEUR “LIVE”
    # ------------------------------
    compteur = 0
if not df.empty:
    df_filtered = df.copy()

    # --- Harmonisation des noms de colonnes
    rename_map = {
        "surface_habitable": "surface_habitable_logement",
        "surface_habitable_l": "surface_habitable_logement",
        "surface_logement": "surface_habitable_logement",
    }
    df_filtered.rename(columns=rename_map, inplace=True)

    # --- Application des filtres
    if "classe_consommation_energie" in df_filtered.columns and dpe_sel:
        df_filtered = df_filtered[df_filtered["classe_consommation_energie"].isin(dpe_sel)]

    if "classe_estimation_ges" in df_filtered.columns and ges_sel:
        df_filtered = df_filtered[df_filtered["classe_estimation_ges"].isin(ges_sel)]

    if "surface_habitable_logement" in df_filtered.columns:
        df_filtered = df_filtered[
            (df_filtered["surface_habitable_logement"] >= smin)
            & (df_filtered["surface_habitable_logement"] <= smax)
        ]
    else:
        st.warning("⚠️ Données ADEME sans surface habitable — filtrage désactivé.")

    compteur = len(df_filtered)
else:
    df_filtered = pd.DataFrame()
    compteur = 0


    st.sidebar.markdown(f"### 📊 Logements correspondant aux filtres : **{compteur}**")

    # ------------------------------
    # AFFICHAGE APRÈS RECHERCHE
    # ------------------------------
    if lancer_recherche and compteur > 0:
        cluster = MarkerCluster().add_to(m)
        for _, r in df_filtered.iterrows():
            popup = (
                f"<b>{r.get('adresse_nom_voie', '?')}</b><br>"
                f"DPE: {r.get('classe_consommation_energie', '?')} / "
                f"GES: {r.get('classe_estimation_ges', '?')}<br>"
                f"Surface: {r.get('surface_habitable_logement', '?')} m²<br>"
                f"Date: {r.get('date_etablissement_dpe', '?')}"
            )
            folium.Marker(
                location=[r["latitude"], r["longitude"]],
                popup=popup,
                icon=folium.Icon(color="green", icon="home"),
            ).add_to(cluster)

        # Calques optionnels
        if afficher_contours:
            draw_postalcode_boundaries(m, st.session_state.get("codes_postaux", []))
        if afficher_parcelles and "repere_coords" in st.session_state:
            lat, lon = st.session_state["repere_coords"]
            draw_cadastre_layer(m, lat, lon)

        st_folium(m, width=1200, height=600)

        # ------------------------------
        # TABLEAU DES RÉSULTATS
        # ------------------------------
        st.subheader(f"📋 {compteur} résultats trouvés")
        display_cols = [
            "adresse_nom_voie",
            "surface_habitable_logement",
            "nombre_batiments",
            "classe_consommation_energie",
            "classe_estimation_ges",
            "date_etablissement_dpe",
        ]
        st.dataframe(df_filtered[display_cols])

        # --- Export CSV
        csv = df_filtered.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Exporter les résultats en CSV",
            data=csv,
            file_name="resultats_dpe.csv",
            mime="text/csv",
        )

    else:
        st_folium(m, width=1200, height=600)
        if not codes:
            st.info("🗺️ Définissez une ou plusieurs villes puis validez un rayon pour lancer la recherche.")
        elif compteur == 0:
            st.warning("Aucun résultat pour ces filtres.")
