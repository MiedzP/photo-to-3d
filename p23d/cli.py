import argparse
import sys
from pathlib import Path

from .agent import run_agent

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def _expand(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            out += sorted(f for f in p.iterdir() if f.suffix.lower() in IMAGE_EXT)
        else:
            out.append(p)
    if not out:
        sys.exit("no reference images found")
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="p23d", description="reference photos -> print-ready 3D model")
    sub = ap.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="build a model from reference photos")
    run.add_argument("refs", nargs="+", help="image files or a folder (name them front_*, right_*, top_*)")
    run.add_argument("--size", type=float, required=True, help="longest side of the print, in mm")
    run.add_argument("--out", type=Path, required=True, help="output folder")
    run.add_argument("--iters", type=int, default=5)
    run.add_argument("--threshold", type=int, default=85, help="judge score that ends the loop")
    run.add_argument("--script", type=Path, help="use this FreeCAD script for the first attempt")
    run.add_argument("--no-llm", action="store_true", help="skip the LLM (needs --script)")

    args = ap.parse_args(argv)
    if args.cmd == "run":
        if args.no_llm and not args.script:
            sys.exit("--no-llm needs --script")
        script = args.script.read_text(encoding="utf-8") if args.script else None
        report = run_agent(
            refs=_expand(args.refs),
            longest_side_mm=args.size,
            out=args.out,
            max_iters=args.iters,
            threshold=args.threshold,
            use_llm=not args.no_llm,
            script=script,
        )
        print(f"result: {report['result']}  (report: {args.out / 'report.json'})")


if __name__ == "__main__":
    main()
