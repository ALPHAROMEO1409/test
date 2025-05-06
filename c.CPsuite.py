import streamlit as st
import pandas as pd

# Remove all px references and replace with altair or matplotlib if needed
# Example using native Streamlit charts:

def dashboard_page():
    st.header("📊 Analytics Dashboard")
    if 'calc_data' in st.session_state:
        df = st.session_state.calc_data
        st.line_chart(df[['speed', 'warranted_speed']])
        st.bar_chart(df[['fuel_consumption']])
