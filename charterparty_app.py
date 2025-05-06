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
    with st.form("dms_coordinates_form"):
    st.markdown("## Enter Coordinates in DMS Format")

    st.markdown("### Departure Latitude & Longitude")
    col1, col2 = st.columns(2)

    with col1:
        dep_lat_deg = st.number_input("Dep Lat Degrees (°)", min_value=0, max_value=90, step=1)
        dep_lat_min = st.number_input("Dep Lat Minutes (')", min_value=0, max_value=59, step=1)
        dep_lat_sec = st.number_input("Dep Lat Seconds (\")", min_value=0.0, max_value=59.999, step=0.1)
        dep_lat_dir = st.selectbox("Dep Lat Direction", options=["N", "S"])

    with col2:
        dep_lon_deg = st.number_input("Dep Lon Degrees (°)", min_value=0, max_value=180, step=1)
        dep_lon_min = st.number_input("Dep Lon Minutes (')", min_value=0, max_value=59, step=1)
        dep_lon_sec = st.number_input("Dep Lon Seconds (\")", min_value=0.0, max_value=59.999, step=0.1)
        dep_lon_dir = st.selectbox("Dep Lon Direction", options=["E", "W"])

    st.markdown("### Arrival Latitude & Longitude")
    col3, col4 = st.columns(2)

    with col3:
        arr_lat_deg = st.number_input("Arr Lat Degrees (°)", min_value=0, max_value=90, step=1)
        arr_lat_min = st.number_input("Arr Lat Minutes (')", min_value=0, max_value=59, step=1)
        arr_lat_sec = st.number_input("Arr Lat Seconds (\")", min_value=0.0, max_value=59.999, step=0.1)
        arr_lat_dir = st.selectbox("Arr Lat Direction", options=["N", "S"])

    with col4:
        arr_lon_deg = st.number_input("Arr Lon Degrees (°)", min_value=0, max_value=180, step=1)
        arr_lon_min = st.number_input("Arr Lon Minutes (')", min_value=0, max_value=59, step=1)
        arr_lon_sec = st.number_input("Arr Lon Seconds (\")", min_value=0.0, max_value=59.999, step=0.1)
        arr_lon_dir = st.selectbox("Arr Lon Direction", options=["E", "W"])

    submitted = st.form_submit_button("Convert to Decimal Degrees")

if submitted:
    # Conversion logic
    dep_lat = dep_lat_deg + dep_lat_min / 60 + dep_lat_sec / 3600
    if dep_lat_dir == "S":
        dep_lat *= -1

    dep_lon = dep_lon_deg + dep_lon_min / 60 + dep_lon_sec / 3600
    if dep_lon_dir == "W":
        dep_lon *= -1

    arr_lat = arr_lat_deg + arr_lat_min / 60 + arr_lat_sec / 3600
    if arr_lat_dir == "S":
        arr_lat *= -1

    arr_lon = arr_lon_deg + arr_lon_min / 60 + arr_lon_sec / 3600
    if arr_lon_dir == "W":
        arr_lon *= -1

    st.success("Converted Decimal Coordinates:")
    st.write(f"**Departure Latitude:** {dep_lat:.6f}")
    st.write(f"**Departure Longitude:** {dep_lon:.6f}")
    st.write(f"**Arrival Latitude:** {arr_lat:.6f}")
    st.write(f"**Arrival Longitude:** {arr_lon:.6f}")

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

        # Placeholder for your actual Python logic
        # >>> Replace the below with real CP performance calculations <<<
        results = {
            "Total Distance (nm)": 1234,
            "Total Steaming Time (hrs)": 120.5,
            "Voyage Avg Speed (knots)": 10.2,
            "Good Wx Distance (nm)": 1020,
            "Fuel Overconsumption (MT)": 5.6,
            "Time Gained (hrs)": 1.8,
            "Time Lost (hrs)": 3.2
        }

        st.session_state.results = results
        for key, value in results.items():
            st.metric(label=key, value=value)
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

