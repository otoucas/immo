import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
import pandas as pd
from services.search_service import SearchService
from ui.state import AppState


def render_results_table(state: AppState, svc: SearchService):
    st.subheader("📋 Résultats (adresse, DPE, GES, surface)")

    df = state.results
    if df is None:
        st.info("Lancez une recherche depuis la barre latérale.")
        return
    if df.empty:
        st.warning("Aucun résultat pour ces filtres.")
        return

    display = df[["adresse", "code_postal", "commune", "dpe", "ges", "surface"]].copy()
    display.index.name = "index"

    gob = GridOptionsBuilder.from_dataframe(display)
    gob.configure_selection("single")
    gob.configure_pagination(paginationAutoPageSize=True)
    grid_options = gob.build()

    grid_resp = AgGrid(
        display,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        height=300,
        fit_columns_on_grid_load=True,
    )

    sel = grid_resp["selected_rows"]
    if sel:
        # récupérer la ligne sélectionnée dans le df original pour DVF + popup
        sel_row = sel[0]
        idx = display.index.get_loc(sel_row["index"]) if "index" in sel_row else None
        if idx is not None:
            state.selected_row_idx = idx
            row = df.iloc[idx]
            st.success(f"📍 Sélection : {row['adresse']} — DPE {row['dpe']} | GES {row['ges']} | {row['surface']} m²")
            # DVF
            with st.spinner("Récupération des infos DVF..."):
                dvf_df = svc.dvf_for_result_row(row)
            if not dvf_df.empty:
                st.markdown("**Transactions DVF (extrait)**")
                st.dataframe(dvf_df.head(10), use_container_width=True)
            else:
                st.caption("Aucune transaction DVF trouvée sur cette adresse/voie (extrait limité).")
