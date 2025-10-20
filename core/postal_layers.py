import requests

def get_postalcode_geojson(code_postaux):
    try:
        url = "https://geo.api.gouv.fr/communes"
        params = {"codePostal": ",".join(code_postaux), "format": "geojson"}
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None
