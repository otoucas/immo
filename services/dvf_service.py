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
props = f.get("properties", f) # support plain list
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
