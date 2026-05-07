from __future__ import annotations

import hmac
import os

import streamlit as st


def _get_secret(name: str) -> str:
    try:
        value = st.secrets[name]
    except (FileNotFoundError, KeyError):
        value = os.getenv(name, "")
    return str(value).strip()


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

    st.title("MonkAudit | GrowingMonk")
    st.caption("Internal prospect audit assistant")
    password = st.text_input("Password", type="password")

    if not password:
        st.stop()

    if hmac.compare_digest(password, expected_password):
        st.session_state.authenticated = True
        st.rerun()

    st.error("Incorrect password.")
    st.stop()
