# ui/map_view.py
from __future__ import annotations
import pydeck as pdk
import pandas as pd
import streamlit as st
from typing import Dict, Optional




PRIMARY_COLOR = [33, 150, 243]
GREY = [170, 170, 170]
HIGHLIGHT = [220, 20, 60]




def render_map(df: pd.DataFrame, extent: Dict[str, float], selected_row_id: Optional[str] = None) -> None:
if df.empty:
st.info("Aucune donnée à afficher sur la carte.")
return


view_state = pdk.ViewState(
latitude=extent.get("center_lat", 46.6),
longitude=extent.get("center_lon", 2.6),
zoom=extent.get("zoom_like", 6.0),
pitch=0,
bearing=0,
)


# Compute colors
def compute_color(row):
if selected_row_id is not None and str(row.get("row_id")) == str(selected_row_id):
return HIGHLIGHT
return PRIMARY_COLOR


df = df.copy()
df["color"] = df.apply(compute_color, axis=1)


tooltip = {
"html": "<b>{full_address}</b><br/>DPE: {dpe} | GES: {ges}<br/>Surface: {surface} m²\n",
"style": {"backgroundColor": "#f9f9f9", "color": "#111"},
}


layer = pdk.Layer(
"ScatterplotLayer",
data=df,
get_position="[lon, lat]",
get_radius=20,
pickable=True,
get_fill_color="color",
)


r = pdk.Deck(
layers=[layer],
initial_view_state=view_state,
tooltip=tooltip,
)


st.pydeck_chart(r, use_container_width=True)


# If a row is selected, show a persistent info box below map (acts as popup)
if selected_row_id is not None:
sel = df[df["row_id"].astype(str) == str(selected_row_id)].head(1)
if not sel.empty:
row = sel.iloc[0]
with st.container(border=True):
st.subheader("📍 Sélection sur la carte")
st.markdown(f"**{row['full_address']}**")
st.write(f"DPE: {row['dpe']} | GES: {row['ges']} | Surface: {row['surface']} m²")
# DVF details if present
dvf_list = row.get("dvf", [])
if dvf_list:
st.caption(f"Transactions DVF associées: {len(dvf_list)}")
st.dataframe(dvf_list)
else:
st.caption("Aucune transaction DVF associée trouvée pour cette adresse (ou non interrogée).")
