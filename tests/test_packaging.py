"""#25 packaging: installable project + console script (feat-scoped only)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class PackagingTests(unittest.TestCase):
    def test_console_script_target_importable(self):
        from ai_marketing_agent.cli import main  # noqa
        self.assertTrue(callable(main))

    def test_pyproject_declares_script(self):
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("[project]", text)
        self.assertIn('ai-marketing-agent = "ai_marketing_agent.cli:main"', text)
        self.assertIn('where = ["src"]', text)

    def test_package_importable_without_path_hack(self):
        import subprocess
        env = {k: v for k, v in __import__("os").environ.items() if k != "PYTHONPATH"}
        r = subprocess.run([sys.executable, "-c", "import ai_marketing_agent; print(ai_marketing_agent.__name__)"],
                           capture_output=True, text=True, cwd=str(ROOT), env=env)
        self.assertEqual(r.returncode, 0, r.stderr[-500:])
        self.assertIn("ai_marketing_agent", r.stdout)

    def test_console_script_runs(self):
        import os
        import shutil
        import subprocess
        import sysconfig
        exe = shutil.which("ai-marketing-agent")
        if exe is None:
            import site
            candidates = {sysconfig.get_path("scripts"),
                          str(Path(sys.executable).parent / "Scripts"),
                          str(Path(site.getusersitepackages()).parent / "Scripts")}
            for d in candidates:
                cand = Path(d) / ("ai-marketing-agent.exe" if os.name == "nt" else "ai-marketing-agent")
                if cand.exists():
                    exe = str(cand)
                    break
        self.assertIsNotNone(exe, "console script not installed (pip install -e .)")
        r = subprocess.run([exe, "--help"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr[-500:])
        self.assertIn("domain", r.stdout)


if __name__ == "__main__":
    unittest.main()
