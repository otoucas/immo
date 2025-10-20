import sys, os
sys.path.append(os.path.dirname(__file__))

import streamlit as st
from utils.auth import auth_gate
from ui.main_interface import render_main_interface

st.set_page_config(page_title="Carte DPE / DVF", layout="wide")

if not auth_gate():
    st.stop()

render_main_interface()
