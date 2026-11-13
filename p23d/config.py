"""Paths and model settings. Everything can be overridden with environment variables."""
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_DEFAULT_FREECAD = r"C:\Users\mcpag\AppData\Local\Programs\FreeCAD 1.1\bin\freecadcmd.exe"


def freecadcmd_path() -> str:
    env = os.environ.get("FREECADCMD")
    if env:
        return env
    if Path(_DEFAULT_FREECAD).exists():
        return _DEFAULT_FREECAD
    found = shutil.which("freecadcmd") or shutil.which("FreeCADCmd")
    if found:
        return found
    raise RuntimeError("FreeCAD command-line tool not found. Set FREECADCMD to freecadcmd.exe.")


# Vision-capable model used to write the FreeCAD script and to judge renders.
GEN_MODEL = os.environ.get("P23D_MODEL", "claude-sonnet-5-5")
JUDGE_MODEL = os.environ.get("P23D_JUDGE_MODEL", GEN_MODEL)
