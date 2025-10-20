import requests
import pandas as pd

def fetch_ademe_all(code_postaux):
    dfs = []
    for cp in code_postaux:
        try:
            url = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-france/lines"
            params = {"q": cp, "size": 300, "page": 1}
            resp = requests.get(url, params=params, timeout=10)
            js = resp.json()
            df = pd.DataFrame(js["results"])
            dfs.append(df)
        except Exception:
            pass
    if not dfs:
        return pd.DataFrame()
    df = pd.concat(dfs, ignore_index=True)
    return df
