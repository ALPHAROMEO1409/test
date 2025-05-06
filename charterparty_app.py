import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from io import BytesIO
import base64

# Initialize session state
if 'vessel' not in st.session_state:
    st.session_state.vessel = {}
if 'voyage' not in st.session_state:
    st.session_state.voyage = {}
if 'cp_terms' not in st.session_state:
    st.session_state.cp_terms = []
if 'weather_def' not in st.session_state:
    st.session_state.weather_def = {}
if 'exclusions' not in st.session_state:
    st.session_state.exclusions = []
if 'calc_data' not in st.session_state:
    st.session_state.calc_data = None
if 'weather_data' not in st.session_state:
    st.session_state.weather_data = None

# Custom CSS styling
st.markdown("""
<style>
.stApp { background: #f0f2f6; color: #2c3e50; }
.stSidebar .sidebar-content { background: #2c3e50; color: white; }
.stTextInput>div>div>input, .stNumberInput>div>div>input { background-color: white; border: 1px solid #3498db; }
.stSelectbox>div>div>select { background-color: white; border: 1px solid #3498db; }
.stDateInput>div>div>input { background-color: white; border: 1px solid #3498db; }
.stButton>button { background: #3498db; color: white; border-radius: 5px; padding: 0.5rem 1rem; }
.stMetric { background: white; border-radius: 10px; padding: 1rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
</style>
""", unsafe_allow_html=True)

def input_configuration():
    st.header("⚓ Charterparty Configuration")
    # [Previous input configuration code remains the same]
    # ... (include all the input fields from previous implementation)

def perform_calculations(df):
    # Get CP parameters from first term
    if not st.session_state.cp_terms:
        st.error("No CP Terms defined!")
        return None
        
    cp_term = st.session_state.cp_terms[0]
    warranted_speed = cp_term['speed']
    warranted_consumption = cp_term['me_consumption']
    fuel_tolerance_percent = st.session_state.cp_params.get('fuel_tolerance', 5.0)
    speed_tolerance_knots = st.session_state.cp_params.get('speed_tolerance', 0.5)

    # Filter relevant rows
    df = df[df['event_type'].isin(['NOON AT SEA', 'COSP', 'EOSP'])]
    
    # Convert numeric columns
    numeric_cols = ['distance_travelled_actual', 'steaming_time_hrs', 'me_fuel_consumed']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Calculate total metrics
    total_distance = df['distance_travelled_actual'].sum()
    total_time = df['steaming_time_hrs'].sum()
    total_fuel = df['me_fuel_consumed'].sum()
    voyage_avg_speed = total_distance / total_time if total_time else 0

    # Weather segmentation
    good_days = df[df['day_status'] == 'GOOD WEATHER DAY']
    bad_days = df[df['day_status'] == 'BAD WEATHER DAY']

    # Good weather calculations
    good_distance = good_days['distance_travelled_actual'].sum()
    good_time = good_days['steaming_time_hrs'].sum()
    good_fuel = good_days['me_fuel_consumed'].sum()
    good_speed = good_distance / good_time if good_time else 0
    good_fo_hr = good_fuel / good_time if good_time else 0
    good_fo_day = good_fo_hr * 24

    # Bad weather calculations
    bad_distance = bad_days['distance_travelled_actual'].sum()
    bad_time = bad_days['steaming_time_hrs'].sum()
    bad_fuel = bad_days['me_fuel_consumed'].sum()
    bad_speed = bad_distance / bad_time if bad_time else 0

    # Warranted calculations
    fuel_tolerance_mt = warranted_consumption * (fuel_tolerance_percent / 100)
    warranted_plus_tol = warranted_consumption + fuel_tolerance_mt
    warranted_minus_tol = warranted_consumption - fuel_tolerance_mt

    # Complex warranted conditions
    speed_condition = (
        warranted_speed - speed_tolerance_knots 
        if good_speed < warranted_speed - speed_tolerance_knots 
        else warranted_speed + speed_tolerance_knots 
        if good_speed > warranted_speed + speed_tolerance_knots 
        else good_speed
    )

    entire_voyage_good_weather_based = (total_distance / good_speed) * (good_fo_day / 24) if good_speed else 0
    max_warranted_cons = (total_distance / speed_condition) * (warranted_plus_tol / 24)
    min_warranted_cons = (total_distance / speed_condition) * (warranted_minus_tol / 24)

    fuel_overconsumption = max(entire_voyage_good_weather_based - max_warranted_cons, 0)
    fuel_saving = max(min_warranted_cons - entire_voyage_good_weather_based, 0)

    # Time calculations
    time_at_good_spd = total_distance / speed_condition
    max_time = total_distance / (warranted_speed - speed_tolerance_knots)
    min_time = total_distance / (warranted_speed + speed_tolerance_knots)
    time_gained = max(min_time - time_at_good_spd, 0)
    time_lost = max(time_at_good_spd - max_time, 0)

    return {
        'total_distance': total_distance,
        'total_steaming_time': total_time,
        'voyage_avg_speed': voyage_avg_speed,
        'good_wx_distance': good_distance,
        'good_wx_time': good_time,
        # ... include all other metrics from your calculation code
    }

def calculations():
    st.header("📈 Performance Calculations")
    
    if st.session_state.calc_data is not None:
        try:
            results = perform_calculations(st.session_state.calc_data)
            
            if results:
                cols = st.columns(4)
                cols[0].metric("Total Distance", f"{results['total_distance']:.1f} nm")
                cols[1].metric("Avg Speed", f"{results['voyage_avg_speed']:.1f} knots")
                cols[2].metric("Total Fuel", f"{results['total_me_fuel']:.1f} MT")
                cols[3].metric("Time Difference", f"{results['time_gained']:.1f} hrs gained")

                st.subheader("Detailed Results")
                st.table(pd.DataFrame(list(results.items()), columns=['Metric', 'Value']))
                
        except Exception as e:
            st.error(f"Calculation error: {str(e)}")
    else:
        st.warning("Please upload calculation data in Page 1")

# [Rest of the code for other pages remains similar]
# ... (include weather_analysis, dashboard_page, and main app controller)

pages = {
    "Configuration": input_configuration,
    "Calculations": calculations,
    "Weather Analysis": weather_analysis,
    "Dashboard": dashboard_page
}

st.sidebar.title("Navigation")
selection = st.sidebar.radio("Go to", list(pages.keys()))
pages[selection]()
