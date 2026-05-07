from __future__ import annotations

import os
import re

import streamlit as st
from google import genai
from google.genai import types


def _get_secret_or_env(name: str, default: str | None = None) -> str | None:
    try:
        value = st.secrets.get(name)
        if value:
            return str(value).strip()
    except Exception:
        pass

    value = os.getenv(name, default)
    return str(value).strip() if value else None


def _normalize_vertex_location(location: str) -> str:
    """Vertex AI Gemini uses regions like asia-south1, not zones like asia-south1-a."""
    if re.fullmatch(r"[a-z]+-[a-z]+[0-9]-[a-z]", location):
        return location.rsplit("-", 1)[0]
    return location


def generate_text(prompt: str, system_instruction: str | None = None) -> str:
    project = _get_secret_or_env("GOOGLE_CLOUD_PROJECT")
    location = _normalize_vertex_location(_get_secret_or_env("GOOGLE_CLOUD_LOCATION", "asia-south1") or "asia-south1")
    model_name = _get_secret_or_env("GEMINI_MODEL", "gemini-1.5-flash")

    if not project:
        raise ValueError(
            "Missing GOOGLE_CLOUD_PROJECT. Add it to .streamlit/secrets.toml "
            "or set it as an environment variable."
        )

    try:
        client = genai.Client(
            vertexai=True,
            project=project,
            location=location,
        )

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.3,
        )

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )

        text = getattr(response, "text", None)
        if not text:
            return "Gemini returned no text. Please try again or check the model/config."

        return text.strip()

    except Exception as exc:
        message = str(exc)
        if "DefaultCredentialsError" in message or "credentials" in message.lower():
            raise RuntimeError(
                "Vertex AI authentication failed. For local development, install the "
                "Google Cloud CLI if `gcloud` is not recognized, then run: "
                "gcloud auth application-default login. Also confirm your Google Cloud "
                "project has Vertex AI API enabled."
            ) from exc

        if "404" in message and "model" in message.lower():
            raise RuntimeError(
                "Vertex AI could not find or access the selected Gemini model. "
                "Set GEMINI_MODEL to a current Vertex AI model such as "
                "`gemini-2.5-flash`, and use a valid region such as `us-central1` "
                "or `asia-south1`. Do not use a zone like `asia-south1-a`."
            ) from exc

        raise RuntimeError(f"Vertex AI Gemini generation failed: {exc}") from exc
