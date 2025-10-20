import time, json
import streamlit as st

try:
    from streamlit_cookies_manager import EncryptedCookieManager
except Exception:
    EncryptedCookieManager = None


def auth_gate() -> bool:
    """
    Affiche un écran d'accueil demandant un mot de passe.
    Si "Se souvenir 30 jours" est coché, stocke un cookie chiffré côté navigateur.
    Retourne True si l'accès est autorisé, sinon False.
    """

    APP_PASSWORD = st.secrets.get("APP_PASSWORD", "demo1234")
    COOKIE_KEY = st.secrets.get("COOKIE_KEY", "change-this-cookie-key")
    COOKIE_NAME = "dpe_auth_v1"
    MAX_AGE_SEC = 30 * 24 * 3600  # 30 jours

    cookies_ok = EncryptedCookieManager is not None
    cookies = None

    if cookies_ok:
        cookies = EncryptedCookieManager(prefix="dpe_app", password=COOKIE_KEY)
        # Attente explicite jusqu’à ce que les cookies soient prêts
        if not cookies.ready:
            st.warning("⏳ Initialisation du gestionnaire de cookies... Veuillez patienter une seconde.")
            time.sleep(1)
            st.rerun()

    # Vérifie si un cookie d'accès est déjà présent
    if cookies_ok and cookies:
        raw = cookies.get(COOKIE_NAME)
        if raw:
            try:
                data = json.loads(raw)
                exp = float(data.get("exp", 0))
                if exp > time.time():
                    return True  # accès déjà autorisé
            except Exception:
                pass  # cookie invalide, on continue

    # --- Formulaire de mot de passe ---
    st.markdown("## 🔐 Accès protégé")
    st.write("Cet outil nécessite un mot de passe pour continuer.")
    with st.form("auth_form", clear_on_submit=False):
        pwd = st.text_input("Mot de passe", type="password")
        remember = st.checkbox("Se souvenir pendant 30 jours", value=True)
        submitted = st.form_submit_button("Entrer")

    if submitted:
        if pwd == APP_PASSWORD:
            # Création du cookie si demandé
            if cookies_ok and remember and cookies:
                payload = {"exp": time.time() + MAX_AGE_SEC}
                cookies.set(COOKIE_NAME, json.dumps(payload), max_age=MAX_AGE_SEC)
                cookies.save()
            st.session_state["_auth_ok"] = True
            st.success("Accès autorisé ✅")
            st.rerun()
        else:
            st.error("Mot de passe incorrect.")

    return bool(st.session_state.get("_auth_ok", False))
