import requests
import streamlit as st
from streamlit_folium import st_folium
import folium
import json
from math import radians, cos, sin, sqrt, atan2
from io import BytesIO
import pandas as pd

# -----------------------------
# Utils
# -----------------------------
def distance_km(lat1, lon1, lat2, lon2):
    R = 6371
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def safe_float(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default

def safe_int(x, default=None):
    try:
        return int(x)
    except (TypeError, ValueError):
        return default

def get_ademe_results(q, size=200):
    base_url = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-france/lines"
    params = {"q": q, "size": size}
    r = requests.get(base_url, params=params, timeout=20)
    r.raise_for_status()
    js = r.json()
    # certains endpoints retournent 'results', d'autres 'data'
    results = js.get("results") or js.get("data") or js.get("hits") or []
    # si la forme est {"results": {"rows": [...]}} ou autre, essayer de détecter une liste
    if isinstance(results, dict):
        # trouver une valeur list dans le dict
        for v in results.values():
            if isinstance(v, list):
                results = v
                break
    if not isinstance(results, list):
        results = []
    return results

# -----------------------------
# Page config
# -----------------------------
st.set_page_config(page_title="Recherche DPE - Open Data France", page_icon="🏠", layout="wide")
st.title("🏠 Recherche DPE - Open Data France (corrigé)")

# -----------------------------
# Session saved filters container
# -----------------------------
if "saved_filters" not in st.session_state:
    st.session_state["saved_filters"] = {}  # nom -> dict

# -----------------------------
# Inputs (avec keys pour faciliter le reload)
# -----------------------------
with st.sidebar:
    st.header("Paramètres de recherche")
    recherche = st.text_input("🔍 Recherche (adresse / ville / CP / DPE)", key="recherche")

    st.markdown("### Filtres DPE / GES / Surface")
    classe_energie = st.multiselect("Classe énergétique (DPE)", list("ABCDEFG"), key="classe_energie")
    classe_ges = st.multiselect("Classe GES", list("ABCDEFG"), key="classe_ges")
    surface_min, surface_max = st.slider("Surface habitable (m²)", 0, 500, (0, 500), step=5, key="surface_range")

    st.markdown("### Codes postaux")
    code_postaux = st.text_input("Codes postaux (séparés par virgule)", placeholder="75001,75002", key="code_postaux")

    st.markdown("### Zone géographique (optionnel)")
    choix_zone = st.radio("Type", ["Aucune", "Ville", "Coordonnées GPS"], index=0, key="choix_zone", horizontal=True)
    lat_centre = lon_centre = None
    rayon_km = None
    if choix_zone == "Ville":
        ville = st.text_input("Nom de la ville", key="ville_name")
        rayon_km = st.slider("Rayon (km)", 1, 100, 10, key="rayon_km")
        if ville:
            # Nominatim requiert un User-Agent ; on retourne la 1ère réponse si ok
            try:
                geocode_url = "https://nominatim.openstreetmap.org/search"
                headers = {"User-Agent": "dpe-search-app/1.0 (contact: dev@example.com)"}
                geo_params = {"q": ville, "format": "json", "limit": 1}
                r = requests.get(geocode_url, params=geo_params, headers=headers, timeout=10)
                if r.ok and r.json():
                    data = r.json()[0]
                    lat_centre = safe_float(data.get("lat"))
                    lon_centre = safe_float(data.get("lon"))
                    st.success(f"Ville trouvée : {ville} — ({lat_centre:.5f}, {lon_centre:.5f})")
                else:
                    st.warning("Ville non trouvée (vérifie l'orthographe).")
            except Exception as e:
                st.warning(f"Erreur géocodage : {e}")
    elif choix_zone == "Coordonnées GPS":
        lat_centre = st.number_input("Latitude", value=48.8566, format="%.6f", key="lat_centre")
        lon_centre = st.number_input("Longitude", value=2.3522, format="%.6f", key="lon_centre")
        rayon_km = st.slider("Rayon (km)", 1, 100, 10, key="rayon_km_gps")

    st.markdown("---")
    # Sauvegarde / chargement filters
    with st.expander("Sauvegarder / Charger filtres"):
        save_name = st.text_input("Nom de la sauvegarde", key="save_name")
        if st.button("💾 Sauvegarder dans la session"):
            keyname = save_name.strip() or f"sauvegarde_{len(st.session_state['saved_filters'])+1}"
            st.session_state["saved_filters"][keyname] = {
                "recherche": st.session_state.get("recherche", ""),
                "classe_energie": st.session_state.get("classe_energie", []),
                "classe_ges": st.session_state.get("classe_ges", []),
                "surface_range": st.session_state.get("surface_range", (0,500)),
                "code_postaux": st.session_state.get("code_postaux", ""),
                "choix_zone": st.session_state.get("choix_zone", "Aucune"),
                "lat_centre": lat_centre,
                "lon_centre": lon_centre,
                "rayon_km": rayon_km
            }
            st.success(f"Filtres sauvegardés sous le nom : {keyname}")

        # Export JSON téléchargeable
        if st.session_state["saved_filters"]:
            if st.button("Télécharger toutes les sauvegardes (.json)"):
                b = BytesIO()
                b.write(json.dumps(st.session_state["saved_filters"], ensure_ascii=False, indent=2).encode("utf-8"))
                b.seek(0)
                st.download_button("Télécharger JSON", b, file_name="filters_saved.json", mime="application/json")

        st.markdown("Ou charger un fichier JSON de filtres")
        uploaded = st.file_uploader("Charger un JSON de filtres", type=["json"], key="upload_filters")
        if uploaded is not None:
            try:
                loaded = json.load(uploaded)
                # on remplace les sauvegardes existantes (simple comportement)
                st.session_state["saved_filters"].update(loaded)
                st.success("Filtres chargés dans la session. Utilise la sélection ci-dessous pour appliquer.")
            except Exception as e:
                st.error(f"Impossible de charger le fichier : {e}")

        # sélection d'une sauvegarde existante à appliquer
        if st.session_state["saved_filters"]:
            choix = st.selectbox("Charger une sauvegarde existante", [""] + list(st.session_state["saved_filters"].keys()))
            if choix:
                sel = st.session_state["saved_filters"][choix]
                # appliquer dans session_state (attention aux keys des widgets)
                st.session_state["recherche"] = sel.get("recherche","")
                st.session_state["classe_energie"] = sel.get("classe_energie",[])
                st.session_state["classe_ges"] = sel.get("classe_ges",[])
                st.session_state["surface_range"] = tuple(sel.get("surface_range",(0,500)))
                st.session_state["code_postaux"] = sel.get("code_postaux","")
                st.session_state["choix_zone"] = sel.get("choix_zone","Aucune")
                # lat/lon/rayon seront lus par la suite si présent
                st.experimental_rerun()

# -----------------------------
# Lancer la recherche (bouton principal)
# -----------------------------
col1, col2 = st.columns([1,4])
with col1:
    lancer = st.button("🔎 Lancer la recherche", use_container_width=True, key="btn_search")
with col2:
    st.write("")  # juste espace

if lancer:
    q = st.session_state.get("recherche","").strip()
    if not q:
        st.warning("Saisis un mot-clé (adresse, ville, code postal ou numéro DPE).")
    else:
        with st.spinner("Interrogation de l'API ADEME..."):
            try:
                raw = get_ademe_results(q, size=300)
            except Exception as e:
                st.error(f"Erreur API ADEME : {e}")
                raw = []

        # normalize results to dicts with expected keys
        normalized = []
        for r in raw:
            try:
                # r peut être une liste ou un dict; gérer les deux cas simples
                if isinstance(r, list):
                    # si c'est une liste, skip (imprévisible)
                    continue
                # récupérer champs en tolerant
                adresse = r.get("adresse") or r.get("adresse_complete") or r.get("adresse_logement") or ""
                cp = str(r.get("code_postal","") or "")
                commune = r.get("nom_commune") or r.get("commune") or ""
                lat = safe_float(r.get("latitude") or r.get("lat"))
                lon = safe_float(r.get("longitude") or r.get("lon"))
                dpe = r.get("classe_consommation_energie") or r.get("classe_energie") or None
                ges = r.get("classe_estimation_ges") or r.get("classe_ges") or None
                surface = safe_float(r.get("surface_habitable_logement") or r.get("surface"))
                numero_dpe = r.get("numero_dpe") or r.get("id") or ""
                normalized.append({
                    "adresse": adresse,
                    "code_postal": cp,
                    "commune": commune,
                    "latitude": lat,
                    "longitude": lon,
                    "dpe": dpe,
                    "ges": ges,
                    "surface": surface,
                    "numero_dpe": numero_dpe,
                    "raw": r
                })
            except Exception:
                continue

        st.info(f"{len(normalized)} entrées récupérées (brutes)")

        # --- Appliquer filtres ---
        filtered = normalized

        # DPE
        sel_dpe = st.session_state.get("classe_energie", [])
        if sel_dpe:
            filtered = [f for f in filtered if (f.get("dpe") in sel_dpe)]

        # GES
        sel_ges = st.session_state.get("classe_ges", [])
        if sel_ges:
            filtered = [f for f in filtered if (f.get("ges") in sel_ges)]

        # Surface
        smin, smax = st.session_state.get("surface_range", (0,500))
        filtered = [f for f in filtered if (f.get("surface") is not None and smin <= f["surface"] <= smax)]

        # Codes postaux (nettoyage)
        cp_text = st.session_state.get("code_postaux","") or ""
        cps = [c.strip() for c in cp_text.split(",") if c.strip()]
        if cps:
            filtered = [f for f in filtered if str(f.get("code_postal","")) in cps]

        # Zone géographique
        z = st.session_state.get("choix_zone","Aucune")
        latc = None; lonc = None; rad = None
        if z == "Ville":
            # on a déjà geocodé dans la sidebar mais s'il manque, essayer maintenant
            latc = lat_centre
            lonc = lon_centre
            rad = rayon_km
        elif z == "Coordonnées GPS":
            latc = st.session_state.get("lat_centre") or lat_centre
            lonc = st.session_state.get("lon_centre") or lon_centre
            rad = st.session_state.get("rayon_km_gps") or rayon_km

        if latc is not None and lonc is not None and rad is not None:
            before = len(filtered)
            tmp = []
            for f in filtered:
                latf = f.get("latitude"); lonf = f.get("longitude")
                if latf is None or lonf is None:
                    continue
                try:
                    if distance_km(latc, lonc, float(latf), float(lonf)) <= float(rad):
                        tmp.append(f)
                except Exception:
                    continue
            filtered = tmp
            st.info(f"Après filtrage géographique (rayon {rad} km) : {len(filtered)} résultats (avant {before})")

        # Résultats finaux
        if not filtered:
            st.warning("Aucun résultat après application des filtres.")
        else:
            st.success(f"{len(filtered)} résultat(s) après filtrage.")

            # Carte
            points = [(f["latitude"], f["longitude"], f["adresse"], f["code_postal"], f["commune"], f["dpe"], f["ges"]) 
                      for f in filtered if f["latitude"] is not None and f["longitude"] is not None]
            if points:
                lat_moy = sum(p[0] for p in points) / len(points)
                lon_moy = sum(p[1] for p in points) / len(points)
                m = folium.Map(location=[lat_moy, lon_moy], zoom_start=12)
                for lat, lon, adr, cp, com, dpe, ges in points:
                    popup = f"<b>{adr}</b><br>{cp} {com}<br>DPE: <b>{dpe}</b> | GES: <b>{ges}</b>"
                    folium.Marker([lat, lon], popup=popup, tooltip=adr).add_to(m)
                if latc and lonc and rad:
                    folium.Circle(radius=float(rad)*1000, location=[latc, lonc], color="red", fill=False).add_to(m)
                st.subheader("🗺️ Carte des résultats")
                st_folium(m, width=900, height=500)
            else:
                st.info("Aucune coordonnée disponible pour les résultats filtrés.")

            # Tableau + export CSV
            st.subheader("📋 Résultats (tableau)")
            df = pd.DataFrame([{
                "adresse": f["adresse"],
                "code_postal": f["code_postal"],
                "commune": f["commune"],
                "dpe": f["dpe"],
                "ges": f["ges"],
                "surface": f["surface"],
                "latitude": f["latitude"],
                "longitude": f["longitude"],
                "numero_dpe": f["numero_dpe"]
            } for f in filtered])
            st.dataframe(df, use_container_width=True)

            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Exporter les résultats en CSV", data=csv, file_name="dpe_results.csv", mime="text/csv")
