# services/dpe_service.py
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
return " ".join([p for p in parts if p]).replace(" ", " ").strip()


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
