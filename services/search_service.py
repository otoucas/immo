from typing import Dict, List, Optional, Tuple
import pandas as pd
from data_adapters.geocoding_client import GeocodingClient
from data_adapters.ademe_client import AdemeDPEClient
from data_adapters.dvf_client import DVFClient
from utils.geo import centroid

class SearchService:
    def __init__(self):
        self.geo = GeocodingClient()
        self.ademe = AdemeDPEClient()
        self.dvf = DVFClient()

    def geocode_city(self, name: str, postcode: Optional[str] = None):
        return self.geo.search_city(name, postcode=postcode, limit=5)

    def compute_map_center(self, cities: List[Dict]) -> Tuple[float, float]:
        pts = [(c["lat"], c["lon"]) for c in cities if c.get("lat") and c.get("lon")]
        return centroid(pts)

    def search_ademe(self, selected_cities, dpe, ges, smin, smax):
        citycodes = [c.get("citycode") for c in selected_cities if c.get("citycode")]
        return self.ademe.search(citycodes=citycodes or None,
                                 dpe_classes=dpe or None,
                                 ges_classes=ges or None,
                                 surface_min=smin, surface_max=smax)


    def dvf_for_result_row(self, row: pd.Series) -> pd.DataFrame:
        # tenter avec la voie extraite de l'adresse
        street = str(row.get("adresse", "")).split(",")[0].strip()
        return self.dvf.search_by_address(street_name=street, postcode=str(row.get("code_postal", "")))
