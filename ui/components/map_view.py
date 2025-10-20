import streamlit as st
import pydeck as pdk
import pandas as pd
from services.search_service import SearchService
from ui.state import AppState


def _layer_cities(cities):
    if not cities:
        return None
    df = pd.DataFrame(cities)
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position="[lon, lat]",
        get_radius=200,
        pickable=True,
        opacity=0.7,
        stroked=True,
        filled=True,
        auto_highlight=True,
    )
    return layer


def _layer_results(df):
    if df is None or df.empty:
        return None
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position="[lon, lat]",
        get_radius=100,
        pickable=True,
        opacity=0.9,
        stroked=False,
        filled=True,
        auto_highlight=True,
    )
    return layer


def render_map(state: AppState, svc: SearchService):
    st.subheader("🗺️ Carte des résultats")

    # Centre de carte : barycentre des villes choisies, sinon France
    lat, lon = svc.compute_map_center(state.selected_cities)

    layers = []
    lc = _layer_cities(state.selected_cities)
    if lc:
        layers.append(lc)
    lr = _layer_results(state.results)
    if lr:
        layers.append(lr)

    tooltip = {
        "text": "{adresse}\nDPE: {dpe} | GES: {ges}\nSurface: {surface} m²"
    }
    view = pdk.ViewState(latitude=lat, longitude=lon, zoom=10 if state.selected_cities else 5)
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view, tooltip=tooltip))
