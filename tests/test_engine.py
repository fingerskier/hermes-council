"""Engine unit tests — no live LLM required (stub seat path)."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = "hermes_council_under_test"


def _ensure_package() -> types.ModuleType:
    """Load the plugin directory as a real package so relative imports work."""
    if PKG in sys.modules and hasattr(sys.modules[PKG], "engine"):
        return sys.modules[PKG]

    # Namespace parent
    init = ROOT / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        PKG,
        init,
        submodule_search_locations=[str(ROOT)],
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = PKG
    mod.__path__ = [str(ROOT)]  # type: ignore[attr-defined]
    sys.modules[PKG] = mod
    spec.loader.exec_module(mod)
    return mod


import importlib.util  # noqa: E402


class CouncilEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pkg = _ensure_package()
        cls.convene_mod = importlib.import_module(f"{PKG}.engine.convene")
        cls.info_mod = importlib.import_module(f"{PKG}.engine.info")
        cls.session_mod = importlib.import_module(f"{PKG}.engine.session")
        cls.records_mod = importlib.import_module(f"{PKG}.engine.records")
        cls.tools_mod = importlib.import_module(f"{PKG}.tools")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_list_templates(self):
        tpls = self.convene_mod.list_templates()
        names = {t["name"] for t in tpls}
        self.assertIn("software-team", names)
        self.assertIn("c-suite", names)

    def test_convene_and_info(self):
        result = self.convene_mod.convene(self.root, "software-team")
        self.assertTrue(result["ok"], result)
        self.assertTrue((self.root / ".council" / "council.yaml").exists())
        self.assertTrue(
            (self.root / ".council" / "seats" / "staff-engineer.md").exists()
        )
        again = self.convene_mod.convene(self.root, "software-team", force=False)
        self.assertFalse(again["ok"])
        self.assertEqual(again["error"], "council_exists")

        info = self.info_mod.council_info(self.root)
        self.assertTrue(info["ok"])
        self.assertEqual(info["chair"], "staff-engineer")
        self.assertIn("staff-engineer", info["table"])

        # seats frontmatter parsed
        seat_text = (
            self.root / ".council" / "seats" / "security-engineer.md"
        ).read_text(encoding="utf-8")
        self.assertIn("name: security-engineer", seat_text)

    def test_meeting_flow_stub(self):
        self.convene_mod.convene(self.root, "software-team")
        start = self.session_mod.meeting_start(
            self.root, "Should we adopt a job queue?"
        )
        self.assertTrue(start["ok"], start)
        sid = start["session_id"]

        rnd = self.session_mod.meeting_round(self.root, sid, ctx=None)
        self.assertTrue(rnd["ok"], rnd)
        self.assertEqual(len(rnd["round_contributions"]), 4)

        rnd2 = self.session_mod.meeting_round(
            self.root, sid, ctx=None, user_steer="Focus on operational risk."
        )
        self.assertTrue(rnd2["ok"], rnd2)

        done = self.session_mod.conclude_meeting(self.root, sid, ctx=None)
        self.assertTrue(done["ok"], done)
        rec = Path(done["record"])
        self.assertTrue(rec.exists())
        text = rec.read_text(encoding="utf-8")
        problems = self.records_mod.validate_record_text(text)
        self.assertEqual(problems, [], problems)
        self.assertTrue(rec.with_suffix(".scratch.md").exists())

    def test_work_requires_git(self):
        self.convene_mod.convene(self.root, "solo-founder")
        result = self.session_mod.work_start(self.root, "add a README note")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "worktree")

    def test_work_flow_stub(self):
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=self.root,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=self.root,
            check=True,
            capture_output=True,
        )
        (self.root / "README.md").write_text("hi\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "."], cwd=self.root, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=self.root,
            check=True,
            capture_output=True,
        )

        self.convene_mod.convene(self.root, "software-team")
        start = self.session_mod.work_start(self.root, "document the retry helper")
        self.assertTrue(start["ok"], start)
        sid = start["session_id"]
        self.assertTrue(Path(start["worktree"]["path"]).exists())

        tick = self.session_mod.work_tick(self.root, sid, ctx=None)
        self.assertTrue(tick["ok"], tick)

        stop = self.session_mod.work_stop(
            self.root, sid, ctx=None, reason="user_stop"
        )
        self.assertTrue(stop["ok"], stop)
        self.assertIn("merge_commands", stop)
        self.assertTrue(Path(stop["record"]).exists())

    def test_tool_dispatch(self):
        out = json.loads(self.tools_mod.handle_council({"action": "list_templates"}))
        self.assertTrue(out["ok"])
        self.assertTrue(out["templates"])

        out = json.loads(
            self.tools_mod.handle_council(
                {
                    "action": "convene",
                    "template": "writing-lab",
                    "root": str(self.root),
                }
            )
        )
        self.assertTrue(out["ok"], out)

        out = json.loads(
            self.tools_mod.handle_council(
                {"action": "info", "root": str(self.root)}
            )
        )
        self.assertTrue(out["ok"])
        self.assertIn("writing-lab", out.get("table", "") + out.get("council", ""))


if __name__ == "__main__":
    unittest.main()
