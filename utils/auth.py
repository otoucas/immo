# utils/auth.py
import streamlit as st
import time
import json
from streamlit_cookies_manager import EncryptedCookieManager

COOKIE_NAME = "session_dpe_auth"
COOKIE_KEY = st.secrets.get("COOKIE_KEY", "secret-cookie-key")
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "demo1234")


def auth_gate():
    """Écran d'authentification avec cookie de persistance (30 jours)."""
    cookies = EncryptedCookieManager(prefix=COOKIE_NAME, password=COOKIE_KEY)
    cookies_ready = False

    # 🔹 Tente d'initialiser le cookie manager
    try:
        if cookies.ready():
            cookies_ready = True
    except Exception:
        st.info("🔄 Initialisation des cookies...")
        time.sleep(0.5)
        st.rerun()

    # 🔹 Vérifie si une session existe déjà
    if cookies_ready:
        try:
            raw = cookies.get(COOKIE_NAME)
            if raw:
                data = json.loads(raw)
                if data.get("authenticated") is True:
                    return True
        except Exception:
            pass

    # 🔹 Sinon, demande le mot de passe
    st.title("🔐 Accès à la carte DPE / DVF")
    st.markdown("Veuillez entrer le mot de passe pour accéder à l'application.")
    pwd = st.text_input("Mot de passe", type="password")

    if st.button("Se connecter"):
        if pwd == APP_PASSWORD:
            # Stocke l'authentification dans un cookie valable 30 jours
            cookies.set(COOKIE_NAME, json.dumps({"authenticated": True}), expires_at="30d")
            cookies.save()
            st.success("Connexion réussie ✅")
            st.rerun()
        else:
            st.error("Mot de passe incorrect.")

    st.stop()
