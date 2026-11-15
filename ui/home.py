"""Page d'accueil AlphaForge."""

import streamlit as st


def render_home() -> None:
    st.caption("Simulation fictive · aucune transaction réelle.")
    st.title("Comprendre avant de décider.")
    st.write("Explorez un portefeuille fictif et comparez l’effet d’un ajout.")
    if st.button("Commencer une simulation", type="primary"):
        st.switch_page("ui/simulation.py")

    columns = st.columns(3)
    messages = (
        ("1. Choisir un profil", "Partez d’une situation fictive clairement décrite."),
        ("2. Tester un ajout", "Choisissez un actif et la place qu’il prendrait."),
        ("3. Comprendre", "Comparez les résultats, les compromis et les limites."),
    )
    for column, (title, text) in zip(columns, messages):
        with column.container(border=True):
            st.subheader(title)
            st.write(text)
    st.info("Simulation pédagogique uniquement : aucune transaction réelle ni recommandation.")
