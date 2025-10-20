# services/dpe_service.py
from __future__ import annotations
from typing import List, Dict, Any, Optional
import requests
import pandas as pd

from config import settings


def fetch_dpe(
    cities: List[Dict[str, Any]],
    min_surface: Optional[int],
    max_surface: Optional[int],
    limit: int = 500,
) -> pd.DataFrame:
    """
    Récupère les données DPE depuis le portail OpenData ADEME.
    Utilise le dataset 'dpe-v2-logements', plus fiable que 'dpe-logements'.
    Retourne un DataFrame avec adresse, DPE, GES, surface, date, coordonnées...
    """

    url = f"{settings.ADEME_BASE_URL}/dpe-v2-logements/search"

    # Construction du texte de requête (qs) au lieu du champ "filters"
    qs_parts = []

    # --- Communes ---
    insee_codes = [c.get("insee") for c in cities if c.get("insee")]
    noms = [c.get("city") for c in cities if c.get("city")]

    if insee_codes:
        qs_parts.append(
            " OR ".join([f'code_insee_commune_actualise:"{c}"' for c in insee_codes])
        )
    elif noms:
        qs_parts.append(" OR ".join([f'nom_commune:"{n}"' for n in noms]))

    # --- Surfaces ---
    if min_surface and not max_surface:
        qs_parts.append(f"surface_habitable_logement:[{min_surface} TO *]")
    elif max_surface and not min_surface:
        qs_parts.append(f"surface_habitable_logement:[* TO {max_surface}]")
    elif min_surface and max_surface:
        qs_parts.append(
            f"surface_habitable_logement:[{min_surface} TO {max_surface}]"
        )

    # Construction de la requête complète
    query_str = " AND ".join(qs_parts) if qs_parts else None

    payload = {
        "size": limit,
        "q": None,
        "qs": query_str,
        "format": "json",
        "source": "default",
        "include": [
            "nom_commune",
            "code_postal",
            "code_insee_commune_actualise",
            "latitude",
            "longitude",
            "classe_consommation_energie",
            "classe_estimation_ges",
            "surface_habitable_logement",
            "date_etablissement_dpe",
            "numero_voie",
            "nom_voie",
            "type_voie",
        ],
    }

    try:
        r = requests.post(url, json=payload, timeout=60)
        r.raise_for_status()
        js = r.json()
        rows = js.get("results", []) or js.get("hits", [])
    except Exception as e:
        print("⚠️ Erreur d’appel ADEME :", e)
        return pd.DataFrame()

   if not rows:
        print("⚠️ Aucun résultat renvoyé par l’API ADEME.")
        return pd.DataFrame()

    def fmt_address(row: Dict[str, Any]) -> str:
        """Construit une adresse lisible à partir des champs ADEME."""
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
        recs.append(
            {
                "full_address": fmt_address(row),
                "city": row.get("nom_commune"),
                "insee": row.get("code_insee_commune_actualise"),
                "lat": row.get("latitude"),
                "lon": row.get("longitude"),
                # harmonisation de noms de colonnes :
                "dpe": row.get("classe_consommation_energie"),
                "ges": row.get("classe_estimation_ges"),
                "surface": row.get("surface_habitable_logement"),
                "date_dpe": row.get("date_etablissement_dpe"),
            }
        )

    df = pd.DataFrame.from_records(recs)

    # 🔧 Harmonise et nettoie les colonnes pour l'app
    expected_cols = ["full_address", "city", "lat", "lon", "dpe", "ges", "surface", "date_dpe"]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = None

    df = df.dropna(subset=["lat", "lon"]).reset_index(drop=True)
    return df
