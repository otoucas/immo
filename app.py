# app.py
st.sidebar.subheader("Filtres actifs")
chips = active_filters_summary(st.session_state.filters)
for chip_key, chip_label in chips:
if st.sidebar.button(f"❌ {chip_label}"):
remove_filter(st.session_state, chip_key)


# --- Main layout ---
st.title("🔎 DPE‑GES Finder (Open Data)")
st.caption(
"Recherchez des logements par villes et surfaces, visualisez les résultats sur carte et tableau."
)


left, right = st.columns([3, 4], gap="large")


if not st.session_state.filters["cities"]:
st.info("Aucun filtre actif. Renseignez au moins une ville puis lancez la recherche.")
st.stop()


# Geocode cities and compute extent
with st.spinner("Géocodage des villes…"):
geo = geocode_cities(st.session_state.filters["cities"]) # List of {city, lat, lon, insee, bbox}


if len(geo) == 0:
st.warning("Aucune ville trouvée. Vérifiez l'orthographe.")
st.stop()


extent = compute_cities_extent(geo)


# Fetch DPE data
with st.spinner("Récupération des DPE depuis l'ADEME…"):
dpe_df = fetch_dpe(
cities=geo,
min_surface=st.session_state.filters["min_surface"],
max_surface=st.session_state.filters["max_surface"],
limit=settings.DEFAULT_RESULT_LIMIT,
)


if dpe_df.empty:
st.warning("Aucun résultat DPE ne correspond à vos critères.")
st.stop()


# Add a stable unique key for map selection
dpe_df["row_id"] = dpe_df.index.astype(str)


# Fetch DVF (optional, matched on full address). This can be slow, so limit addresses
with st.expander("Options d'enrichissement DVF (valeurs foncières)"):
enrich_dvf = st.checkbox("Joindre les infos DVF par adresse", value=True)
dvf_limit = st.slider("Max adresses DVF à interroger", 10, 200, 50, 10)


dvf_data: Dict[str, Any] = {}
if enrich_dvf:
with st.spinner("Interrogation DVF…"):
unique_addresses = (
dpe_df["full_address"].dropna().drop_duplicates().head(dvf_limit).tolist()
)
dvf_data = fetch_dvf_for_addresses(unique_addresses)


# Merge DVF data back (simple indicator and a json blob)
if dvf_data:
dpe_df["dvf_count"] = dpe_df["full_address"].map(lambda a: len(dvf_data.get(a, [])))
dpe_df["dvf"] = dpe_df["full_address"].map(lambda a: dvf_data.get(a, []))
else:
dpe_df["dvf_count"] = 0
dpe_df["dvf"] = [[] for _ in range(len(dpe_df))]


# UI: map + table synchronized
with left:
selected_row_id = st.session_state.get("selected_row_id")
render_map(
df=dpe_df,
extent=extent,
selected_row_id=selected_row_id,
)


with right:
selected_row_id = render_results_table(dpe_df)
if selected_row_id is not None:
st.session_state["selected_row_id"] = selected_row_id


st.success(f"{len(dpe_df)} logements affichés.")
