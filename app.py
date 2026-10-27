"""AEGIS Decision Intelligence Platform — Streamlit Cloud Entry Point."""

import sys
import traceback
from pathlib import Path

# Ensure 'src' is on sys.path across all platforms (Linux/macOS/Windows)
_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

try:
    # Import and execute the UI decision workspace
    import aegis.ui.app  # noqa: E402, F401
except Exception as exc:
    import streamlit as st

    st.error(f"### Startup Initialization Diagnostic\n\n```text\n{traceback.format_exc()}\n```")
    st.exception(exc)
