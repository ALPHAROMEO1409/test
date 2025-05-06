import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import datetime
import base64
from io import BytesIO
import math
import pytz
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import tempfile

# Set page config
st.set_page_config(
    page_title="Charter Party Performance Calculator",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state variables if they don't exist
if 'vessel_details' not in st.session_state:
    st.session_state.vessel_details = {
        'vessel_name': '',
        'imo_no': '',
        'grt': ''
    }

if 'voyage_details' not in st.session_state:
    st.session_state.voyage_details = {
        'dep_port': '',
        'arr_port': '',
        'cosp_date': None,
        'cosp_time': None,
        'eosp_date': None,
        'eosp_time': None,
        'dep_lat': '',
        'dep_long': '',
        'arr_lat': '',
        'arr_long': ''
    }

if 'cp_terms' not in st.session_state:
    st.session_state.cp_terms = []

if 'weather_definition' not in st.session_state:
    st.session_state.weather_definition = {
        'beaufort_scale': 5,
        'wave_height': 2.5,
        'include_current': False
    }

if 'excluded_periods' not in st.session_state:
    st.session_state.excluded_periods = []

if 'comments' not in st.session_state:
    st.session_state.comments = ''

if 'calc_data' not in st.session_state:
    st.session_state.calc_data = None

if 'weather_data' not in st.session_state:
    st.session_state.weather_data = None

if 'calculation_results' not in st.session_state:
    st.session_state.calculation_results = {}

# Function to convert datetime to UTC
def to_utc(date, time):
    if date and time:
        dt = datetime.datetime.combine(date, time)
        return dt.replace(tzinfo=pytz.UTC)
    return None

# Function to calculate distance between two lat/long points using Haversine formula
def calculate_distance(lat1, lon1, lat2, lon2):
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 3440  # Radius of Earth in nautical miles
    return c * r

# Function to process calculation data based on the provided Python code
def process_calculation_data(df, cp_terms, weather_def, excluded_periods):
    # Make a copy of the dataframe to avoid modifying the original
    df_processed = df.copy()
    
    # Handle column naming variations
    # Map common column name patterns
    column_mapping = {
        'distance': ['distance', 'distance_travelled', 'distance_travelled_actual', 'distance_nm'],
        'time_hrs': ['steaming_time_hrs', 'time_hrs', 'hours', 'steaming_hours'],
        'me_fuel': ['me_fuel_consumed', 'me_fuel', 'fuel_consumed', 'fuel_consumption'],
        'weather_status': ['day_status', 'weather_status', 'weather_condition'],
        'event_type': ['event_type', 'event']
    }
    
    # Find actual column names in the dataframe
    column_dict = {}
    for target, possibilities in column_mapping.items():
        for col in possibilities:
            if col in df_processed.columns:
                column_dict[target] = col
                break
    
    # Extract warranted values from CP terms
    if cp_terms:
        # Get the first CP term for simplicity (can be enhanced to select the most appropriate)
        selected_cp = cp_terms[0]
        warranted_speed = float(selected_cp['speed'])
        warranted_consumption = float(selected_cp['me_consumption'])
    else:
        # Default values
        warranted_speed = 13.0
        warranted_consumption = 20.0
    
    # Apply fuel and speed tolerances
    fuel_tolerance_percent = 5.0  # %
    speed_tolerance_knots = 0.5  # knots
    
    # Filter relevant rows if event_type exists
    if 'event_type' in column_dict and column_dict['event_type'] in df_processed.columns:
        df_processed = df_processed[df_processed[column_dict['event_type']].isin(['NOON AT SEA', 'COSP', 'EOSP'])]
    
    # Mark excluded periods if datetime column exists
    if 'datetime' in df_processed.columns:
        if not pd.api.types.is_datetime64_any_dtype(df_processed['datetime']):
            df_processed['datetime'] = pd.to_datetime(df_processed['datetime'])
        
        df_processed['excluded'] = False
        for period in excluded_periods:
            start = period['from']
            end = period['to']
            if start and end:
                mask = (df_processed['datetime'] >= start) & (df_processed['datetime'] <= end)
                df_processed.loc[mask, 'excluded'] = True
        
        df_processed = df_processed[~df_processed['excluded']]
    
    # Ensure numeric types for calculations
    for target, col in column_dict.items():
        if col in df_processed.columns:
            df_processed[col] = pd.to_numeric(df_processed[col], errors='coerce')
    
    # Calculate total metrics
    distance_col = column_dict.get('distance', None)
    time_col = column_dict.get('time_hrs', None)
    fuel_col = column_dict.get('me_fuel', None)
    
    total_distance = df_processed[distance_col].sum() if distance_col and distance_col in df_processed.columns else 0
    total_time = df_processed[time_col].sum() if time_col and time_col in df_processed.columns else 0
    total_fuel = df_processed[fuel_col].sum() if fuel_col and fuel_col in df_processed.columns else 0
    voyage_avg_speed = total_distance / total_time if total_time > 0 else 0
    
    # Good and Bad Weather segmentation
    weather_col = column_dict.get('weather_status', None)
    
    if weather_col and weather_col in df_processed.columns:
        # Use existing weather status
        good_days = df_processed[df_processed[weather_col] == 'GOOD WEATHER DAY']
        bad_days = df_processed[df_processed[weather_col] == 'BAD WEATHER DAY']
    else:
        # Use wind and wave data to determine weather
        df_processed['good_weather'] = True
        
        if 'wind_force' in df_processed.columns and 'wave_height' in df_processed.columns:
            mask = (df_processed['wind_force'] > weather_def['beaufort_scale']) | \
                   (df_processed['wave_height'] > weather_def['wave_height'])
            df_processed.loc[mask, 'good_weather'] = False
        
        # If current factor is included, also check current
        if weather_def['include_current'] and 'current' in df_processed.columns:
            mask = df_processed['current'] > 1.0
            df_processed.loc[mask, 'good_weather'] = False
        
        good_days = df_processed[df_processed['good_weather']]
        bad_days = df_processed[~df_processed['good_weather']]
    
    # Good Weather Metrics
    good_distance = good_days[distance_col].sum() if distance_col and distance_col in good_days.columns else 0
    good_time = good_days[time_col].sum() if time_col and time_col in good_days.columns else 0
    good_fuel = good_days[fuel_col].sum() if fuel_col and fuel_col in good_days.columns else 0
    good_speed = good_distance / good_time if good_time > 0 else 0
    good_fo_hr = good_fuel / good_time if good_time > 0 else 0
    good_fo_day = good_fo_hr * 24
    
    # Bad Weather Metrics
    bad_distance = bad_days[distance_col].sum() if distance_col and distance_col in bad_days.columns else 0
    bad_time = bad_days[time_col].sum() if time_col and time_col in bad_days.columns else 0
    bad_fuel = bad_days[fuel_col].sum() if fuel_col and fuel_col in bad_days.columns else 0
    bad_speed = bad_distance / bad_time if bad_time > 0 else 0
    
    # Warranted Calculations
    fuel_tolerance_mt = warranted_consumption * (fuel_tolerance_percent / 100)
    warranted_plus_tol = warranted_consumption + fuel_tolerance_mt
    warranted_minus_tol = warranted_consumption - fuel_tolerance_mt
    
    # Determine the effective speed for calculations
    if good_speed < warranted_speed + speed_tolerance_knots and good_speed > warranted_speed - speed_tolerance_knots:
        effective_speed = good_speed
    elif good_speed > warranted_speed + speed_tolerance_knots:
        effective_speed = warranted_speed + speed_tolerance_knots
    else:
        effective_speed = warranted_speed - speed_tolerance_knots
    
    # Entire Voyage Consumption Using Good Weather Consumption
    entire_voyage_cons = (total_distance / good_speed) * (good_fo_day / 24) if good_speed > 0 else 0
    
    # Maximum and Minimum Warranted Fuel
    max_warranted_fo = (total_distance / effective_speed) * (warranted_plus_tol / 24)
    min_warranted_fo = (total_distance / effective_speed) * (warranted_minus_tol / 24)
    
    # Overconsumption and Saving
    fuel_overconsumption = max(0, entire_voyage_cons - max_warranted_fo)
    fuel_saving = max(0, min_warranted_fo - entire_voyage_cons)
    
    # Time Estimates
    time_at_good_wx_speed = total_distance / effective_speed
    max_time_at_warranted_spd = total_distance / (warranted_speed - speed_tolerance_knots)
    min_time_at_warranted_spd = total_distance / (warranted_speed + speed_tolerance_knots)
    
    time_gained = max(0, min_time_at_warranted_spd - time_at_good_wx_speed)
    time_lost = max(0, time_at_good_wx_speed - max_time_at_warranted_spd)
    
    # Compile results
    results = {
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
        'bad_wx_speed': bad_speed,
        'bad_wx_fo_cons': bad_fuel,
        'total_me_fuel': total_fuel,
        'entire_voyage_cons': entire_voyage_cons,
        'max_warranted_fo': max_warranted_fo,
        'min_warranted_fo': min_warranted_fo,
        'fuel_overconsumption': fuel_overconsumption,
        'fuel_saving': fuel_saving,
        'time_at_good_wx_speed': time_at_good_wx_speed,
        'max_time_at_warranted_spd': max_time_at_warranted_spd,
        'min_time_at_warranted_spd': min_time_at_warranted_spd,
        'time_gained': time_gained,
        'time_lost': time_lost
    }
    
    return results, df_processed

# Function to create a downloadable PDF report
def create_pdf_report(vessel_details, voyage_details, cp_terms, weather_def, results):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Title'],
        fontSize=16,
        alignment=1,
        spaceAfter=20
    )
    story.append(Paragraph("Charter Party Performance Report", title_style))
    story.append(Spacer(1, 0.25*inch))
    
    # Vessel Details
    story.append(Paragraph("Vessel Details", styles['Heading2']))
    vessel_data = [
        ["Vessel Name", vessel_details['vessel_name']],
        ["IMO Number", vessel_details['imo_no']],
        ["GRT", vessel_details['grt']]
    ]
    vessel_table = Table(vessel_data, colWidths=[2*inch, 3*inch])
    vessel_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(vessel_table)
    story.append(Spacer(1, 0.25*inch))
    
    # Voyage Details
    story.append(Paragraph("Voyage Details", styles['Heading2']))
    # Format dates and times
    cosp_datetime = "N/A"
    eosp_datetime = "N/A"
    
    if voyage_details['cosp_date'] and voyage_details['cosp_time']:
        cosp_date = voyage_details['cosp_date']
        cosp_time = voyage_details['cosp_time']
        cosp_datetime = f"{cosp_date.strftime('%Y-%m-%d')} {cosp_time.strftime('%H:%M')} UTC"
    
    if voyage_details['eosp_date'] and voyage_details['eosp_time']:
        eosp_date = voyage_details['eosp_date']
        eosp_time = voyage_details['eosp_time']
        eosp_datetime = f"{eosp_date.strftime('%Y-%m-%d')} {eosp_time.strftime('%H:%M')} UTC"
    
    voyage_data = [
        ["Departure Port", voyage_details['dep_port']],
        ["Arrival Port", voyage_details['arr_port']],
        ["COSP Date/Time", cosp_datetime],
        ["EOSP Date/Time", eosp_datetime],
        ["Departure Lat/Long", f"{voyage_details['dep_lat']}, {voyage_details['dep_long']}"],
        ["Arrival Lat/Long", f"{voyage_details['arr_lat']}, {voyage_details['arr_long']}"]
    ]
    voyage_table = Table(voyage_data, colWidths=[2*inch, 3*inch])
    voyage_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(voyage_table)
    story.append(Spacer(1, 0.25*inch))
    
    # CP Terms
    story.append(Paragraph("Charter Party Terms", styles['Heading2']))
    if cp_terms:
        cp_data = [["Speed (knots)", "ME Consumption (MT/day)", "AE Consumption (MT/day)"]]
        for term in cp_terms:
            cp_data.append([term['speed'], term['me_consumption'], term['ae_consumption']])
        cp_table = Table(cp_data, colWidths=[1.6*inch, 1.7*inch, 1.7*inch])
        cp_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(cp_table)
    else:
        story.append(Paragraph("No CP terms defined", styles['Normal']))
    story.append(Spacer(1, 0.25*inch))
    
    # Weather Definition
    story.append(Paragraph("Weather Definition", styles['Heading2']))
    weather_data = [
        ["Beaufort Scale Threshold", str(weather_def['beaufort_scale'])],
        ["Wave Height Threshold (m)", str(weather_def['wave_height'])],
        ["Include Current Factor", "Yes" if weather_def['include_current'] else "No"]
    ]
    weather_table = Table(weather_data, colWidths=[2*inch, 3*inch])
    weather_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(weather_table)
    story.append(Spacer(1, 0.25*inch))
    
    # Calculation Results
    story.append(Paragraph("Performance Calculation Results", styles['Heading2']))
    
    # Two columns of results for better layout
    results_data = [
        ["Metric", "Value", "Metric", "Value"],
        ["Total Distance (nm)", f"{results['total_distance']:.2f}", "Total Steaming Time (hrs)", f"{results['total_steaming_time']:.2f}"],
        ["Voyage Avg Speed (knots)", f"{results['voyage_avg_speed']:.2f}", "Good Wx Distance (nm)", f"{results['good_wx_distance']:.2f}"],
        ["Good Wx Time (hrs)", f"{results['good_wx_time']:.2f}", "Good Wx Speed (knots)", f"{results['good_wx_speed']:.2f}"],
        ["Good Wx FO Cons (MT)", f"{results['good_wx_fo_cons']:.2f}", "Good Wx FO Rate (MT/hr)", f"{results['good_wx_fo_rate_hr']:.2f}"],
        ["Good Wx FO Rate (MT/day)", f"{results['good_wx_fo_rate_day']:.2f}", "Bad Wx Distance (nm)", f"{results['bad_wx_distance']:.2f}"],
        ["Bad Wx Time (hrs)", f"{results['bad_wx_time']:.2f}", "Bad Wx Speed (knots)", f"{results['bad_wx_speed']:.2f}"],
        ["Bad Wx FO Cons (MT)", f"{results['bad_wx_fo_cons']:.2f}", "Total ME Fuel (MT)", f"{results['total_me_fuel']:.2f}"],
        ["Entire Voyage Cons (MT)", f"{results['entire_voyage_cons']:.2f}", "Max Warranted FO (MT)", f"{results['max_warranted_fo']:.2f}"],
        ["Min Warranted FO (MT)", f"{results['min_warranted_fo']:.2f}", "Fuel Overconsumption (MT)", f"{results['fuel_overconsumption']:.2f}"],
        ["Fuel Saving (MT)", f"{results['fuel_saving']:.2f}", "Time at Good Wx Speed (hrs)", f"{results['time_at_good_wx_speed']:.2f}"],
        ["Max Time @ Warranted Spd (hrs)", f"{results['max_time_at_warranted_spd']:.2f}", "Min Time @ Warranted Spd (hrs)", f"{results['min_time_at_warranted_spd']:.2f}"],
        ["Time Gained (hrs)", f"{results['time_gained']:.2f}", "Time Lost (hrs)", f"{results['time_lost']:.2f}"]
    ]
    
    results_table = Table(results_data, colWidths=[2*inch, 1*inch, 2*inch, 1*inch])
    results_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(results_table)
    
    # Build the PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

# Function to create a download link for the PDF
def get_pdf_download_link(pdf, filename):
    """Generates a link allowing the PDF to be downloaded
    Args:
        pdf: The BytesIO stream for the pdf.
        filename: The name of the file to download
    Returns:
        A link that when clicked will download the pdf.
    """
    b64 = base64.b64encode(pdf.getvalue()).decode()
    return f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">Download PDF Report</a>'

# Navigation function
def navigation():
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", 
                           ["Vessel & CP Terms", 
                            "CP Calculation", 
                            "Weather Data Analysis", 
                            "Dashboard & Report"])
    return page

# Main application
def main():
    page = navigation()
    
    if page == "Vessel & CP Terms":
        st.title("Vessel, Voyage & CP Terms")
        
        # Vessel Details
        st.header("Vessel Details")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.session_state.vessel_details['vessel_name'] = st.text_input("Vessel Name", st.session_state.vessel_details['vessel_name'])
        with col2:
            st.session_state.vessel_details['imo_no'] = st.text_input("IMO Number", st.session_state.vessel_details['imo_no'])
        with col3:
            st.session_state.vessel_details['grt'] = st.text_input("GRT", st.session_state.vessel_details['grt'])
        
        # Voyage Details
        st.header("Voyage Details")
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.voyage_details['dep_port'] = st.text_input("Departure Port", st.session_state.voyage_details['dep_port'])
            st.session_state.voyage_details['cosp_date'] = st.date_input("COSP Date", st.session_state.voyage_details['cosp_date'] or datetime.date.today())
            st.session_state.voyage_details['cosp_time'] = st.time_input("COSP Time (UTC)", st.session_state.voyage_details['cosp_time'] or datetime.time(0, 0))
            st.session_state.voyage_details['dep_lat'] = st.text_input("Departure Latitude", st.session_state.voyage_details['dep_lat'])
            st.session_state.voyage_details['dep_long'] = st.text_input("Departure Longitude", st.session_state.voyage_details['dep_long'])
        with col2:
            st.session_state.voyage_details['arr_port'] = st.text_input("Arrival Port", st.session_state.voyage_details['arr_port'])
            st.session_state.voyage_details['eosp_date'] = st.date_input("EOSP Date", st.session_state.voyage_details['eosp_date'] or datetime.date.today())
            st.session_state.voyage_details['eosp_time'] = st.time_input("EOSP Time (UTC)", st.session_state.voyage_details['eosp_time'] or datetime.time(0, 0))
            st.session_state.voyage_details['arr_lat'] = st.text_input("Arrival Latitude", st.session_state.voyage_details['arr_lat'])
            st.session_state.voyage_details['arr_long'] = st.text_input("Arrival Longitude", st.session_state.voyage_details['arr_long'])
        
        # CP Terms
        st.header("Charter Party Terms")
        st.subheader("Speed and Consumption")
        
        # Display existing CP terms
        if st.session_state.cp_terms:
            st.write("Current CP Terms:")
            cp_df = pd.DataFrame(st.session_state.cp_terms)
            st.dataframe(cp_df)
        
        # Add new CP term
        st.subheader("Add CP Term")
        with st.form("add_cp_term"):
            col1, col2, col3 = st.columns(3)
            with col1:
                speed = st.number_input("Speed (knots)", min_value=0.0, step=0.1)
            with col2:
                me_consumption = st.number_input("ME Consumption (MT/day)", min_value=0.0, step=0.1)
            with col3:
                ae_consumption = st.number_input("AE Consumption (MT/day)", min_value=0.0, step=0.1)
            
            submitted = st.form_submit_button("Add CP Term")
            if submitted:
                st.session_state.cp_terms.append({
                    'speed': speed,
                    'me_consumption': me_consumption,
                    'ae_consumption': ae_consumption
                })
                st.success("CP Term added successfully!")
                st.experimental_rerun()
        
        # Delete CP term
        if st.session_state.cp_terms:
            with st.form("delete_cp_term"):
                term_to_delete = st.selectbox(
                    "Select CP Term to Delete",
                    range(len(st.session_state.cp_terms)),
                    format_func=lambda i: f"Speed: {st.session_state.cp_terms[i]['speed']} knots, ME: {st.session_state.cp_terms[i]['me_consumption']} MT/day"
                )
                if st.form_submit_button("Delete Selected CP Term"):
                    st.session_state.cp_terms.pop(term_to_delete)
                    st.success("CP Term deleted successfully!")
                    st.experimental_rerun()
        
        # Weather Definition
        st.header("Weather Definition as per CP")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.session_state.weather_definition['beaufort_scale'] = st.slider(
                "Wind Force (Beaufort Scale)",
                min_value=0,
                max_value=12,
                value=st.session_state.weather_definition['beaufort_scale']
            )
        with col2:
            st.session_state.weather_definition['wave_height'] = st.slider(
                "Significant Wave Height (m)",
                min_value=0.0,
                max_value=10.0,
                value=float(st.session_state.weather_definition['wave_height']),
                step=0.1
            )
        with col3:
            st.session_state.weather_definition['include_current'] = st.checkbox(
                "Include Current Factor",
                value=st.session_state.weather_definition['include_current']
            )
        
        # Excluded Periods
        st.header("Excluded Periods")
        
        # Display existing excluded periods
        if st.session_state.excluded_periods:
            st.write("Current Excluded Periods:")
            for i, period in enumerate(st.session_state.excluded_periods):
                st.write(f"{i+1}. From: {period['from']} To: {period['to']}")
        
        # Add new excluded period
        st.subheader("Add Excluded Period")
        with st.form("add_excluded_period"):
            col1, col2 = st.columns(2)
            with col1:
                from_date = st.date_input("From Date", datetime.date.today())
                from_time = st.time_input("From Time (UTC)", datetime.time(0, 0))
            with col2:
                to_date = st.date_input("To Date", datetime.date.today())
                to_time = st.time_input("To Time (UTC)", datetime.time(0, 0))
            
            submitted = st.form_submit_button("Add Excluded Period")
            if submitted:
                from_dt = to_utc(from_date, from_time)
                to_dt = to_utc(to_date, to_time)
                
                if from_dt and to_dt and from_dt < to_dt:
                    st.session_state.excluded_periods.append({
                        'from': from_dt,
                        'to': to_dt
                    })
                    st.success("Excluded period added successfully!")
                    st.experimental_rerun()
                else:
                    st.error("Invalid date range. 'From' must be before 'To'.")
        
        # Delete excluded period
        if st.session_state.excluded_periods:
            with st.form("delete_excluded_period"):
                period_to_delete = st.selectbox(
                    "Select Excluded Period to Delete",
                    range(len(st.session_state.excluded_periods)),
                    format_func=lambda i: f"From: {st.session_state.excluded_periods[i]['from']} To: {st.session_state.excluded_periods[i]['to']}"
                )
                if st.form_submit_button("Delete Selected Period"):
                    st.session_state.excluded_periods.pop(period_to_delete)
                    st.success("Excluded period deleted successfully!")
                    st.experimental_rerun()
        
        # Comments
        st.header("Comments")
        st.session_state.comments = st.text_area("Additional Comments", st.session_state.comments, height=100)
        
        # Calculation Data Upload
        st.header("Calculation Data Upload")
        st.write("Upload CSV or Excel file with data for CP performance calculation")
        calc_file = st.file_uploader("Choose a file", type=["csv", "xlsx", "xls"], key="calc_data_upload")
        
        if calc_file is not None:
            try:
                if calc_file.name.endswith('.csv'):
                    df = pd.read_csv(calc_file)
                else:
                    df = pd.read_excel(calc_file)
                
                st.session_state.calc_data = df
                st.success(f"File uploaded successfully. {len(df)} records found.")
                st.dataframe(df.head())
                
                # Check if required columns are present
                required_cols = ['datetime', 'distance']
                missing_cols = [col for col in required_cols if col not in df.columns]
                if missing_cols:
                    st.warning(f"Warning: The following required columns are missing: {', '.join(missing_cols)}")
            except Exception as e:
                st.error(f"Error reading file: {e}")
        
        # Weather Data Upload
        st.header("Weather Data Upload")
        st.write("Upload CSV or
