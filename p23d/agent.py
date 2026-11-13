"""Photo(s) -> FreeCAD model, with a generate / run / render / judge loop.

Each iteration:
  1. the generator (vision LLM) writes a FreeCAD Part script from the reference photos,
     or from the previous judge's feedback;
  2. freecadcmd runs it headless and exports an STL (errors go back to the generator);
  3. the STL is rendered to front/right/top views;
  4. the judge compares those renders with the reference photos and returns a 0-100 score
     plus concrete fixes;
  5. the loop stops at the threshold or the iteration cap; the best-scoring model is kept.
The best model is then repaired and scaled for print, and exported as a 360° viewer.
"""
import json
from pathlib import Path
from typing import Callable

import trimesh

from .config import GEN_MODEL, JUDGE_MODEL
from .freecad import run_freecad
from .llm import ask, extract_json, extract_python, image_block
from .prepare import prepare_for_print
from .prompts import (
    FREECAD_ERROR_FEEDBACK,
    GENERATOR_FEEDBACK,
    GENERATOR_SYSTEM,
    JUDGE_SYSTEM,
)
from .render import render_views
from .viewer import export_viewer

Log = Callable[[str], None]


def _label(path: Path) -> str:
    stem = path.stem.lower()
    if stem.startswith(("front", "right", "top")):
        return f"Reference photo, view = {stem.split('_')[0]} ({path.name}):"
    return f"Reference photo, other angle, context only ({path.name}):"


def _ref_blocks(refs: list[Path]) -> list[dict]:
    blocks: list[dict] = []
    for ref in refs:
        blocks += image_block(ref, _label(ref))
    return blocks


def _judge(refs: list[Path], render_png: Path, code: str) -> dict:
    content = _ref_blocks(refs)
    content += image_block(render_png, "Three-view render of the model (front, right, top):")
    content.append({"type": "text", "text": "FreeCAD code:\n```python\n" + code + "\n```"})
    reply = ask([{"role": "user", "content": content}], JUDGE_SYSTEM, JUDGE_MODEL, max_tokens=2000)
    return extract_json(reply)


def run_agent(
    refs: list[Path],
    longest_side_mm: float,
    out: Path,
    max_iters: int = 5,
    threshold: int = 85,
    use_llm: bool = True,
    script: str | None = None,
    log: Log = print,
) -> dict:
    """Run the loop. `script` replaces the first generation (useful for testing the pipeline)."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    refs = [Path(r) for r in refs]
    messages: list[dict] = []
    attempts: list[dict] = []
    best: dict | None = None

    if use_llm:
        messages.append({
            "role": "user",
            "content": _ref_blocks(refs) + [{
                "type": "text",
                "text": f"Build the model. Its longest side should be about {longest_side_mm:g} mm.",
            }],
        })

    for i in range(max_iters):
        tag = f"iter{i:02d}"
        att: dict = {"iteration": i}
        attempts.append(att)

        if script is not None and i == 0:
            code, att["assumptions"] = script, "(supplied script)"
        elif not use_llm:
            break
        else:
            reply = ask(messages, GENERATOR_SYSTEM, GEN_MODEL)
            messages.append({"role": "assistant", "content": reply})
            att["generator_reply"] = reply
            try:
                code, rest = extract_python(reply)
                att["assumptions"] = rest
            except ValueError as err:
                att["error"] = str(err)
                messages.append({"role": "user", "content": f"{err}. Reply again in the required format."})
                log(f"[{tag}] no code block; asking again")
                continue

        (out / f"{tag}.py").write_text(code, encoding="utf-8")
        ok, freecad_log = run_freecad(code, out / f"{tag}.stl")
        att["ok"] = ok
        if not ok:
            att["error"] = freecad_log[-1500:]
            log(f"[{tag}] FreeCAD failed")
            if use_llm:
                messages.append({"role": "user", "content": FREECAD_ERROR_FEEDBACK.format(log=att["error"])})
            continue

        mesh = trimesh.load(str(out / f"{tag}.stl"), force="mesh")
        att["faces"] = int(len(mesh.faces))
        att["extents_raw"] = [round(float(v), 2) for v in mesh.extents]
        render_png = render_views(out / f"{tag}.stl", out / f"{tag}_views.png")

        if use_llm:
            try:
                judge = _judge(refs, render_png, code)
            except ValueError as err:  # judge reply was not valid JSON
                judge = {"score": 0, "visible_mismatches": [f"judge reply unparseable: {err}"],
                         "fix_instructions": "Keep the model simple and recheck proportions."}
            att["judge"] = judge
            att["score"] = int(judge.get("score", 0))
            log(f"[{tag}] judge score {att['score']}/100")
        else:
            att["score"] = None
            log(f"[{tag}] built ({att['faces']} faces); no LLM judge")

        if best is None or (att["score"] or 0) >= (best["score"] or 0):
            best = att

        if not use_llm or att["score"] >= threshold:
            break

        j = att["judge"]
        instructions = "\n".join(
            [f"- {m}" for m in j.get("visible_mismatches", [])] + [j.get("fix_instructions", "")]
        )
        messages.append({
            "role": "user",
            "content": GENERATOR_FEEDBACK.format(score=att["score"], instructions=instructions),
        })

    report: dict = {"attempts": attempts, "best_iteration": None, "result": "failed"}
    if best is None or not best.get("ok"):
        log("no successful model; see report.json")
        (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

    report["best_iteration"] = best["iteration"]
    raw = out / f"iter{best['iteration']:02d}.stl"
    print_stl = out / "print_ready.stl"
    report["print"] = prepare_for_print(raw, print_stl, longest_side_mm=longest_side_mm)
    report["viewer"] = export_viewer(print_stl, out / "viewer", title=out.name)
    report["result"] = "ok" if (use_llm is False or best["score"] >= threshold) else "below_threshold"
    report["final_score"] = best["score"]
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"done: best = iter{best['iteration']:02d}, result = {report['result']}")
    return report
