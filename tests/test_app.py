import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class StreamlitAppTests(unittest.TestCase):
    def test_amira_form_runs_complete_analysis(self):
        app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=60)
        app.run()

        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox[0].value, "Amira")
        self.assertEqual(app.selectbox[1].value, "NVDA")
        self.assertEqual(app.slider[0].value, 10)

        app.button[0].click()
        app.run()

        self.assertFalse(app.exception)
        self.assertTrue(
            any("Simulation historique calculée" in item.value for item in app.success)
        )
        self.assertEqual(len(app.metric), 3)
        self.assertTrue(
            any("Explication locale déterministe" in item.value for item in app.caption)
        )
        self.assertTrue(
            any("Contrôles du profil" in item.value for item in app.markdown)
        )


if __name__ == "__main__":
    unittest.main()
