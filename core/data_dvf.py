# core/data_dvf.py

import requests

def get_dvf_data(code_postal, voie=""):
    """
    Récupère les ventes immobilières récentes depuis l'API DVF Etalab.
    """
    try:
        url = "https://api.dvf.etalab.gouv.fr/search"
        params = {"code_postal": code_postal, "voie": voie}
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            return []
        js = r.json()
        ventes = []
        for v in js.get("resultats", []):
            ventes.append({
                "date": v.get("date_mutation"),
                "type": v.get("type_local"),
                "surface": v.get("surface_reelle_bati"),
                "valeur_fonciere": v.get("valeur_fonciere"),
            })
        return ventes
    except Exception:
        return []
