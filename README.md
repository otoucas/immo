# DPE-GES Finder – dépôt Streamlit (arbo + code)

Ci-dessous, l’arborescence proposée et **tout le code** nécessaire, découpé par fichiers. L’application repose sur **Streamlit**, **PyDeck**, **requests**, **pandas** et **streamlit-aggrid**.

> ⚠️ Les endpoints d’API Data Fair/ADEME et DVF changent parfois d’URL. J’ai isolé ces URLs dans `config.py` pour pouvoir les ajuster facilement sans toucher au reste du code.

---

## Arborescence

```
.
├── app.py
├── README.md
├── requirements.txt
├── config.py
├── utils
│   ├── cache.py
│   └── geo.py
├── data_adapters
│   ├── ademe_client.py
│   ├── dvf_client.py
│   └── geocoding_client.py
├── services
│   └── search_service.py
└── ui
    ├── state.py
    └── components
        ├── sidebar.py
        ├── map_view.py
        └── results_table.py
```

---

## `requirements.txt`

```txt
streamlit>=1.36
pandas>=2.2
requests>=2.32
pydeck>=0.9
streamlit-aggrid>=0.3.5
numpy>=1.26
```

---

## `README.md`

```md
# DPE-GES Finder

Application Streamlit pour interroger les données open data ADEME (DPE/GES) et afficher les résultats (adresse, DPE, GES, surface) sur une **carte** et un **tableau** en permanence. Intégration d’indices DVF (à la même adresse) dans la fiche (popup) de chaque résultat.

## Lancer en local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Environnements / configuration

Les URLs d’API sont centralisées dans `config.py`. Adaptez si nécessaire les slugs/URLs des datasets.

```
ADEME_DATASET_SLUG = "dpe-logements-existants-depuis-juillet-2021"
ADEME_API_BASE = "https://data.ademe.fr/data-fair/api/v1"
DVF_DATASET_SLUG = "demandes-de-valeurs-foncieres-geolocalisees"
DVF_API_BASE = "https://www.data.gouv.fr/fr/datasets/r/"  # ou endpoint Data Fair si dispo
ADRESSE_API = "https://api-adresse.data.gouv.fr"  # (service Geoplateforme possible)
```

> Remarque : certains producteurs exposent les données via Data Fair avec des endpoints de type `/datasets/<slug>/lines`. Si l’URL précise change, ne modifier que `config.py`.
```

```

---

## `config.py`

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    # ADEME
    ADEME_API_BASE: str = "https://data.ademe.fr/data-fair/api/v1"
    ADEME_DATASET_SLUG: str = "dpe-logements-existants-depuis-juillet-2021"

    # DVF (à adapter selon votre source API ; fallback : réutilisation Data.gouv ou service interne)
    # Ex. si dataset exposé via Data Fair : "https://data.gouv.fr/data-fair/api/v1"
    DVF_API_BASE: str = "https://data.ademe.fr/data-fair/api/v1"  # remplacer si besoin
    DVF_DATASET_SLUG: str = "demandes-de-valeurs-foncieres-geolocalisees"  # exemple

    # Géocodage
    ADRESSE_API: str = "https://api-adresse.data.gouv.fr"  # service BAN (toujours actif)
    # Pour Geoplateforme (IGN) : https://geocodage.ign.fr/ (adapter client si vous basculez)

    # App
    MAX_ROWS: int = 1000

SETTINGS = Settings()
```

---

## `utils/cache.py`

```python
import functools
import time
from typing import Callable

# Petit cache mémoire simple pour éviter de spammer les APIs

def memoize_ttl(ttl_seconds: int = 600):
    def decorator(func: Callable):
        cache = {}
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.time()
            if key in cache:
                ts, value = cache[key]
                if now - ts < ttl_seconds:
                    return value
            value = func(*args, **kwargs)
            cache[key] = (now, value)
            return value
        return wrapper
    return decorator
```

---

## `utils/geo.py`

```python
from typing import List, Tuple
import numpy as np


def centroid(points: List[Tuple[float, float]]) -> Tuple[float, float]:
    """Retourne (lat, lon) du barycentre d'une liste de points (lat, lon)."""
    if not points:
        return (46.5, 2.5)  # centre France approx
    arr = np.array(points)
    lat = float(arr[:, 0].mean())
    lon = float(arr[:, 1].mean())
    return lat, lon
```

---

## `data_adapters/geocoding_client.py`

```python
from typing import Dict, List, Optional
import requests
from urllib.parse import urlencode
from utils.cache import memoize_ttl
from config import SETTINGS


class GeocodingClient:
    """Client pour l'API Adresse (BAN)."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or SETTINGS.ADRESSE_API

    @memoize_ttl(3600)
    def search_city(self, q: str, postcode: Optional[str] = None, limit: int = 5) -> List[Dict]:
        params = {
            "q": q,
            "type": "municipality",
            "limit": limit,
        }
        if postcode:
            params["postcode"] = postcode
        url = f"{self.base_url}/search/?{urlencode(params)}"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        feats = data.get("features", [])
        results = []
        for f in feats:
            props = f.get("properties", {})
            lon, lat = f.get("geometry", {}).get("coordinates", [None, None])
            results.append({
                "city": props.get("city"),
                "postcode": props.get("postcode"),
                "label": props.get("label"),
                "lat": lat,
                "lon": lon,
                "citycode": props.get("citycode"),
            })
        return results
```

---

## `data_adapters/ademe_client.py`

```python
from typing import Dict, List, Optional, Tuple
import requests
import pandas as pd
from urllib.parse import urlencode
from config import SETTINGS


# Champs cibles renvoyés par le dataset ADEME (à ajuster si le schéma évolue)
ADEME_FIELDS = {
    "adresse": [
        "adresse_complete",  # ex. concat déjà fournie
        "adresse",            # fallback
    ],
    "code_postal": ["code_postal"],
    "commune": ["nom_commune", "commune"],
    "lat": ["latitude", "lat"],
    "lon": ["longitude", "lon"],
    "dpe": ["classe_dpe", "classe_energie"],
    "ges": ["classe_ges", "classe_emission_ges"],
    "surface": ["surface_habitable_logement", "surface_habitable", "surface"]
}


def _first(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


class AdemeDPEClient:
    def __init__(self, base_url: Optional[str] = None, dataset_slug: Optional[str] = None):
        self.base_url = base_url or SETTINGS.ADEME_API_BASE
        self.dataset_slug = dataset_slug or SETTINGS.ADEME_DATASET_SLUG

    def _dataset_lines_url(self) -> str:
        return f"{self.base_url}/datasets/{self.dataset_slug}/lines"

    def search(
        self,
        citycodes: Optional[List[str]] = None,
        postcodes: Optional[List[str]] = None,
        dpe_classes: Optional[List[str]] = None,
        ges_classes: Optional[List[str]] = None,
        surface_min: Optional[int] = None,
        surface_max: Optional[int] = None,
        size: int = 1000,
    ) -> pd.DataFrame:
        """
        Construit une requête Data Fair sur le dataset ADEME.
        Filtrage basique via paramètres `qs` (full-text) et `refine.*` quand possible.
        """
        url = self._dataset_lines_url()
        params = {
            "size": min(size, SETTINGS.MAX_ROWS),
        }

        refine = []
        if citycodes:
            for code in citycodes:
                refine.append(("refine.nom_commune", code))  # selon schéma réel, sinon citycode
        if postcodes:
            for pc in postcodes:
                refine.append(("refine.code_postal", pc))
        if dpe_classes:
            for c in dpe_classes:
                refine.append(("refine.classe_dpe", c))
        if ges_classes:
            for c in ges_classes:
                refine.append(("refine.classe_ges", c))
        # Plage sur surface
        if surface_min is not None:
            params["gte.surface_habitable_logement"] = surface_min
        if surface_max is not None:
            params["lte.surface_habitable_logement"] = surface_max

        # Encoder manuellement les refines multiples
        query = urlencode(params)
        for k, v in refine:
            query += f"&{k}={v}"
        final_url = f"{url}?{query}"

        r = requests.get(final_url, timeout=30)
        r.raise_for_status()
        payload = r.json()

        rows = payload.get("results") or payload.get("data") or []
        df = pd.DataFrame(rows)
        if df.empty:
            return pd.DataFrame(columns=["adresse", "code_postal", "commune", "lat", "lon", "dpe", "ges", "surface"])

        # Remap champs
        col_adresse = _first(df, ADEME_FIELDS["adresse"]) or "adresse"
        col_cp = _first(df, ADEME_FIELDS["code_postal"]) or "code_postal"
        col_commune = _first(df, ADEME_FIELDS["commune"]) or "commune"
        col_lat = _first(df, ADEME_FIELDS["lat"]) or "lat"
        col_lon = _first(df, ADEME_FIELDS["lon"]) or "lon"
        col_dpe = _first(df, ADEME_FIELDS["dpe"]) or "classe_dpe"
        col_ges = _first(df, ADEME_FIELDS["ges"]) or "classe_ges"
        col_surf = _first(df, ADEME_FIELDS["surface"]) or "surface"

        out = pd.DataFrame({
            "adresse": df[col_adresse],
            "code_postal": df[col_cp],
            "commune": df[col_commune],
            "lat": pd.to_numeric(df[col_lat], errors="coerce"),
            "lon": pd.to_numeric(df[col_lon], errors="coerce"),
            "dpe": df[col_dpe],
            "ges": df[col_ges],
            "surface": pd.to_numeric(df[col_surf], errors="coerce"),
        }).dropna(subset=["lat", "lon"]).reset_index(drop=True)
        return out
```

---

## `data_adapters/dvf_client.py`

```python
from typing import Dict, List, Optional
import requests
import pandas as pd
from urllib.parse import urlencode
from config import SETTINGS

# Ce client récupère des mutations DVF à proximité d'une adresse (par code postal + nom de voie)
# Adapter l'endpoint selon votre source (Data Fair, service interne, etc.)

class DVFClient:
    def __init__(self, base_url: Optional[str] = None, dataset_slug: Optional[str] = None):
        self.base_url = base_url or SETTINGS.DVF_API_BASE
        self.dataset_slug = dataset_slug or SETTINGS.DVF_DATASET_SLUG

    def _dataset_lines_url(self) -> str:
        return f"{self.base_url}/datasets/{self.dataset_slug}/lines"

    def search_by_address(self, street_name: str, postcode: str, limit: int = 20) -> pd.DataFrame:
        url = self._dataset_lines_url()
        params = {
            "size": limit,
            # full text, à défaut de colonnes exactes (à ajuster au schéma du dataset retenu)
            "q": f"{street_name} {postcode}"
        }
        r = requests.get(f"{url}?{urlencode(params)}", timeout=30)
        r.raise_for_status()
        payload = r.json()
        rows = payload.get("results") or payload.get("data") or []
        if not rows:
            return pd.DataFrame(columns=["date_mutation","valeur_fonciere","type_local","surface_reelle_bati","adresse_nom_voie","code_postal"])
        df = pd.DataFrame(rows)
        # mapping champs probables
        keep = [c for c in [
            "date_mutation","valeur_fonciere","type_local","surface_reelle_bati",
            "adresse_nom_voie","code_postal","nom_commune"
        ] if c in df.columns]
        return df[keep].copy()
```

---

## `services/search_service.py`

```python
from typing import Dict, List, Optional, Tuple
import pandas as pd
from data_adapters.geocoding_client import GeocodingClient
from data_adapters.ademe_client import AdemeDPEClient
from data_adapters.dvf_client import DVFClient
from utils.geo import centroid

class SearchService:
    def __init__(self):
        self.geo = GeocodingClient()
        self.ademe = AdemeDPEClient()
        self.dvf = DVFClient()

    def geocode_city(self, name: str, postcode: Optional[str] = None):
        return self.geo.search_city(name, postcode=postcode, limit=5)

    def compute_map_center(self, cities: List[Dict]) -> Tuple[float, float]:
        pts = [(c["lat"], c["lon"]) for c in cities if c.get("lat") and c.get("lon")]
        return centroid(pts)

    def search_ademe(self, selected_cities: List[Dict], postcodes: List[str], dpe: List[str], ges: List[str], smin: int, smax: int) -> pd.DataFrame:
        citycodes = [c.get("citycode") for c in selected_cities if c.get("citycode")]
        pcodes = list({c.get("postcode") for c in selected_cities if c.get("postcode")})
        pcodes.extend(postcodes)
        pcodes = list({p for p in pcodes if p})
        return self.ademe.search(citycodes=citycodes or None,
                                 postcodes=pcodes or None,
                                 dpe_classes=dpe or None,
                                 ges_classes=ges or None,
                                 surface_min=smin, surface_max=smax)

    def dvf_for_result_row(self, row: pd.Series) -> pd.DataFrame:
        # tenter avec la voie extraite de l'adresse
        street = str(row.get("adresse", "")).split(",")[0].strip()
        return self.dvf.search_by_address(street_name=street, postcode=str(row.get("code_postal", "")))
```

---

## `ui/state.py`

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class AppState:
    selected_cities: List[Dict] = field(default_factory=list)
    extra_postcodes: List[str] = field(default_factory=list)
    dpe_filters: List[str] = field(default_factory=list)  # ["A","B",...]
    ges_filters: List[str] = field(default_factory=list)
    surface_min: int = 50
    surface_max: int = 200
    results: Optional[object] = None  # DataFrame
    selected_row_idx: Optional[int] = None
```

---

## `ui/components/sidebar.py`

```python
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
    if st.sidebar.button("Ajouter codes postaux"):
        raw = st.session_state.get("_tmp_pcs", "")
        pcs = [p.strip() for p in raw.split(",") if p.strip()]
        for p in pcs:
            if p not in state.extra_postcodes:
                state.extra_postcodes.append(p)
        st.session_state["_tmp_pcs"] = ""
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
```

---

## `ui/components/map_view.py`

```python
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
```

---

## `ui/components/results_table.py`

```python
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
```

---

## `app.py`

```python
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
```

