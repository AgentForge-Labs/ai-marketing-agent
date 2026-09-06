"""#28 UI inventory guard: *.html may only live in dashboard/ or mouse_dojo/."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_PARENTS = (ROOT / "dashboard", ROOT / "services" / "biometric-mouse" / "mouse_dojo")
SKIP_PARTS = {".git", "__pycache__", ".pytest_cache", "node_modules", ".venv", "venv"}


class UiInventoryTests(unittest.TestCase):
    def test_html_confined_to_known_surfaces(self):
        stray = []
        for path in ROOT.rglob("*.html"):
            if any(part in SKIP_PARTS for part in path.parts):
                continue
            if not any(allowed in path.parents for allowed in ALLOWED_PARENTS):
                stray.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(stray, [], f"unexpected UI surface(s): {stray}")

    def test_known_surfaces_present(self):
        self.assertTrue((ROOT / "dashboard" / "index.html").exists())
        self.assertTrue((ROOT / "dashboard" / "app.js").exists())
        self.assertTrue((ROOT / "services" / "biometric-mouse" / "mouse_dojo" / "index.html").exists())

    def test_dojo_marked_vendored(self):
        readme = (ROOT / "services" / "biometric-mouse" / "README.md").read_text(encoding="utf-8")
        self.assertIn("rün UI", readme)  # "ürün UI'ı değildir" banner (encoding-safe slice)
        self.assertIn("mouse_dojo", readme)


if __name__ == "__main__":
    unittest.main()
