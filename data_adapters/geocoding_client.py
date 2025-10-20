
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
