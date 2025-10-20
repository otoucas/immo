import streamlit as st
from services.search_service import SearchService
from ui.state import AppState

DPE_GRADES = list("ABCDEFG")
GES_GRADES = list("ABCDEFG")


def render_sidebar(state: AppState, svc: SearchService):
    st.sidebar.header("🔎 Recherche")

    # Ajout d'une ville / code postal
    st.sidebar.subheader("Zones géographiques")
    with st.sidebar.form("city_form", clear_on_submit=True):
        q = st.text_input("Ville", placeholder="Ex: Lyon, Paris, ...")
        submitted = st.form_submit_button("Ajouter la ville")
        if submitted and q:
            matches = svc.geocode_city(q or None)
            if matches:
                chosen = matches[0]  # premier résultat
                # éviter doublons (par citycode)
                if not any(c.get("citycode") == chosen.get("citycode") for c in state.selected_cities):
                    state.selected_cities.append(chosen)
            else:
                st.sidebar.warning("Aucune ville trouvée.")

    # Liste des villes sélectionnées (avec suppression)
    if state.selected_cities:
        for i, city in enumerate(state.selected_cities):
            cols = st.sidebar.columns([3,2,1])
            cols[0].markdown(f"**{city['city']}**")
            cols[1].markdown(f"`{city.get('postcode','')}`")
            if cols[2].button("✕", key=f"del_city_{i}"):
                state.selected_cities.pop(i)
                st.rerun()

    # Filtres surface
    st.sidebar.subheader("Surface habitable (m²)")

    col_min, col_max = st.sidebar.columns(2)
    with col_min:
        smin = st.number_input(
            "Min",
            min_value=0,
            max_value=10000,
            value=state.surface_min,
            step=5,
            key="surface_min_input"
        )
    with col_max:
        smax = st.number_input(
            "Max",
            min_value=0,
            max_value=10000,
            value=state.surface_max,
            step=5,
            key="surface_max_input"
        )

    # synchroniser avec l'état global
    state.surface_min = smin
    state.surface_max = smax


    # Filtres DPE & GES
    st.sidebar.subheader("Filtres DPE")
    selected_dpe = []
    for g in DPE_GRADES:
        if st.sidebar.checkbox(f"{g}", key=f"dpe_{g}"):
            selected_dpe.append(g)
    state.dpe_filters = selected_dpe

    st.sidebar.subheader("Filtres GES")
    selected_ges = []
    for g in GES_GRADES:
        if st.sidebar.checkbox(f"GES {g}", key=f"ges_{g}"):
            selected_ges.append(g)
    state.ges_filters = selected_ges

    st.sidebar.divider()
    
    # Bouton de lancement explicite
    if st.sidebar.button("🚀 Lancer la recherche", use_container_width=True):
        state.results = svc.search_ademe(
            state.selected_cities,
            state.dpe_filters,
            state.ges_filters,
            state.surface_min,
            state.surface_max,
        )
