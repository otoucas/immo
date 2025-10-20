# core/postal_layers.py
import requests
import folium
from folium import GeoJson
from folium.features import GeoJsonTooltip

def get_postalcode_geojson(code_postal: str):
    """Récupère le contour d'un code postal via l'API Geo.gouv.fr"""
    try:
        url = f"https://geo.api.gouv.fr/communes?codePostal={code_postal}&format=geojson"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def add_postalcode_layer(map_obj: folium.Map, code_postaux: list):
    """Ajoute les contours des codes postaux sur la carte."""
    for cp in code_postaux:
        geojson_data = get_postalcode_geojson(cp)
        if geojson_data:
            GeoJson(
                geojson_data,
                name=f"Code postal {cp}",
                style_function=lambda x: {
                    "fillColor": "#3388ff",
                    "color": "#3388ff",
                    "weight": 2,
                    "fillOpacity": 0.05,
                },
                tooltip=GeoJsonTooltip(fields=["nom"], aliases=["Commune :"]),
            ).add_to(map_obj)
    folium.LayerControl().add_to(map_obj)


def add_cadastre_layer(map_obj: folium.Map):
    """Ajoute le calque WMS du cadastre sur la carte."""
    folium.raster_layers.WmsTileLayer(
        url="https://wms.cadastre.gouv.fr/cadastre",
        layers="CP.CadastralParcel",
        fmt="image/png",
        transparent=True,
        name="Parcelles cadastrales",
        attribution="Cadastre © DGFiP",
    ).add_to(map_obj)
    folium.LayerControl().add_to(map_obj)
