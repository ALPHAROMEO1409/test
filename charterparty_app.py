import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime

# App setup
st.set_page_config(page_title="Charter Party Performance", layout="wide", initial_sidebar_state="expanded")

# Session state initialization
if "cp_data" not in st.session_state: st.session_state.cp_data = {}
if "calc_file" not in st.session_state: st.session_state.calc_file = None
if "weather_file" not in st.session_state: st.session_state.weather_file = None
if "results" not in st.session_state: st.session_state.results = {}

# Sidebar navigation
page = st.sidebar.radio("Navigation", ["1. Input Form", "2. CP Calculation", "3. Weather Data", "4. Dashboard & Report"])

st.markdown(
    """
    <style>
    .stApp {
        background-color: #2f4f4f;
    }
    h1, h2, h3 {
        color: #003366;
    }
    .css-1v0mbdj p {
        color: #003366;
    }
    </style>
    """, unsafe_allow_html=True
)

if page == "1. Input Form":
    st.title("Page 1: Vessel / Voyage / CP Terms / Weather Definition")

    st.subheader("A. Vessel Details")
    vessel_name = st.text_input("Vessel Name")
    imo_no = st.text_input("IMO Number")
    grt = st.text_input("Gross Register Tonnage (GRT)")

    st.subheader("B. Voyage Details")
    dep_port = st.text_input("Departure Port")
    arr_port = st.text_input("Arrival Port")
    cosp_date = st.date_input("COSP Date (UTC)")
    cosp_time = st.time_input("COSP Time (UTC)")
    eosp_date = st.date_input("EOSP Date (UTC)")
    eosp_time = st.time_input("EOSP Time (UTC)")

    dep_lat = st.number_input("Departure Latitude", format="%.6f")
    dep_lon = st.number_input("Departure Longitude", format="%.6f")
    arr_lat = st.number_input("Arrival Latitude", format="%.6f")
    arr_lon = st.number_input("Arrival Longitude", format="%.6f")

    st.subheader("C. CP Terms - Speed & Consumption")
    cp_terms = st.data_editor(
    pd.DataFrame(columns=["Speed (kn)", "ME Cons (MT/day)", "AE Cons (MT/day)"]),
    num_rows="dynamic",
    use_container_width=True,
    key="cp_terms"
    )

    st.subheader("D. Weather Definition (CP)")
    beaufort_limit = st.selectbox("Max Beaufort Scale (Good Weather)", list(range(0, 13)))
    wave_height = st.number_input("Max Significant Wave Height (m)", format="%.2f")
    include_current = st.checkbox("Include Current Factor in Analysis", value=True)
    
    excluded_periods = st.data_editor(
    pd.DataFrame(columns=["From (UTC)", "To (UTC)"]),
    num_rows="dynamic",
    use_container_width=True,
    key="excluded_periods"
    )

    st.subheader("F. Additional Comments")
    comments = st.text_area("Any comments")

    st.subheader("G. Upload Calculation Data")
    calc_file = st.file_uploader("Upload CP Calculation Data (.csv or .xlsx)", type=["csv", "xlsx"])

    st.subheader("H. Upload Weather Data")
    weather_file = st.file_uploader("Upload Weather Data (.csv or .xlsx)", type=["csv", "xlsx"])

    if st.button("Save & Proceed"):
        st.session_state.cp_data = {
            "vessel": {"name": vessel_name, "imo": imo_no, "grt": grt},
            "voyage": {
                "dep_port": dep_port, "arr_port": arr_port,
      

                "dep_coords": (dep_lat, dep_lon),
                "arr_coords": (arr_lat, arr_lon)
            },
            "cp_terms": cp_terms.to_dict(),
            "weather_def": {
                "beaufort": beaufort_limit,
                "wave_height": wave_height,
                "include_current": include_current
            },
            "excluded_periods": excluded_periods.to_dict(),
            "comments": comments,
        }
        st.session_state.calc_file = calc_file
        st.session_state.weather_file = weather_file
        st.success("Data saved successfully! Navigate to Page 2 for CP Calculations.")

elif page == "2. CP Calculation":
    st.title("Page 2: CP Performance Calculation")

    if st.session_state.calc_file:
        if st.session_state.calc_file.name.endswith(".csv"):
            df = pd.read_csv(st.session_state.calc_file)
        else:
            df = pd.read_excel(st.session_state.calc_file)
        
        st.subheader("Uploaded Calculation Data")
        st.dataframe(df)

        st.subheader("Processing Results")

       
# =========================
# Load Data
# =========================
df = pd.read_excel("/content/sample_data/cp SAMPLE DATA for  .xlsx")  # Replace with actual filename

# Filter relevant rows: NOON AT SEA, COSP, and EOSP
df = df[df['event_type'].isin(['NOON AT SEA', 'COSP', 'EOSP'])]

# Ensure numeric types for calculations
df['distance_travelled_actual'] = pd.to_numeric(df['distance_travelled_actual'], errors='coerce')
df['steaming_time_hrs'] = pd.to_numeric(df['steaming_time_hrs'], errors='coerce')
df['me_fuel_consumed'] = pd.to_numeric(df['me_fuel_consumed'], errors='coerce')

# =========================
# Total Metrics
# =========================
total_distance = df['distance_travelled_actual'].sum()
total_time = df['steaming_time_hrs'].sum()
total_fuel = df['me_fuel_consumed'].sum()
voyage_avg_speed = total_distance / total_time if total_time else 0

# =========================
# Good and Bad Weather Segmentation
# =========================
good_days = df[df['day_status'] == 'GOOD WEATHER DAY']
bad_days = df[df['day_status'] == 'BAD WEATHER DAY']

# Good Weather Metrics
good_distance = good_days['distance_travelled_actual'].sum()
good_time = good_days['steaming_time_hrs'].sum()
good_fuel = good_days['me_fuel_consumed'].sum()
good_speed = good_distance / good_time if good_time else 0
good_fo_hr = good_fuel / good_time if good_time else 0
good_fo_day = good_fo_hr * 24

# Bad Weather Metrics
bad_distance = bad_days['distance_travelled_actual'].sum()
bad_time = bad_days['steaming_time_hrs'].sum()
bad_fuel = bad_days['me_fuel_consumed'].sum()
bad_speed = bad_distance / bad_time if bad_time else 0

# =========================
# Warranted Calculations
# =========================
fuel_tolerance_mt = warranted_consumption * (fuel_tolerance_percent / 100)
warranted_plus_tol = warranted_consumption + fuel_tolerance_mt
warranted_minus_tol = warranted_consumption - fuel_tolerance_mt

# Entire Voyage Consumption Using Good Weather Consumption (c)
entire_voyage_good_weather_based = (total_distance / good_speed) * (good_fo_day / 24) if good_speed else 0

# Maximum and Minimum Warranted Fuel
max_warranted_cons = (total_distance / (good_speed if good_speed<warranted_speed+speed_tolerance_knots and good_speed>warranted_speed-speed_tolerance_knots else warranted_speed+speed_tolerance_knots if good_speed>warranted_speed+speed_tolerance_knots else warranted_speed-speed_tolerance_knots )) * (warranted_plus_tol / 24)
min_warranted_cons = (total_distance / (good_speed if good_speed<warranted_speed+speed_tolerance_knots and good_speed>warranted_speed-speed_tolerance_knots else warranted_speed+speed_tolerance_knots if good_speed>warranted_speed+speed_tolerance_knots else warranted_speed-speed_tolerance_knots)) * (warranted_minus_tol / 24)

# Overconsumption and Saving (based on good weather based consumption)
fuel_overconsumption = (entire_voyage_good_weather_based - max_warranted_cons)if entire_voyage_good_weather_based>max_warranted_cons else 0
fuel_saving = (entire_voyage_good_weather_based - min_warranted_cons)if entire_voyage_good_weather_based<min_warranted_cons else 0

# Time Estimates for reference
time_at_good_spd = total_distance / (good_speed if good_speed<warranted_speed+speed_tolerance_knots and good_speed>warranted_speed-speed_tolerance_knots else warranted_speed+speed_tolerance_knots if good_speed>warranted_speed+speed_tolerance_knots else warranted_speed-speed_tolerance_knots)
max_time = total_distance / (warranted_speed - speed_tolerance_knots)
min_time = total_distance / (warranted_speed + speed_tolerance_knots)
time_gained = (min_time - time_at_good_spd)if time_at_good_spd<min_time else 0
time_lost = (time_at_good_spd - max_time)if time_at_good_spd>max_time else 0
import streamlit as st

results = {
    "Total Distance (nm)": 0,
    "Total Steaming Time (hrs)": 0,
    "Voyage Avg Speed (knots)": 0,
    "Good Wx Distance (nm)": 0,
    "Good Wx Time (hrs)": 0,
    "Good Wx Speed (knots)": 0,
    "Good Wx FO Cons (MT)": 0,
    "Good Wx FO Rate (MT/hr)": 0,
    "Good Wx FO Rate (MT/day)": 0,
    "Bad Wx Distance (nm)": 0,
    "Bad Wx Time (hrs)": 0,
    "Bad Wx FO Cons (MT)": 0,
    "Bad Wx Speed (knots)": 0,
    "Total ME Fuel (MT)": 0,
    "Entire Voyage Cons (MT) via Good Wx Perf": 0,
    "Max Warranted FO (MT)": 0,
    "Min Warranted FO (MT)": 0,
    "Fuel Overconsumption (MT)": 0,
    "Fuel Saving (MT)": 0,
    "Time @ Good Wx Speed (hrs)": 0,
    "Max Time @ Warranted Spd (hrs)": 0,
    "Min Time @ Warranted Spd (hrs)": 0,
    "Time Gained (hrs)": 0,
    "Time Lost (hrs)": 0}

else:
        st.warning("Please upload calculation data on Page 1.")

elif page == "3. Weather Data":
    st.title("Page 3: Weather Data Analysis")

    if st.session_state.weather_file:
        if st.session_state.weather_file.name.endswith(".csv"):
            weather_df = pd.read_csv(st.session_state.weather_file)
        else:
            weather_df = pd.read_excel(st.session_state.weather_file)

        st.dataframe(weather_df)
    else:
        st.warning("Please upload weather data on Page 1.")

elif page == "4. Dashboard & Report":
    st.title("Page 4: Dashboard & PDF Report Generation")

    st.subheader("Summary Dashboard")
    col1, col2 = st.columns(2)
    with col1:
        st.write("### Vessel Info")
        for k, v in st.session_state.cp_data.get("vessel", {}).items():
            st.write(f"{k}: **{v}**")
    with col2:
        st.write("### Voyage Summary")
        for k, v in st.session_state.cp_data.get("voyage", {}).items():
            st.write(f"{k}: **{v}**")

    st.write("### Performance Metrics")
    for key, value in st.session_state.results.items():
        st.write(f"- {key}: **{value}**")

    if st.button("Generate PDF Report"):
        import base64
        import tempfile
        from fpdf import FPDF

        class PDF(FPDF):
            def header(self):
                self.set_font("Arial", "B", 12)
                self.cell(0, 10, "Charter Party Performance Report", ln=True, align="C")

            def chapter_title(self, title):
                self.set_font("Arial", "B", 12)
                self.cell(0, 10, title, ln=True, align="L")

            def chapter_body(self, text):
                self.set_font("Arial", "", 10)
                self.multi_cell(0, 10, text)

        pdf = PDF()
        pdf.add_page()
        pdf.chapter_title("Vessel and Voyage Details")
        vessel_data = st.session_state.cp_data.get("vessel", {})
        voyage_data = st.session_state.cp_data.get("voyage", {})
        cp_result = st.session_state.results

        summary = "\n".join([f"{k}: {v}" for k, v in {**vessel_data, **voyage_data, **cp_result}.items()])
        pdf.chapter_body(summary)

        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        pdf.output(tmp_file.name)

        with open(tmp_file.name, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
            href = f'<a href="data:application/pdf;base64,{b64}" download="cp_report.pdf">Download Report</a>'
            st.markdown(href, unsafe_allow_html=True)

