"""AEGIS Decision Intelligence Platform — Streamlit Cloud Entry Point."""

import importlib
import runpy
import subprocess
import sys
import traceback
from pathlib import Path

# Ensure 'src' is at the front of sys.path across all platforms (Linux/macOS/Windows)
_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
if str(_SRC) in sys.path:
    sys.path.remove(str(_SRC))
sys.path.insert(0, str(_SRC))


def _get_code_signature() -> str:
    """Compute a fast signature of current git commit and UI/GenAI source mtimes."""
    commit = "unknown"
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(_ROOT),
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            commit = res.stdout.strip()
    except Exception:
        pass
    mtimes: list[str] = []
    for sub in ("ui", "genai", "explainability"):
        folder = _SRC / "aegis" / sub
        if folder.exists():
            for p in sorted(folder.glob("*.py")):
                try:
                    mtimes.append(f"{p.name}:{p.stat().st_mtime_ns}")
                except OSError:
                    pass
    return f"{commit}|{'|'.join(mtimes)}"


_CURRENT_SIG = _get_code_signature()
if getattr(sys, "_aegis_code_sig", None) != _CURRENT_SIG:
    importlib.invalidate_caches()
    for _mod_name in list(sys.modules.keys()):
        if (
            _mod_name
            in (
                "aegis.ui.components",
                "aegis.ui.plots",
                "aegis.ui.theme",
                "aegis.explainability.decision_explainer",
            )
            or _mod_name == "aegis.genai"
            or _mod_name.startswith("aegis.genai.")
        ):
            sys.modules.pop(_mod_name, None)
    sys._aegis_code_sig = _CURRENT_SIG  # type: ignore[attr-defined]

try:
    # Execute the UI decision workspace on every Streamlit rerun
    app_script = _SRC / "aegis" / "ui" / "app.py"
    runpy.run_path(str(app_script), run_name="__main__")
except Exception as exc:
    import streamlit as st

    st.error(f"### Startup Initialization Diagnostic\n\n```text\n{traceback.format_exc()}\n```")
    st.exception(exc)
