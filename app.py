"""Point d'entrée de l'interface multipage AlphaForge."""

import streamlit as st

from ui.home import render_home
from ui.shared import CSS_PATH, THEMES

st.set_page_config(page_title="AlphaForge AI", layout="wide")

with st.sidebar:
    st.markdown("## AlphaForge")
    st.caption("Comprendre avant de décider.")
    theme = st.radio("Thème de l’interface", ["Clair", "Sombre"], index=1, key="app_theme")

try:
    css = CSS_PATH.read_text(encoding="utf-8")
except OSError as exc:
    st.error(f"Impossible de charger la feuille de style : {exc}")
    st.stop()
variables = " ".join(f"--{key}: {value};" for key, value in THEMES[theme].items())
color_scheme = "dark" if theme == "Sombre" else "light"
st.html(f"<style>:root {{ {variables} color-scheme: {color_scheme}; }} {css}</style>")

page = st.navigation(
    [
        st.Page(render_home, title="Accueil", icon=":material/home:", default=True, url_path=""),
        st.Page("ui/simulation.py", title="Simulation", icon=":material/science:", url_path="simulation"),
        st.Page("ui/portfolio_editor.py", title="Éditeur de portefeuille", icon=":material/edit:", url_path="portfolio-editor"),
    ],
    position="sidebar",
)
page.run()
