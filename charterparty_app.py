# charterparty_performance.py
import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO

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
.stTextInput>div>div>input, .stNumberInput>div>div>input { 
    background-color: white; border: 1px solid #3498db; }
.stSelectbox>div>div>select { background-color: white; border: 1px solid #3498db; }
.stDateInput>div>div>input { background-color: white; border: 1px solid #3498db; }
.stButton>button { background: #3498db; color: white; border-radius: 5px; padding: 0.5rem 1rem; }
.stMetric { background: white; border-radius: 10px; padding: 1rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
</style>
""", unsafe_allow_html=True)

def input_configuration():
    st.header("⚓ Charterparty Configuration")
    
    with st.expander("Vessel Details", expanded=True):
        cols = st.columns(3)
        st.session_state.vessel['name'] = cols[0].text_input("Vessel Name")
        st.session_state.vessel['imo'] = cols[1].text_input("IMO Number")
        st.session_state.vessel['grt'] = cols[2].number_input("GRT", min_value=0.0)
    
    with st.expander("Voyage Details"):
        cols = st.columns(2)
        st.session_state.voyage['dep_port'] = cols[0].text_input("Departure Port")
        st.session_state.voyage['arr_port'] = cols[1].text_input("Arrival Port")
        
        cols = st.columns(2)
        st.session_state.voyage['cosp'] = cols[0].datetime_input("COSP (UTC)", value=datetime.utcnow())
        st.session_state.voyage['eosp'] = cols[1].datetime_input("EOSP (UTC)", value=datetime.utcnow())
        
        cols = st.columns(2)
        st.session_state.voyage['dep_lat'] = cols[0].number_input("Departure Latitude", format="%.4f")
        st.session_state.voyage['dep_lon'] = cols[1].number_input("Departure Longitude", format="%.4f")
        st.session_state.voyage['arr_lat'] = cols[0].number_input("Arrival Latitude", format="%.4f")
        st.session_state.voyage['arr_lon'] = cols[1].number_input("Arrival Longitude", format="%.4f")
    
    with st.expander("CP Terms"):
        cols = st.columns(3)
        new_speed = cols[0].number_input("Speed (knots)", min_value=0.0)
        new_me = cols[1].number_input("ME Consumption (MT/day)", min_value=0.0)
        new_ae = cols[2].number_input("AE Consumption (MT/day)", min_value=0.0)
        
        col1, col2 = st.columns([1, 3])
        if col1.button("Add CP Term"):
            st.session_state.cp_terms.append({
                'speed': new_speed,
                'me_consumption': new_me,
                'ae_consumption': new_ae
            })
        if col2.button("Clear CP Terms"):
            st.session_state.cp_terms = []
        
        if st.session_state.cp_terms:
            st.write("Current CP Terms:")
            st.table(pd.DataFrame(st.session_state.cp_terms))
    
    with st.expander("Weather Definition"):
        cols = st.columns(2)
        st.session_state.weather_def['beaufort'] = cols[0].slider("Max Beaufort Scale", 0, 12, 6)
        st.session_state.weather_def['wave_height'] = cols[1].select_slider(
            "Significant Wave Height (m)",
            options=[round(i*0.25, 2) for i in range(0, 21)]
        )
        st.session_state.weather_def['include_current'] = st.checkbox("Include Current Factor")
    
    with st.expander("Excluded Periods"):
        cols = st.columns(3)
        start = cols[0].date_input("Start Date (UTC)")
        start_time = cols[1].time_input("Start Time (UTC)")
        end = cols[2].date_input("End Date (UTC)")
        end_time = cols[3].time_input("End Time (UTC)")
        
        if st.button("Add Exclusion"):
            st.session_state.exclusions.append({
                'start': datetime.combine(start, start_time),
                'end': datetime.combine(end, end_time)
            })
        if st.button("Clear Exclusions"):
            st.session_state.exclusions = []
        
        if st.session_state.exclusions:
            st.write("Current Exclusions:")
            for idx, period in enumerate(st.session_state.exclusions):
                st.write(f"{idx+1}. {period['start']} to {period['end']}")
    
    with st.expander("Data Upload"):
        calc_file = st.file_uploader("Upload Calculation Data (CSV/Excel)", type=['csv', 'xlsx'])
        if calc_file:
            if calc_file.name.endswith('.xlsx'):
                st.session_state.calc_data = pd.read_excel(calc_file)
            else:
                st.session_state.calc_data = pd.read_csv(calc_file)
        
        weather_file = st.file_uploader("Upload Weather Data (CSV/Excel)", type=['csv', 'xlsx'])
        if weather_file:
            if weather_file.name.endswith('.xlsx'):
                st.session_state.weather_data = pd.read_excel(weather_file)
            else:
                st.session_state.weather_data = pd.read_csv(weather_file)

def perform_calculations(df):
    if not st.session_state.cp_terms:
        st.error("No CP Terms defined!")
        return None
        
    cp_term = st.session_state.cp_terms[0]
    warranted_speed = cp_term['speed']
    warranted_consumption = cp_term['me_consumption']
    fuel_tolerance_percent = 5.0  # Default value
    speed_tolerance_knots = 0.5    # Default value

    df = df[df['event_type'].isin(['NOON AT SEA', 'COSP', 'EOSP'])]
    
    numeric_cols = ['distance_travelled_actual', 'steaming_time_hrs', 'me_fuel_consumed']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    total_distance = df['distance_travelled_actual'].sum()
    total_time = df['steaming_time_hrs'].sum()
    total_fuel = df['me_fuel_consumed'].sum()
    voyage_avg_speed = total_distance / total_time if total_time else 0

    good_days = df[df['day_status'] == 'GOOD WEATHER DAY']
    bad_days = df[df['day_status'] == 'BAD WEATHER DAY']

    good_distance = good_days['distance_travelled_actual'].sum()
    good_time = good_days['steaming_time_hrs'].sum()
    good_fuel = good_days['me_fuel_consumed'].sum()
    good_speed = good_distance / good_time if good_time else 0
    good_fo_hr = good_fuel / good_time if good_time else 0
    good_fo_day = good_fo_hr * 24

    bad_distance = bad_days['distance_travelled_actual'].sum()
    bad_time = bad_days['steaming_time_hrs'].sum()
    bad_fuel = bad_days['me_fuel_consumed'].sum()
    bad_speed = bad_distance / bad_time if bad_time else 0

    fuel_tolerance_mt = warranted_consumption * (fuel_tolerance_percent / 100)
    warranted_plus_tol = warranted_consumption + fuel_tolerance_mt
    warranted_minus_tol = warranted_consumption - fuel_tolerance_mt

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
        'good_wx_speed': good_speed,
        'good_wx_fo_cons': good_fuel,
        'good_wx_fo_rate_hr': good_fo_hr,
        'good_wx_fo_rate_day': good_fo_day,
        'bad_wx_distance': bad_distance,
        'bad_wx_time': bad_time,
        'bad_wx_fo_cons': bad_fuel,
        'bad_wx_speed': bad_speed,
        'total_me_fuel': total_fuel,
        'entire_voyage_cons': entire_voyage_good_weather_based,
        'max_warranted_fo': max_warranted_cons,
        'min_warranted_fo': min_warranted_cons,
        'fuel_overconsumption': fuel_overconsumption,
        'fuel_saving': fuel_saving,
        'time_gained': time_gained,
        'time_lost': time_lost
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
                cols[3].metric("Time Difference", 
                    f"Gained: {results['time_gained']:.1f} hrs" if results['time_gained'] > 0 
                    else f"Lost: {results['time_lost']:.1f} hrs")

                st.subheader("Detailed Results")
                st.table(pd.DataFrame(list(results.items()), columns=['Metric', 'Value']))
                
        except Exception as e:
            st.error(f"Calculation error: {str(e)}")
    else:
        st.warning("Please upload calculation data in Configuration page")

def weather_analysis():
    st.header("🌦️ Weather Data Analysis")
    
    if st.session_state.weather_data is not None:
        st.dataframe(
            st.session_state.weather_data.style.format({
                'wind_speed': "{:.1f} m/s",
                'wave_height': "{:.2f} m"
            }),
            use_container_width=True
        )
        
        st.subheader("Weather Statistics")
        cols = st.columns(3)
        cols[0].metric("Max Wind Speed", 
            f"{st.session_state.weather_data['wind_speed'].max():.1f} m/s")
        cols[1].metric("Max Wave Height", 
            f"{st.session_state.weather_data['wave_height'].max():.1f} m")
        cols[2].metric("Bad Weather Days", 
            f"{len(st.session_state.weather_data[st.session_state.weather_data['day_status'] == 'BAD WEATHER DAY'])}")
    else:
        st.warning("Please upload weather data in Configuration page")

def dashboard_page():
    st.header("📊 Performance Dashboard")
    
    if st.session_state.calc_data is not None:
        df = st.session_state.calc_data
        
        st.subheader("Speed Analysis")
        st.line_chart(df[['speed', 'warranted_speed']])
        
        st.subheader("Fuel Consumption")
        st.bar_chart(df['me_fuel_consumed'])
        
        cols = st.columns(2)
        with cols[0]:
            st.subheader("Weather Distribution")
            weather_counts = df['day_status'].value_counts()
            st.bar_chart(weather_counts)
        
        with cols[1]:
            st.subheader("Performance Metrics")
            st.metric("Total Distance", f"{df['distance_travelled_actual'].sum():.1f} nm")
            st.metric("Average Speed", f"{df['speed'].mean():.1f} knots")
    else:
        st.warning("Please upload calculation data in Configuration page")

def create_pdf():
    buffer = BytesIO()
    
    report_content = f"""
    Charterparty Performance Report
    ==============================
    Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
    
    Vessel Information
    ------------------
    Name: {st.session_state.vessel.get('name', 'N/A')}
    IMO: {st.session_state.vessel.get('imo', 'N/A')}
    GRT: {st.session_state.vessel.get('grt', 'N/A')}
    
    Voyage Details
    --------------
    Departure: {st.session_state.voyage.get('dep_port', 'N/A')}
    Arrival: {st.session_state.voyage.get('arr_port', 'N/A')}
    COSP: {st.session_state.voyage.get('cosp', 'N/A')}
    EOSP: {st.session_state.voyage.get('eosp', 'N/A')}
    
    Performance Summary
    -------------------
    """
    
    if st.session_state.calc_data is not None:
        results = perform_calculations(st.session_state.calc_data)
        if results:
            report_content += "\n".join([f"{k}: {v}" for k, v in results.items()])
    
    buffer.write(report_content.encode())
    buffer.seek(0)
    return buffer

def generate_report():
    pdf_buffer = create_pdf()
    st.download_button(
        label="📄 Download PDF Report",
        data=pdf_buffer,
        file_name="performance_report.pdf",
        mime="application/pdf"
    )

pages = {
    "Configuration": input_configuration,
    "Calculations": calculations,
    "Weather Analysis": weather_analysis,
    "Dashboard": dashboard_page
}

st.sidebar.title("Navigation")
selection = st.sidebar.radio("Go to", list(pages.keys()))
pages[selection]()

st.sidebar.divider()
if st.sidebar.button("Generate Report"):
    generate_report()
