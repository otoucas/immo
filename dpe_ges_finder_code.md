# Project structure

```
.
├── app.py
├── config.py
├── services
│   ├── __init__.py
│   ├── geocoding.py
│   ├── dpe_service.py
│   └── dvf_service.py
├── ui
│   ├── __init__.py
│   ├── map_view.py
│   └── results_table.py
└── utils
    ├── __init__.py
    └── filters.py
```

---

## app.py
```python
# app.py
# Streamlit app entrypoint

import json
import math
from typing import List, Dict, Any

import pandas as pd
import streamlit as st

from config import settings
from services.geocoding import geocode_cities, compute_cities_extent
from services.dpe_service import fetch_dpe
from services.dvf_service import fetch_dvf_for_addresses
from ui.map_view import render_map
from ui.results_table import render_results_table
from utils.filters import active_filters_summary, clear_all_filters, remove_filter

st.set_page_config(page_title="DPE‑GES Finder", layout="wide")

# --- Sidebar (filters) ---
st.sidebar.title("Filtres")

# City input (allow multiple)
with st.sidebar:
    st.subheader("Villes d'intérêt")
    cities_input = st.text_input(
        "Renseigner une ou plusieurs villes (séparées par des virgules)",
        value="",
        placeholder="Ex: Lyon, Villeurbanne, Caluire-et-Cuire",
    )

    st.subheader("Surface habitable (m²)")
    col_a, col_b = st.columns(2)
    with col_a:
        min_surf = st.number_input("Min", min_value=0, value=0, step=1)
    with col_b:
        max_surf = st.number_input("Max", min_value=0, value=0, step=1)

    # Buttons to manage filters
    apply_btn = st.button("Lancer la recherche", type="primary")
    reset_btn = st.button("Réinitialiser tous les filtres")

# Manage state for filters
if "filters" not in st.session_state:
    st.session_state.filters = {
        "cities": [],
        "min_surface": None,
        "max_surface": None,
    }

if reset_btn:
    clear_all_filters(st.session_state)

# Parse cities
parsed_cities = [c.strip() for c in cities_input.split(",") if c.strip()]

# Apply filters to state when user clicks search
if apply_btn:
    st.session_state.filters["cities"] = parsed_cities
    st.session_state.filters["min_surface"] = int(min_surf) if min_surf > 0 else None
    st.session_state.filters["max_surface"] = int(max_surf) if max_surf > 0 else None

# Show active filters as removable chips (buttons)
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
    geo = geocode_cities(st.session_state.filters["cities"])  # List of {city, lat, lon, insee, bbox}

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
```

---

## config.py
```python
# config.py
from dataclasses import dataclass

@dataclass
class Settings:
    # ADEME Data Fair dataset slug for DPE logements (change if needed)
    DPE_DATASET_SLUG: str = "dpe-logements"  # e.g., 'dpe-logements' (ADEME Data Fair)

    # Base endpoints
    ADEME_BASE_URL: str = "https://data.ademe.fr/data-fair/api/v1/datasets"
    BAN_SEARCH_URL: str = "https://api-adresse.data.gouv.fr/search/"

    # DVF API (simple, no key). You may replace by a more robust endpoint if available.
    DVF_BASE_URL: str = "https://api.etalab.gouv.fr/api/valeursfoncieres"

    DEFAULT_RESULT_LIMIT: int = 500

settings = Settings()
```

---

## services/__init__.py
```python
# services/__init__.py
```

---

## services/geocoding.py
```python
# services/geocoding.py
from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple
import requests

from config import settings


def geocode_city(name: str) -> Optional[Dict[str, Any]]:
    """Geocode a French municipality using BAN (api-adresse).
    Returns dict with city, lat, lon, insee, bbox
    """
    params = {
        "q": name,
        "type": "municipality",
        "limit": 1,
    }
    r = requests.get(settings.BAN_SEARCH_URL, params=params, timeout=20)
    r.raise_for_status()
    js = r.json()
    feats = js.get("features", [])
    if not feats:
        return None
    f = feats[0]
    props = f.get("properties", {})
    lon, lat = f.get("geometry", {}).get("coordinates", [None, None])
    bbox = f.get("bbox")  # [minx, miny, maxx, maxy]
    return {
        "city": props.get("label") or name,
        "lat": lat,
        "lon": lon,
        "insee": props.get("citycode"),
        "bbox": bbox,
    }


def geocode_cities(cities: List[str]) -> List[Dict[str, Any]]:
    out = []
    for c in cities:
        try:
            g = geocode_city(c)
            if g:
                out.append(g)
        except Exception:
            # Ignore failing city, continue
            continue
    return out


def compute_cities_extent(geo: List[Dict[str, Any]]) -> Dict[str, float]:
    """Compute an extent that covers all cities.
    Returns dict with center_lat, center_lon, zoom_like, bbox
    """
    lats = [g["lat"] for g in geo if g.get("lat") is not None]
    lons = [g["lon"] for g in geo if g.get("lon") is not None]
    if not lats or not lons:
        return {"center_lat": 46.6, "center_lon": 2.6, "zoom_like": 5.0, "bbox": None}

    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)

    # bbox union
    minx = min((g["bbox"][0] for g in geo if g.get("bbox")), default=None)
    miny = min((g["bbox"][1] for g in geo if g.get("bbox")), default=None)
    maxx = max((g["bbox"][2] for g in geo if g.get("bbox")), default=None)
    maxy = max((g["bbox"][3] for g in geo if g.get("bbox")), default=None)

    # Simple zoom heuristic
    if None in (minx, miny, maxx, maxy):
        zoom_like = 8.0 if len(geo) == 1 else 6.0
    else:
        dx = maxx - minx
        dy = maxy - miny
        span = max(dx, dy)
        if span <= 0.2:
            zoom_like = 11
        elif span <= 0.5:
            zoom_like = 9
        elif span <= 1.5:
            zoom_like = 8
        elif span <= 3:
            zoom_like = 7
        else:
            zoom_like = 6

    return {
        "center_lat": center_lat,
        "center_lon": center_lon,
        "zoom_like": float(zoom_like),
        "bbox": [minx, miny, maxx, maxy] if None not in (minx, miny, maxx, maxy) else None,
    }
```

---

## services/dpe_service.py
```python
# services/dpe_service.py
from __future__ import annotations
from typing import List, Dict, Any, Optional
import requests
import pandas as pd

from config import settings

# --- Helpers

def _build_dpe_query(cities: List[Dict[str, Any]], min_surface: Optional[int], max_surface: Optional[int], limit: int) -> Dict[str, Any]:
    """
    Build a Data Fair query for ADEME DPE dataset.
    Filters by INSEE city codes when available, fallback to city label otherwise.
    """
    filters = []

    # Common field names in ADEME DPE datasets (may vary slightly). Adjust if needed.
    # We'll try by INSEE first (code_commune_insee) else by commune
    insee_codes = [g.get("insee") for g in cities if g.get("insee")]
    labels = [g.get("city") for g in cities if g.get("city")]

    if insee_codes:
        filters.append({"field": "code_commune_insee", "operator": "in", "value": insee_codes})
    elif labels:
        filters.append({"field": "nom_commune", "operator": "in", "value": labels})

    if min_surface is not None:
        filters.append({"field": "surface_habitable_logement", "operator": ">=", "value": min_surface})
    if max_surface is not None:
        filters.append({"field": "surface_habitable_logement", "operator": "<=", "value": max_surface})

    return {
        "size": limit,
        "q": None,
        "format": "json",
        "source": "default",
        "page": 1,
        "sort": [{"field": "date_etablissement_dpe", "order": "desc"}],
        "include": [
            "nom_commune",
            "code_commune_insee",
            "code_postal",
            "numero_voie",
            "nom_voie",
            "type_voie",
            "code_departement",
            "latitude",
            "longitude",
            "classe_consommation_energie",
            "classe_estimation_ges",
            "surface_habitable_logement",
            "date_etablissement_dpe",
        ],
        "facets": [],
        "filters": filters,
    }


def fetch_dpe(cities: List[Dict[str, Any]], min_surface: Optional[int], max_surface: Optional[int], limit: int = 500) -> pd.DataFrame:
    """Fetch DPE rows from ADEME Data Fair API and normalize into a DataFrame.
    Returns columns: full_address, city, insee, lat, lon, dpe, ges, surface, date_dpe
    """
    url = f"{settings.ADEME_BASE_URL}/{settings.DPE_DATASET_SLUG}/search"
    payload = _build_dpe_query(cities, min_surface, max_surface, limit)

    try:
        r = requests.post(url, json=payload, timeout=60)
        r.raise_for_status()
        js = r.json()
        rows = js.get("results", []) or js.get("hits", [])
    except Exception as e:
        # Fail gracefully with empty DF
        return pd.DataFrame(columns=["full_address", "city", "insee", "lat", "lon", "dpe", "ges", "surface", "date_dpe"])

    def fmt_address(row: Dict[str, Any]) -> str:
        parts = [
            str(row.get("numero_voie") or "").strip(),
            str(row.get("type_voie") or "").strip(),
            str(row.get("nom_voie") or "").strip(),
            str(row.get("code_postal") or "").strip(),
            str(row.get("nom_commune") or "").strip(),
        ]
        return " ".join([p for p in parts if p]).replace("  ", " ").strip()

    recs = []
    for row in rows:
        recs.append({
            "full_address": fmt_address(row),
            "city": row.get("nom_commune"),
            "insee": row.get("code_commune_insee"),
            "lat": row.get("latitude"),
            "lon": row.get("longitude"),
            "dpe": row.get("classe_consommation_energie"),
            "ges": row.get("classe_estimation_ges"),
            "surface": row.get("surface_habitable_logement"),
            "date_dpe": row.get("date_etablissement_dpe"),
        })

    df = pd.DataFrame.from_records(recs)

    # Drop rows without coordinates (can't place them on the map)
    df = df.dropna(subset=["lat", "lon"]).reset_index(drop=True)

    return df
```

---

## services/dvf_service.py
```python
# services/dvf_service.py
from __future__ import annotations
from typing import Dict, List, Any
import requests

from config import settings


def fetch_dvf_for_addresses(addresses: List[str]) -> Dict[str, List[dict]]:
    """
    Query DVF API for each address string and return mapping address -> list of transactions.
    This is a best‑effort free endpoint and may need refinement depending on the chosen DVF API.
    """
    out: Dict[str, List[dict]] = {}

    for addr in addresses:
        try:
            params = {"q": addr, "size": 10}
            r = requests.get(settings.DVF_BASE_URL, params=params, timeout=30)
            r.raise_for_status()
            js = r.json()
            # Try common keys used by Etalab style APIs
            feats = js.get("features") or js.get("results") or []
            tx = []
            for f in feats:
                props = f.get("properties", f)  # support plain list
                tx.append({
                    "date_mutation": props.get("date_mutation"),
                    "valeur_fonciere": props.get("valeur_fonciere"),
                    "nature_mutation": props.get("nature_mutation"),
                    "surface_reelle_bati": props.get("surface_reelle_bati"),
                    "nombre_pieces_principales": props.get("nombre_pieces_principales"),
                })
            out[addr] = tx
        except Exception:
            out[addr] = []

    return out
```

---

## ui/__init__.py
```python
# ui/__init__.py
```

---

## ui/map_view.py
```python
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
```

---

## ui/results_table.py
```python
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
            return str(df.iloc[idx]["row_id"])  # type: ignore
        return None
```

---

## utils/__init__.py
```python
# utils/__init__.py
```

---

## utils/filters.py
```python
# utils/filters.py
from __future__ import annotations
from typing import Dict, List, Tuple


def active_filters_summary(filters: Dict) -> List[Tuple[str, str]]:
    chips: List[Tuple[str, str]] = []
    if filters.get("cities"):
        chips.append(("cities", "Villes: " + ", ".join(filters["cities"])))
    if filters.get("min_surface") is not None:
        chips.append(("min_surface", f"Surface min: {filters['min_surface']} m²"))
    if filters.get("max_surface") is not None:
        chips.append(("max_surface", f"Surface max: {filters['max_surface']} m²"))
    return chips


def clear_all_filters(state) -> None:
    state.filters = {"cities": [], "min_surface": None, "max_surface": None}


def remove_filter(state, key: str) -> None:
    if key in state.filters:
        if isinstance(state.filters[key], list):
            state.filters[key] = []
        else:
            state.filters[key] = None
```

