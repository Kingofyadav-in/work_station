from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT_DIR  = Path(__file__).resolve().parents[2]
JARVIS_DIR = ROOT_DIR / "Jarvis"
if str(JARVIS_DIR) not in sys.path:
    sys.path.insert(0, str(JARVIS_DIR))

import ai_connector  # noqa: E402

_STATUS_COLOR = {
    "ready":        "#3a9e62",
    "unconfigured": "#cc8830",
    "unavailable":  "#e05555",
    "unknown":      "#8095b0",
}

_PROVIDER_ORDER = ["ollama", "openai", "anthropic"]
_PROVIDER_LABELS = {
    "openai":    "OpenAI",
    "anthropic": "Claude (Anthropic)",
    "ollama":    "Ollama (Local)",
}


def render_model_selector() -> None:
    st.sidebar.divider()
    st.sidebar.markdown("### AI Model")

    cfg              = ai_connector.get_model_config()
    current_provider = cfg.get("provider", "openai")
    current_model    = cfg.get("model", "")

    # Sync session_state to config file when file changes externally so the
    # selectbox doesn't overwrite an intentional external config change.
    if st.session_state.get("_ms_provider") != current_provider:
        st.session_state["_ms_provider"] = current_provider
    if st.session_state.get("_ms_model") != current_model:
        st.session_state["_ms_model"] = current_model

    labels   = [_PROVIDER_LABELS[p] for p in _PROVIDER_ORDER]
    p_index  = _PROVIDER_ORDER.index(current_provider) if current_provider in _PROVIDER_ORDER else 0

    selected_label    = st.sidebar.selectbox("Provider", labels, index=p_index, key="_ms_provider")
    selected_provider = _PROVIDER_ORDER[labels.index(selected_label)]

    # Model list: Ollama reads live from running instance
    if selected_provider == "ollama":
        models = ai_connector.sort_ollama_models(ai_connector.get_ollama_models())
        if not models:
            st.sidebar.caption("Local runtime not ready — start with `ollama serve`")
            models = [current_model] if (current_provider == "ollama" and current_model) else ["llama3:latest"]
        elif current_provider == "ollama" and current_model and current_model not in models:
            models = [current_model] + [m for m in models if m != current_model]
    else:
        models = ai_connector.PROVIDERS[selected_provider]["models"]

    m_index        = models.index(current_model) if current_model in models else 0
    selected_model = st.sidebar.selectbox("Model", models, index=m_index, key="_ms_model")

    # Only persist when the user actively changed provider or model
    if selected_provider != current_provider or selected_model != current_model:
        ai_connector.set_model_config(selected_provider, selected_model)

    # Live status indicator
    status = ai_connector.provider_status(selected_provider)
    s      = status["status"]
    color  = _STATUS_COLOR.get(s, "#8095b0")
    st.sidebar.markdown(
        f'<div style="font-size:0.78rem;color:{color};font-weight:600;padding:0.2rem 0;">'
        f"● {status['message']}"
        "</div>",
        unsafe_allow_html=True,
    )

    if s == "unconfigured":
        env_key = ai_connector.PROVIDERS.get(selected_provider, {}).get("env_key") or ""
        if env_key:
            st.sidebar.caption(f"Add `{env_key}=your-key` to `.env` and restart.")

    if s == "unavailable" and selected_provider == "ollama":
        st.sidebar.caption("Install: https://ollama.com  then run `ollama pull llama3.2:3b`")
