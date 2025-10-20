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
