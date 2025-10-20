# core/postal_layers.py
import requests
import folium
import streamlit as st


@st.cache_data(ttl=86400)
def get_postalcode_geojson(code_postal: str):
    """Récupère le GeoJSON des contours du code postal depuis l’API Etalab."""
    try:
        url = f"https://geo.api.gouv.fr/communes?codePostal={code_postal}&format=geojson"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None


def draw_postalcode_boundaries(m, codes_postaux):
    """Ajoute les contours des codes postaux sur la carte Folium."""
    for cp in codes_postaux:
        geojson = get_postalcode_geojson(cp)
        if geojson:
            folium.GeoJson(
                geojson,
                name=f"CP {cp}",
                style_function=lambda x: {
                    "color": "#FF6600",
                    "weight": 2,
                    "fillOpacity": 0.05,
                },
            ).add_to(m)


@st.cache_data(ttl=86400)
def get_cadastre_parcelle_geojson(lat, lon):
    """Récupère le GeoJSON des parcelles cadastrales autour d’un point."""
    try:
        url = "https://apicarto.ign.fr/api/cadastre/parcelle"
        r = requests.get(
            url,
            params={"geom": f"POINT({lon} {lat})", "format": "geojson"},
            timeout=5,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None


def draw_cadastre_layer(m, lat=None, lon=None):
    """Ajoute le calque des parcelles cadastrales sur la carte."""
    if not lat or not lon:
        return
    geojson = get_cadastre_parcelle_geojson(lat, lon)
    if geojson:
        folium.GeoJson(
            geojson,
            name="Parcelles cadastrales",
            style_function=lambda x: {
                "color": "#0080FF",
                "weight": 1,
                "fillOpacity": 0.05,
            },
        ).add_to(m)
