# ui/results_table.py
from __future__ import annotations
from typing import Optional
import pandas as pd
import streamlit as st


try:
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
HAS_AGGRID = True
except Exception:
HAS_AGGRID = False




DISPLAY_COLUMNS = {
"full_address": "Adresse",
"dpe": "DPE",
"ges": "GES",
"surface": "Surface (m²)",
"date_dpe": "Date DPE",
}




def render_results_table(df: pd.DataFrame) -> Optional[str]:
st.subheader("Résultats")


if df.empty:
st.info("Aucun résultat à afficher.")
return None


table_df = df[list(DISPLAY_COLUMNS.keys())].rename(columns=DISPLAY_COLUMNS)


if HAS_AGGRID:
gob = GridOptionsBuilder.from_dataframe(table_df)
gob.configure_selection("single")
gob.configure_grid_options(domLayout="autoHeight")
grid = AgGrid(
table_df,
gridOptions=gob.build(),
update_mode=GridUpdateMode.SELECTION_CHANGED,
height=400,
theme="balham",
)
sel = grid.selected_rows
if sel:
# Find the corresponding row_id based on Adresse value
adr = sel[0].get("Adresse")
match = df[df["full_address"] == adr].head(1)
if not match.empty:
return str(match.iloc[0]["row_id"])
return None
else:
# Fallback to simple dataframe with a selectbox for selection
st.dataframe(table_df, use_container_width=True)
options = [f"{i} — {row['full_address']}" for i, row in df.iterrows()]
choice = st.selectbox("Sélectionner une ligne pour afficher le popup sur la carte", ["(aucune)"] + options)
if choice != "(aucune)":
idx = int(choice.split(" — ")[0])
return str(df.iloc[idx]["row_id"]) # type: ignore
return None
