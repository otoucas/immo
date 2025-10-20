import time, json
import streamlit as st

try:
    from streamlit_cookies_manager import EncryptedCookieManager
except Exception:
    EncryptedCookieManager = None


def auth_gate() -> bool:
    """Formulaire de mot de passe + cookie 30 jours."""
    APP_PASSWORD = st.secrets.get("APP_PASSWORD")  # 🔐 mot de passe par défaut corrigé
    COOKIE_KEY = st.secrets.get("COOKIE_KEY")
    COOKIE_NAME = "dpe_auth_v1"
    MAX_AGE_SEC = 30 * 24 * 3600

    cookies_ok = EncryptedCookieManager is not None
    cookies = None
    if cookies_ok:
        cookies = EncryptedCookieManager(prefix="dpe_app", password=COOKIE_KEY)
        if not cookies.ready:
            st.warning("⏳ Initialisation du gestionnaire de cookies...")
            time.sleep(1)
            st.rerun()

    # Cookie existant ?
    if cookies_ok and cookies:
        raw = cookies.get(COOKIE_NAME)
        if raw:
            try:
                data = json.loads(raw)
                exp = float(data.get("exp", 0))
                if exp > time.time():
                    st.session_state["_auth_ok"] = True
                    return True
            except Exception:
                pass

    # Si déjà connecté
    if st.session_state.get("_auth_ok", False):
        return True

    # Sinon, afficher le formulaire dans un container centré
    with st.container():
        st.markdown("### 🔐 Accès protégé")
        st.write("Veuillez entrer le mot de passe pour accéder à l’outil.")
        with st.form("auth_form", clear_on_submit=False):
            pwd = st.text_input("Mot de passe", type="password")
            remember = st.checkbox("Se souvenir pendant 30 jours", value=True)
            submitted = st.form_submit_button("Entrer")

        if submitted:
            if pwd == APP_PASSWORD:
                if cookies_ok and remember and cookies:
                    payload = {"exp": time.time() + MAX_AGE_SEC}
                    cookies.set(COOKIE_NAME, json.dumps(payload), max_age=MAX_AGE_SEC)
                    cookies.save()
                st.session_state["_auth_ok"] = True
                st.success("Accès autorisé ✅")
                st.rerun()
            else:
                st.error("Mot de passe incorrect.")

    return False
