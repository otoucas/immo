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
        col1, col2 = st.columns([2,1])
        with col1:
            q = st.text_input("Ville", placeholder="Ex: Lyon, Paris, ...")
        with col2:
            pc = st.text_input("CP", placeholder="69001")
        submitted = st.form_submit_button("Ajouter la ville")
        if submitted and q:
            matches = svc.geocode_city(q, postcode=pc or None)
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

    # Codes postaux additionnels
    st.sidebar.text_input("Codes postaux (séparés par des virgules)", key="_tmp_pcs", placeholder="69001,69002")
    with st.sidebar.form("pc_form", clear_on_submit=True):
        raw = st.text_input("Codes postaux (séparés par des virgules)", key="_tmp_pcs", placeholder="69001,69002")
        submitted_pc = st.form_submit_button("Ajouter codes postaux")
        if submitted_pc:
            pcs = [p.strip() for p in raw.split(",") if p.strip()]
            for p in pcs:
                if p not in state.extra_postcodes:
                    state.extra_postcodes.append(p)
            st.rerun()


    if state.extra_postcodes:
        st.sidebar.caption("Codes postaux ajoutés :")
        for i, p in enumerate(state.extra_postcodes):
            cols = st.sidebar.columns([4,1])
            cols[0].markdown(f"`{p}`")
            if cols[1].button("✕", key=f"del_pc_{i}"):
                state.extra_postcodes.pop(i)
                st.rerun()

    st.sidebar.divider()

    # Filtres surface
    st.sidebar.subheader("Surface habitable (m²)")
    smin, smax = st.sidebar.slider("Plage", min_value=0, max_value=1000, value=(state.surface_min, state.surface_max), step=5)
    state.surface_min, state.surface_max = smin, smax

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
            state.extra_postcodes,
            state.dpe_filters,
            state.ges_filters,
            state.surface_min,
            state.surface_max,
        )
