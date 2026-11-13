# photo-to-3d

Reference photos → FreeCAD parametric model → print-ready STL and a 360° viewer.
An agent writes the FreeCAD script, and an evaluation loop checks each render against the
photos and asks for fixes until the model matches or the iteration cap is reached.

```
photos ─► LLM writes FreeCAD Part script ─► freecadcmd (headless) ─► STL
            ▲                                                         │
            │  fix list + score                                       ▼
            └──── LLM judge compares 3-view render with photos ◄── render (front/right/top)
                                                                      │ best attempt
                                                                      ▼
                                              trimesh repair + scale ─► print_ready.stl
                                                                      └► decimate → GLB → viewer.html
```

## Setup

1. FreeCAD 1.1 is installed at `C:\Users\mcpag\AppData\Local\Programs\FreeCAD 1.1`. If you move it,
   set `FREECADCMD` to the path of `bin\freecadcmd.exe`.
2. `python -m pip install -r requirements.txt`
3. For the LLM loop: `set ANTHROPIC_API_KEY=...` (get one at console.anthropic.com). Optionally set
   `P23D_MODEL` (default `claude-sonnet-5-5`) and `P23D_JUDGE_MODEL`.

## Usage

```
python -m p23d run photos\ --size 120 --out runs\mug
```

- `photos\` is a folder or a list of files. Name them by view when you can: `front_*.jpg`,
  `right_*.jpg`, `top_*.jpg`. Other photos are used as context only.
- `--size` is the longest side of the print, in mm.
- `--iters` (default 5) caps the loop. `--threshold` (default 85) is the judge score that stops it.

Output in `runs\<name>\`:

| file | what it is |
|---|---|
| `iterNN.py` | the FreeCAD script the agent wrote on that attempt |
| `iterNN.stl` | raw FreeCAD export |
| `iterNN_views.png` | the 3-view render the judge saw |
| `print_ready.stl` | the best attempt, repaired, centred on the bed, scaled to `--size` |
| `viewer\viewer.html` | self-contained 360° viewer (model embedded as base64, works offline apart from the viewer script) |
| `report.json` | every attempt: score, judge notes, inferred regions, FreeCAD errors, print stats |

Test without an API key, using the included gabled-house script:

```
python -m p23d run examples\photos_placeholder.jpg --size 120 --out runs\house --no-llm --script examples\gabled_house.py
```

(Any image path works in `--no-llm` mode; no photos are read.)

## How the loop decides

- **Generator** (`p23d/agent.py`, prompt in `p23d/prompts.py`): sees the photos, then the previous
  judge notes or FreeCAD error log. Must return one `python` block that defines `result`, plus an
  ASSUMPTIONS list naming every hidden or inferred feature.
- **FreeCAD errors** go back to the generator as the log tail. A broken script costs one iteration.
- **Judge** sees the labelled photos, the render and the code, and returns a 0–100 score, the visible
  mismatches, the inferred regions and concrete fix instructions. It is told to judge only what is visible.
- **Best attempt wins.** The model is not always improved by later iterations, so the best-scoring
  attempt is kept, not the last one.

## Known limits

- **The LLM loop is untested against a real model.** `tests/test_agent_loop.py` covers the control flow
  with scripted replies, and the FreeCAD, render, print and viewer stages run for real. Whether
  Claude's scripts and judgments are good enough is something only a real run will show.
- **The judge is only as good as the photos.** One front photo cannot determine depth, and the model
  must guess hidden geometry. The report lists those guesses under `inferred_regions`; treat them as
  guesses.
- **Generated code runs on this machine** through freecadcmd. Use it only on photos and objects you
  are working with.
- **Score is not accuracy.** The judge is a vision model comparing an image with a render. Use it to
  rank attempts, not as a measurement. For a measured result, compare silhouettes against
  reference masks.
- **Scope of geometry:** the prompt asks for a few hundred features in simple parametric shapes. Organic
  forms (faces, hands, fabric) will not come out well.
- **Print checks** are minimal: watertightness, volume sign and bed placement. Check slicer
  output yourself before printing.

## Layout

```
p23d/
  agent.py     the generate / run / render / judge loop
  freecad.py   headless freecadcmd runner (adds the STL export footer)
  render.py    3-view matplotlib render with back-face culling and crease lines
  prepare.py   trimesh repair, centre on bed, scale
  viewer.py    decimate, GLB export, embed in templates/viewer.html
  llm.py       Anthropic client, image blocks, JSON and code-block parsing
  prompts.py   generator, feedback and judge prompts
  cli.py       `python -m p23d run ...`
examples/gabled_house.py   known-good test model
tests/test_agent_loop.py   loop tests with the model replaced by scripted replies
templates/viewer.html      viewer template
```
