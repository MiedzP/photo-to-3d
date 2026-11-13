"""Control-flow tests for the agent loop with the LLM replaced by scripted replies.

Run:  python -m unittest discover -s tests -v
(The FreeCAD and render steps are real; only the model calls are faked.)
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from p23d import agent
from p23d.llm import extract_json, extract_python

ROOT = Path(__file__).resolve().parent.parent
HOUSE = (ROOT / "examples" / "gabled_house.py").read_text(encoding="utf-8")

BROKEN = "result = this_name_does_not_exist\n"

WRONG_ROOF = HOUSE.replace("RIDGE = 30.0", "RIDGE = 5.0")   # valid, but the judge says the roof is too flat


def reply(code: str, assumptions: str = "- roof pitch inferred") -> str:
    return f"Here is the model.\n```python\n{code}```\nASSUMPTIONS:\n{assumptions}\n"


class ParsingTests(unittest.TestCase):
    def test_extract_python_returns_code_and_rest(self):
        code, rest = extract_python(reply("result = 1\n", "- none"))
        self.assertEqual(code, "result = 1\n")
        self.assertIn("ASSUMPTIONS", rest)

    def test_extract_python_requires_block(self):
        with self.assertRaises(ValueError):
            extract_python("no code here")

    def test_extract_json_tolerates_fences(self):
        self.assertEqual(extract_json('```json\n{"score": 70}\n```'), {"score": 70})
        self.assertEqual(extract_json('Sure: {"score": 12} thanks'), {"score": 12})


class AgentLoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="p23d_test_"))
        self.refs = []
        for name in ("front_01.jpg", "right_01.jpg"):
            p = self.tmp / name
            Image.new("RGB", (64, 48), (200, 200, 200)).save(p)
            self.refs.append(p)

    def test_error_then_low_score_then_pass(self):
        replies = iter([reply(BROKEN), reply(WRONG_ROOF), reply(HOUSE)])
        judgments = iter([{"score": 60, "visible_mismatches": ["roof too flat"],
                           "fix_instructions": "raise the ridge"},
                          {"score": 92, "visible_mismatches": [], "fix_instructions": "",
                           "inferred_regions": ["back wall"]}])
        sent_messages = []

        def fake_ask(messages, system, model, max_tokens=8000):
            sent_messages.append(len(messages))
            return next(replies)

        with mock.patch.object(agent, "ask", side_effect=fake_ask), \
             mock.patch.object(agent, "_judge", side_effect=lambda *a, **k: next(judgments)):
            report = agent.run_agent(
                refs=self.refs, longest_side_mm=120, out=self.tmp / "run",
                max_iters=5, threshold=85, use_llm=True, log=lambda *_: None,
            )

        self.assertEqual(report["result"], "ok")
        self.assertEqual(report["best_iteration"], 2)
        self.assertEqual(report["final_score"], 92)

        attempts = report["attempts"]
        self.assertFalse(attempts[0]["ok"])                    # NameError in FreeCAD
        self.assertIn("this_name_does_not_exist", attempts[0]["error"])
        self.assertEqual(attempts[1]["score"], 60)
        self.assertEqual(attempts[2]["score"], 92)

        # The generator saw the error and then the judge's feedback, so its context grew each call.
        self.assertEqual(sent_messages, sorted(sent_messages))
        self.assertGreater(sent_messages[-1], sent_messages[0])

        # Outputs for the best model exist and are print-ready.
        self.assertTrue((self.tmp / "run" / "print_ready.stl").exists())
        self.assertTrue((self.tmp / "run" / "viewer" / "viewer.html").exists())
        self.assertTrue(report["print"]["watertight"])
        self.assertEqual(report["print"]["extents_mm"], [120.0, 96.0, 108.0])

    def test_no_llm_with_script_builds_once(self):
        with mock.patch.object(agent, "ask") as fake_ask:
            report = agent.run_agent(
                refs=self.refs, longest_side_mm=100, out=self.tmp / "nollm",
                use_llm=False, script=HOUSE, log=lambda *_: None,
            )
        fake_ask.assert_not_called()
        self.assertEqual(report["result"], "ok")
        self.assertEqual(len(report["attempts"]), 1)

    def test_gives_up_after_max_iterations(self):
        with mock.patch.object(agent, "ask", return_value=reply(BROKEN)):
            report = agent.run_agent(
                refs=self.refs, longest_side_mm=100, out=self.tmp / "fail",
                max_iters=2, use_llm=True, log=lambda *_: None,
            )
        self.assertEqual(report["result"], "failed")
        self.assertEqual(len(report["attempts"]), 2)


if __name__ == "__main__":
    unittest.main()
