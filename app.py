import streamlit as st
from ui.state import AppState
from services.search_service import SearchService
from ui.components.sidebar import render_sidebar
from ui.components.map_view import render_map
from ui.components.results_table import render_results_table

# Config page
st.set_page_config(page_title="DPE-GES Finder", page_icon="🏠", layout="wide")

# État applicatif
if "state" not in st.session_state:
    st.session_state["state"] = AppState()
state: AppState = st.session_state["state"]

# Services
svc = SearchService()

# UI
render_sidebar(state, svc)

col_map, col_table = st.columns([3, 2])
with col_map:
    render_map(state, svc)
with col_table:
    render_results_table(state, svc)

# Footer discret
st.caption("Sources: ADEME (DPE), Etalab/DGFiP (DVF), BAN/Adresse.")
