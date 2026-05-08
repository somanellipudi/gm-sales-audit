from __future__ import annotations

import base64
import hmac
import os
from pathlib import Path

import streamlit as st


APP_DIR = Path(__file__).resolve().parent
LOGO_PATH = APP_DIR / "assets" / "growingmonk_logo.png"


def _get_secret(name: str) -> str:
    try:
        value = st.secrets[name]
    except (FileNotFoundError, KeyError):
        value = os.getenv(name, "")
    return str(value).strip()


def _asset_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _render_login_header() -> None:
    logo_uri = _asset_data_uri(LOGO_PATH)
    logo_html = f'<img src="{logo_uri}" alt="GrowingMonk" />' if logo_uri else "<strong>GrowingMonk</strong>"
    st.markdown(
        f"""
        <section class="gm-hero gm-login">
            <div>
                <div class="gm-kicker">Internal growth audit system</div>
                <h1>MonkAudit</h1>
                <p>Sign in to prepare prospect audits, sales diligence, and client-safe delivery packs.</p>
            </div>
            <div class="gm-hero-panel">{logo_html}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def require_login() -> None:
    """Simple password gate for internal v1 access."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    expected_password = _get_secret("APP_PASSWORD")
    if not expected_password:
        st.error("APP_PASSWORD is missing from Streamlit secrets or environment variables.")
        st.info(
            "For local setup, copy `.streamlit/secrets.example.toml` to "
            "`.streamlit/secrets.toml` and set APP_PASSWORD. For Cloud Run, set "
            "APP_PASSWORD as an environment variable."
        )
        st.stop()

    if st.session_state.authenticated:
        with st.sidebar:
            if st.button("Logout"):
                st.session_state.authenticated = False
                st.rerun()
        return

    _render_login_header()
    password = st.text_input("Password", type="password")

    if not password:
        st.stop()

    if hmac.compare_digest(password, expected_password):
        st.session_state.authenticated = True
        st.rerun()

    st.error("Incorrect password.")
    st.stop()
