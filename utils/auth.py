import time, json
import streamlit as st

try:
    from streamlit_cookies_manager import EncryptedCookieManager
except Exception:
    EncryptedCookieManager = None


def auth_gate() -> bool:
    APP_PASSWORD = st.secrets.get("APP_PASSWORD", "demo1234")
    COOKIE_KEY = st.secrets.get("COOKIE_KEY", "change-this-cookie-key")
    COOKIE_NAME = "dpe_auth_v1"
    MAX_AGE_SEC = 30 * 24 * 3600

    cookies_ok = EncryptedCookieManager is not None
    if cookies_ok:
        cookies = EncryptedCookieManager(prefix="dpe_app", password=COOKIE_KEY)
        if not cookies.ready:
            st.stop()
    else:
        cookies = None

    if cookies_ok:
        raw = cookies.get(COOKIE_NAME)
        if raw:
            try:
                data = json.loads(raw)
                exp = float(data.get("exp", 0))
                if exp > time.time():
                    return True
            except Exception:
                pass

    st.markdown("## 🔐 Accès protégé")
    with st.form("auth_form", clear_on_submit=False):
        pwd = st.text_input("Mot de passe", type="password")
        remember = st.checkbox("Se souvenir pendant 30 jours", value=True)
        submitted = st.form_submit_button("Entrer")

    if submitted:
        if pwd == APP_PASSWORD:
            if cookies_ok and remember:
                payload = {"exp": time.time() + MAX_AGE_SEC}
                cookies.set(COOKIE_NAME, json.dumps(payload), max_age=MAX_AGE_SEC)
                cookies.save()
            st.session_state["_auth_ok"] = True
            st.success("Accès autorisé ✅")
            st.rerun()
        else:
            st.error("Mot de passe incorrect.")
    return bool(st.session_state.get("_auth_ok", False))
