# core/postal_layers.py
import requests

def _fetch_commune_contour_by_cp(cp: str):
    """Retourne un FeatureCollection GeoJSON (contour) pour un code postal donné."""
    try:
        url = "https://geo.api.gouv.fr/communes"
        params = {
            "codePostal": cp,
            "format": "geojson",
            "geometry": "contour",  # indispensable pour avoir le polygone
        }
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            return r.json()  # FeatureCollection
    except Exception:
        pass
    return {"type": "FeatureCollection", "features": []}


def get_postalcode_geojson(code_postaux):
    """
    Agrège les contours des communes correspondant à CHAQUE code postal fourni.
    Retourne un FeatureCollection fusionné.
    """
    if not code_postaux:
        return {"type": "FeatureCollection", "features": []}

    features = []
    for cp in code_postaux:
        fc = _fetch_commune_contour_by_cp(str(cp))
        feats = fc.get("features", [])
        # enrichit le tooltip: ajoute 'codePostal' (utile côté popup)
        for f in feats:
            props = f.setdefault("properties", {})
            props["codePostal"] = str(cp)
        features.extend(feats)

    return {"type": "FeatureCollection", "features": features}
