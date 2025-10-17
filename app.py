import requests
import streamlit as st
from streamlit_folium import st_folium
import folium
import json
from math import radians, cos, sin, sqrt, atan2

# -----------------------------
# Configuration de la page
# -----------------------------
st.set_page_config(page_title="Recherche DPE - Open Data France", page_icon="🏠")

st.title("🏠 Recherche DPE - Open Data France")
st.markdown("""
Recherchez des logements par adresse, ville, code postal ou dans un rayon géographique.  
Filtrez selon la **classe énergétique (DPE)**, le **GES** et la **surface habitable**.
""")

# -----------------------------
# Fonction utilitaire
# -----------------------------
def distance_km(lat1, lon1, lat2, lon2):
    """Retourne la distance entre deux points GPS en kilomètres."""
    R = 6371  # rayon de la Terre (km)
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

# -----------------------------
# Gestion des filtres sauvegardés
# -----------------------------
if "saved_filters" not in st.session_state:
    st.session_state["saved_filters"] = {}

def save_filters(filters):
    with open("saved_filters.json", "w") as f:
        json.dump(filters, f)
    st.success("🎉 Filtres sauvegardés !")

def load_filters():
    try:
        with open("saved_filters.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# -----------------------------
# Bloc de recherche
# -----------------------------
recherche = st.text_input("🔍 Recherche :", placeholder="Ex : Paris, Lyon, 75001 ou 10 rue de Rivoli")

with st.expander("⚙️ Filtres avancés"):
    col1, col2 = st.columns(2)
    with col1:
        classe_energie = st.multiselect("Classe énergétique (DPE) :", list("ABCDEFG"), default=[])
        classe_ges = st.multiselect("Classe GES :", list("ABCDEFG"), default=[])
    with col2:
        code_postaux = st.text_input("Codes postaux (séparés par des virgules) :", placeholder="Ex : 75001, 75002, 75003")

    surface_min, surface_max = st.slider("Surface habitable (m²) :", 0, 500, (0, 500), step=10)

    st.markdown("### 📍 Zone géographique")
    choix_zone = st.radio("Type de recherche géographique :", ["Aucune", "Ville", "Coordonnées GPS"], horizontal=True)

    lat_centre = lon_centre = None
    if choix_zone == "Ville":
        ville = st.text_input("Nom de la ville :", placeholder="Ex : Lyon")
        rayon_km = st.slider("Rayon (km) autour de la ville :", 1, 50, 10)
        if ville:
            # Géocodage via API Nominatim (OpenStreetMap)
            geocode_url = "https://nominatim.openstreetmap.org/search"
            geo_params = {"q": ville, "format": "json", "limit": 1}
            r = requests.get(geocode_url, params=geo_params)
            if r.ok and r.json():
                data = r.json()[0]
                lat_centre, lon_centre = float(data["lat"]), float(data["lon"])
                st.success(f"📍 Ville trouvée : {ville} ({lat_centre:.4f}, {lon_centre:.4f})")
            else:
                st.warning("Ville non trouvée.")
    elif choix_zone == "Coordonnées GPS":
        lat_centre = st.number_input("Latitude :", value=48.8566)
        lon_centre = st.number_input("Longitude :", value=2.3522)
        rayon_km = st.slider("Rayon (km) :", 1, 50, 10)

    # Sauvegarde des filtres
    if st.button("💾 Sauvegarder les filtres"):
        current_filters = {
            "classe_energie": classe_energie,
            "classe_ges": classe_ges,
            "surface_min": surface_min,
            "surface_max": surface_max,
            "code_postaux": code_postaux,
            "choix_zone": choix_zone,
            "lat": lat_centre,
            "lon": lon_centre,
            "rayon_km": rayon_km if choix_zone != "Aucune" else None,
        }
        save_filters(current_filters)

    # Chargement des filtres
    if st.button("📂 Charger les filtres sauvegardés"):
        saved = load_filters()
        if saved:
            st.session_state.update(saved)
            st.experimental_rerun()
        else:
            st.warning("Aucun filtre sauvegardé trouvé.")

# -----------------------------
# Recherche API ADEME
# -----------------------------
if st.button("🔎 Lancer la recherche") and recherche.strip():
    with st.spinner("Recherche en cours..."):
        base_url = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-france/lines"
        params = {"q": recherche, "size": 200}
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])

        if not results:
            st.warning("Aucun résultat trouvé.")
        else:
            # --- Filtres ---
            if classe_energie:
                results = [r for r in results if r.get("classe_consommation_energie") in classe_energie]
            if classe_ges:
                results = [r for r in results if r.get("classe_estimation_ges") in classe_ges]
            if surface_min or surface_max:
                results = [
                    r for r in results
                    if r.get("surface_habitable_logement") and surface_min <= r["surface_habitable_logement"] <= surface_max
                ]
            if code_postaux.strip():
                codes = [cp.strip() for cp in code_postaux.split(",") if cp.strip()]
                results = [r for r in results if str(r.get("code_postal", "")) in codes]

            # --- Filtrage géographique ---
            if lat_centre and lon_centre:
                results = [
                    r for r in results
                    if r.get("latitude") and r.get("longitude") and
                    distance_km(lat_centre, lon_centre, float(r["latitude"]), float(r["longitude"])) <= rayon_km
                ]

            # --- Affichage ---
            if not results:
                st.warning("Aucun résultat ne correspond aux filtres.")
            else:
                st.success(f"{len(results)} résultat(s) trouvé(s).")

                # Carte
                points = [
                    (
                        float(r["latitude"]), float(r["longitude"]),
                        r.get("adresse", "Adresse inconnue"),
                        r.get("code_postal", ""), r.get("nom_commune", ""),
                        r.get("classe_consommation_energie", "N/A"),
                        r.get("classe_estimation_ges", "N/A")
                    )
                    for r in results if r.get("latitude") and r.get("longitude")
                ]
                if points:
                    lat_moy = sum(p[0] for p in points) / len(points)
                    lon_moy = sum(p[1] for p in points) / len(points)
                    m = folium.Map(location=[lat_moy, lon_moy], zoom_start=11)

                    for lat, lon, adresse, cp, commune, dpe, ges in points:
                        folium.Marker(
                            [lat, lon],
                            popup=f"<b>{adresse}</b><br>{cp} {commune}<br>DPE : <b>{dpe}</b> | GES : <b>{ges}</b>",
                            tooltip=adresse,
                            icon=folium.Icon(color="blue", icon="home", prefix="fa"),
                        ).add_to(m)

                    if lat_centre and lon_centre:
                        folium.Circle(
                            radius=rayon_km * 1000,
                            location=[lat_centre, lon_centre],
                            color="red",
                            fill=False
                        ).add_to(m)

                    st.subheader("🗺️ Carte des résultats")
                    st_folium(m, width=700, height=500)

                # Liste
                st.subheader("📋 Détails des logements")
                for r in results:
                    adresse = r.get("adresse", "Adresse inconnue")
                    code_postal = r.get("code_postal", "")
                    commune = r.get("nom_commune", "")
                    classe_energie = r.get("classe_consommation_energie", "N/A")
                    classe_ges = r.get("classe_estimation_ges", "N/A")
                    annee_construction = r.get("annee_construction", "N/A")
                    surface = r.get("surface_habitable_logement", "N/A")
                    numero_dpe = r.get("numero_dpe", "")
                    with st.expander(f"📍 {adresse}, {code_postal} {commune}"):
                        st.write(f"**Numéro DPE :** {numero_dpe}")
                        st.write(f"**Classe énergie :** {classe_energie}")
                        st.write(f"**Classe GES :** {classe_ges}")
                        st.write(f"**Année construction :** {annee_construction}")
                        st.write(f"**Surface :** {surface} m²")
