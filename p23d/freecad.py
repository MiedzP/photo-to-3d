"""Run a generated FreeCAD Part script headless and export an STL.

The generated code must assign a Part.Shape to a variable named `result`
(units: mm, Z up). This module adds the export footer and runs freecadcmd.
Generated code is executed on this machine: only feed it inputs you trust.
"""
import subprocess
import tempfile
from pathlib import Path

from .config import freecadcmd_path

HEADER = "import FreeCAD, Part\n"

FOOTER = '''
_shape = result
_shape.exportStl(r"{out}")
print("P23D_OK volume=%.3f bbox=%s" % (_shape.Volume, _shape.BoundBox))
'''


def run_freecad(body: str, out_stl: Path, timeout: int = 300) -> tuple[bool, str]:
    """Return (ok, log). On success `out_stl` exists and the log contains P23D_OK."""
    out_stl = Path(out_stl).resolve()
    out_stl.parent.mkdir(parents=True, exist_ok=True)
    if out_stl.exists():
        out_stl.unlink()

    work = Path(tempfile.mkdtemp(prefix="p23d_"))
    script = work / "model.py"
    script.write_text(HEADER + body + FOOTER.format(out=str(out_stl)), encoding="utf-8")

    try:
        proc = subprocess.run(
            [freecadcmd_path(), str(script)],
            capture_output=True, text=True, timeout=timeout, cwd=str(work),
        )
    except subprocess.TimeoutExpired:
        return False, f"FreeCAD timed out after {timeout}s"

    log = (proc.stdout or "") + (proc.stderr or "")
    ok = out_stl.exists() and "P23D_OK" in log
    return ok, log
