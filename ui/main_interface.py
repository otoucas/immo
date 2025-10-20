# ui/main_interface.py
import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster

import pandas as pd
from core.data_ademe import fetch_ademe_all
from core.geodata import geocode_city, compute_barycenter, filter_ademe_data_by_radius
from core.postal_layers import add_postalcode_layer, add_cadastre_layer
from utils.storage import save_filter, load_filters, delete_saved_filter


def render_main_interface():
    st.title("🗺️ Carte DPE / DVF interactive")
    st.markdown("### 🔎 Paramètres et filtres")

    # --- Initialisation ---
    if "villes" not in st.session_state:
        st.session_state["villes"] = []
    if "codes_postaux" not in st.session_state:
        st.session_state["codes_postaux"] = []

    # === ZONE FILTRES ===
    st.subheader("Filtres principaux")

    col1, col2, col3 = st.columns([1.5, 1, 1])
    with col1:
        # --- Villes dynamiques ---
        st.markdown("**Ajouter une ville**")
        with st.form("form_ville"):
            new_ville = st.text_input("Nom de la ville")
            submit_ville = st.form_submit_button("Ajouter")
        if submit_ville and new_ville:
            g = geocode_city(new_ville)
            if g:
                ville_label = f"{new_ville.title()} ({g.get('code_postal', '?')})"
                if ville_label not in st.session_state["villes"]:
                    st.session_state["villes"].append(ville_label)
                    st.success(f"{ville_label} ajoutée ✅")
            else:
                st.warning("Ville introuvable.")
        if st.session_state["villes"]:
            to_delete = st.selectbox("🗑️ Supprimer une ville :", ["Aucune"] + st.session_state["villes"])
            if to_delete != "Aucune":
                st.session_state["villes"].remove(to_delete)
                st.rerun()

    with col2:
        # --- Rayon ---
        rayon = st.number_input("Rayon (km)", min_value=0.0, step=0.5)
        if st.button("Valider le rayon"):
            if st.session_state["villes"]:
                bary = compute_barycenter(st.session_state["villes"])
                if bary:
                    df_temp = fetch_ademe_all(st.session_state["villes"])
                    df_temp = filter_ademe_data_by_radius(df_temp, bary[0], bary[1], rayon)
                    codes_in_radius = df_temp["code_postal"].dropna().unique().tolist()
                    st.session_state["codes_postaux"] = codes_in_radius
                    st.success(f"{len(codes_in_radius)} codes postaux inclus dans le rayon.")
            else:
                st.warning("Ajoutez d'abord une ville.")

    with col3:
        # --- Surface habitable ---
        st.markdown("**Surface habitable (m²)**")
        surface_min = st.number_input("Min", min_value=0, value=0)
        surface_max = st.number_input("Max", min_value=0, value=500)

    # --- Filtres DPE / GES ---
    st.subheader("Filtres DPE et GES")
    col_dpe, col_ges = st.columns(2)
    with col_dpe:
        dpe_selected = st.multiselect(
            "Classe DPE",
            ["A", "B", "C", "D", "E", "F", "G"],
            default=[]
        )
    with col_ges:
        ges_selected = st.multiselect(
            "Classe GES",
            ["A", "B", "C", "D", "E", "F", "G"],
            default=[]
        )

    # === OPTIONS D’AFFICHAGE ===
    st.subheader("Options d'affichage sur la carte")
    col_opt1, col_opt2, col_opt3 = st.columns([1, 1, 1])
    with col_opt1:
        show_postal = st.checkbox("Contours codes postaux")
    with col_opt2:
        show_cadastre = st.checkbox("Parcelles cadastrales")
    with col_opt3:
        carte_type = st.radio("Type de carte", ["Classique", "Satellite"], horizontal=True)

    # === FILTRES ACTIFS ===
    st.markdown("### 🎛️ Filtres actifs")
    active_filters = []
    if st.session_state["villes"]:
        active_filters.append("Villes : " + ", ".join(st.session_state["villes"]))
    if rayon:
        active_filters.append(f"Rayon : {rayon} km")
    if dpe_selected:
        active_filters.append("DPE : " + ", ".join(dpe_selected))
    if ges_selected:
        active_filters.append("GES : " + ", ".join(ges_selected))
    if surface_min or surface_max:
        active_filters.append(f"Surface : {surface_min or 0} – {surface_max or '∞'} m²")
    if st.session_state["codes_postaux"]:
        active_filters.append("Codes postaux : " + ", ".join(st.session_state["codes_postaux"]))

    st.info(" | ".join(active_filters) if active_filters else "Aucun filtre appliqué.")

    # === CARTE ===
    st.markdown("### 🗺️ Carte interactive")

    m = folium.Map(location=[46.6, 2.4], zoom_start=6)
    if st.session_state["villes"]:
        bary = compute_barycenter(st.session_state["villes"])
        if bary:
            m.location = bary
            m.zoom_start = 11

    if carte_type == "Satellite":
        folium.TileLayer("Esri.WorldImagery", name="Satellite").add_to(m)
    else:
        folium.TileLayer("OpenStreetMap", name="Classique").add_to(m)

    # Ajout des calques
    if show_postal and st.session_state["codes_postaux"]:
        add_postalcode_layer(m, st.session_state["codes_postaux"])
    if show_cadastre:
        add_cadastre_layer(m)

    # --- Données DPE filtrées ---
    df = fetch_ademe_all(st.session_state["villes"])
    if not df.empty:
        if dpe_selected:
            df = df[df["classe_consommation_energie"].isin(dpe_selected)]
        if ges_selected:
            df = df[df["classe_estimation_ges"].isin(ges_selected)]
        if surface_min:
            df = df[df["surface_habitable_logement"] >= surface_min]
        if surface_max:
            df = df[df["surface_habitable_logement"] <= surface_max]
        if rayon and st.session_state["villes"]:
            bary = compute_barycenter(st.session_state["villes"])
            if bary:
                df = filter_ademe_data_by_radius(df, bary[0], bary[1], rayon)

        # --- Points sur la carte ---
        cluster = MarkerCluster().add_to(m)
        for _, r in df.iterrows():
            folium.Marker(
                location=[r["latitude"], r["longitude"]],
                popup=(
                    f"<b>{r.get('adresse_nom_voie','?')}</b><br>"
                    f"DPE : {r.get('classe_consommation_energie','?')}<br>"
                    f"GES : {r.get('classe_estimation_ges','?')}<br>"
                    f"Surface : {r.get('surface_habitable_logement','?')} m²<br>"
                    f"Nbre bâtiments : {r.get('nombre_batiments','?')}<br>"
                    f"Date DPE : {r.get('date_etablissement_dpe','?')}"
                ),
            ).add_to(cluster)

    st_folium(m, height=600)

    # === TABLEAU DE RÉSULTATS ===
    st.markdown("### 📋 Résultats")
    display_cols = [
        "adresse_nom_voie",
        "surface_habitable_logement",
        "nombre_batiments",
        "classe_consommation_energie",
        "classe_estimation_ges",
        "date_etablissement_dpe",
    ]
    if df.empty:
        st.dataframe(pd.DataFrame(columns=display_cols))
    else:
        display_df = df[display_cols].copy()
        st.dataframe(display_df)

        csv = display_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📤 Exporter les résultats en CSV",
            csv,
            "resultats_dpe.csv",
            "text/csv",
            key="download-csv"
        )
