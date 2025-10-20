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
