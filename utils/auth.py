# utils/auth.py
import streamlit as st
import json
import time
from streamlit_cookies_manager import EncryptedCookieManager

COOKIE_NAME = "session_dpe_auth"
COOKIE_KEY = st.secrets.get("COOKIE_KEY", "secret-cookie-key")
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "demo1234")


def auth_gate():
    """
    Écran d'authentification sécurisé avec cookie de session de 30 jours.
    Empêche les erreurs CookiesNotReady sur Streamlit Cloud.
    """
    cookies = EncryptedCookieManager(prefix=COOKIE_NAME, password=COOKIE_KEY)

    # --- Attente de l'initialisation du gestionnaire de cookies ---
    if not cookies.ready():
        st.info("🔄 Initialisation du gestionnaire de session...")
        time.sleep(0.5)
        st.stop()  # on arrête ce run, Streamlit relancera la page automatiquement

    # --- Vérifie si un cookie valide existe ---
    try:
        raw = cookies.get(COOKIE_NAME)
        if raw:
            data = json.loads(raw)
            if data.get("authenticated") is True:
                return True
    except Exception:
        pass

    # --- Interface de connexion ---
    st.title("🔐 Accès sécurisé à la carte DPE / DVF")
    st.markdown("Veuillez entrer le mot de passe pour accéder à l'application.")

    pwd = st.text_input("Mot de passe", type="password")
    remember = st.checkbox("Se souvenir pendant 30 jours")

    if st.button("Se connecter"):
        if pwd == APP_PASSWORD:
            if remember:
                cookies.set(COOKIE_NAME, json.dumps({"authenticated": True}), expires_at="30d")
                cookies.save()
            st.success("Connexion réussie ✅")
            st.rerun()
        else:
            st.error("Mot de passe incorrect.")

    st.stop()
