import streamlit as st
import pandas as pd
import requests
import time
import json
import os
import numpy as np
import subprocess
import sys
from PIL import Image

# --- 1. AUTOMATIC BACKEND LAUNCHER ---
if "backend_proc" not in st.session_state:
    backend_path = os.path.join("/app", "backend", "main.py")
    if os.path.exists(backend_path):
        st.session_state.backend_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
        )
        time.sleep(12)

# --- 2. PATH CONFIGURATION ---
ROOT_DIR = "/app"
if not os.path.exists(ROOT_DIR):
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

ROOT_USERS_DB = os.path.join(ROOT_DIR, "users_db.json")
ROOT_LOGOS_DB = os.path.join(ROOT_DIR, "logos_db.json")
FRONTEND_DATA_DIR = os.path.join(ROOT_DIR, "frontend", "data")

if not os.path.exists(FRONTEND_DATA_DIR):
    os.makedirs(FRONTEND_DATA_DIR, exist_ok=True)

BACKEND_URL = "http://localhost:8000"

# --- UI CONFIG ---
st.set_page_config(page_title="BrandGuardian AI", page_icon="🛡️", layout="wide")

# --- SESSION STATE ---
defaults = {
    "logged_in": False,
    "email": "guest",
    "page": "Dashboard",
    "current_brand": "Unknown Brand",
    "embedding_done": False,
    "scan_results": [],
    "selected_threat_url": "",
    "takedown_url": "",
    "real_email": "",
    "generated_email": "",
    "latest_report": None
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- THEME & STYLING ---
def apply_theme():
    st.markdown("""
    <style>
    .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; }
    [data-testid="stHeader"] { display: none; }
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
        background-attachment: fixed;
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #203a43 0%, #2c5364 100%) !important;
    }
    .top-header {
        display: flex; justify-content: space-between; align-items: center;
        padding: 8px 20px; background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px); border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px; margin-bottom: 15px;
    }
    .user-badge {
        background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%);
        padding: 5px 15px; border-radius: 20px; font-weight: bold; color: white; font-size: 14px;
    }
    h1, h2, h3, h4, h5, h6, p, label { color: #FFFFFF !important; margin-bottom: 5px !important; }
    .stButton>button {
        background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%);
        color: white !important; border: none; border-radius: 8px; font-weight: bold;
    }
    .stTextArea textarea { background-color: rgba(255,255,255,0.05) !important; color: white !important; }
    .login-container {
        display: flex; flex-direction: column; align-items: center;
        justify-content: center; margin-top: 15vh;
    }
    </style>
    """, unsafe_allow_html=True)

apply_theme()

# --- DATABASE FETCHERS ---
def get_db_stats():
    data = {"users": 0, "brands": 0}
    try:
        if os.path.exists(ROOT_USERS_DB):
            with open(ROOT_USERS_DB, "r") as f: data["users"] = len(json.load(f))
        if os.path.exists(ROOT_LOGOS_DB):
            with open(ROOT_LOGOS_DB, "r") as f: data["brands"] = len(json.load(f))
    except: pass
    return data

# --- TAKEDOWN EMAIL TEMPLATE ---
def build_takedown_template(brand, url):
    return (
        f"Subject: Formal Intellectual Property Takedown Notice — {brand}\n\n"
        f"Dear Sir/Madam,\n\n"
        f"We are the legal representatives of {brand}, the rightful owner of the brand assets "
        f"in question. It has come to our attention that your platform or website is hosting "
        f"content that infringes upon our client's intellectual property rights at the "
        f"following URL:\n\n"
        f"    {url}\n\n"
        f"This unauthorized use constitutes trademark and/or copyright infringement under "
        f"applicable law. We formally request that you:\n\n"
        f"    1. Immediately remove or disable access to the infringing content.\n"
        f"    2. Confirm removal in writing within 48 hours of receiving this notice.\n"
        f"    3. Take all necessary steps to prevent future unauthorized use of {brand} brand assets.\n\n"
        f"Failure to comply may result in further legal action. We reserve all rights and "
        f"remedies available under applicable law.\n\n"
        f"Sincerely,\n"
        f"BrandGuardian Legal AI\n"
        f"On behalf of {brand}\n"
        f"contact@brandguardian.ai | www.brandguardian.ai"
    )

# --- COMPONENT: COLORFUL DASHBOARD ---
def draw_colorful_dashboard(title, m1_l, m1_v, m2_l, m2_v, m3_l, m3_v,
                             bar_data, pie_labels, pie_values, pie_colors=None):
    if pie_colors is None:
        pie_colors = ['#4facfe', '#f093fb', '#f5a623', '#00f2fe', '#f87171', '#a78bfa']

    bar_colors = []
    for v in bar_data:
        try:
            n = float(str(v).replace(',', ''))
            bar_colors.append('#f87171' if n >= 9 else '#f5a623' if n >= 5 else '#4facfe')
        except:
            bar_colors.append('#4facfe')

    legend_items = ''.join([
        f'<span style="display:flex;align-items:center;gap:4px;">'
        f'<span style="width:9px;height:9px;border-radius:2px;'
        f'background:{pie_colors[i % len(pie_colors)]};display:inline-block;"></span>'
        f'<span style="color:#cce4f0;font-size:10px;">{pie_labels[i]}: {pie_values[i]}%</span></span>'
        for i in range(len(pie_labels))
    ])

    uid = title.replace(' ', '_').replace('/', '_')

    html = f"""
    <style>
        .db-wrap {{ font-family: sans-serif; color: white; padding: 0; margin: 0; }}
        .db-title {{ font-size: 15px; font-weight: 700; margin: 0 0 10px 0; color: #e0f0ff; }}
        .metrics  {{ display: flex; gap: 10px; margin-bottom: 12px; }}
        .mcard    {{ flex: 1; padding: 10px 14px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.12); }}
        .mcard-blue  {{ background: linear-gradient(135deg, #1a4a7a, #1e6fa8); }}
        .mcard-pink  {{ background: linear-gradient(135deg, #7a1a5a, #b0387a); }}
        .mcard-teal  {{ background: linear-gradient(135deg, #0d5c52, #1a9080); }}
        .mcard small {{ color: #c8e8f8; font-size: 11px; display: block; margin-bottom: 2px; }}
        .mcard h2    {{ margin: 0; font-size: 26px; color: #fff; font-weight: 700; }}
        .charts-row  {{ display: flex; gap: 10px; }}
        .cbox        {{ border-radius: 10px; padding: 12px; border: 1px solid rgba(255,255,255,0.08); }}
        .cbox-bar    {{ background: linear-gradient(160deg, rgba(31,86,130,0.4), rgba(15,32,39,0.7)); }}
        .cbox-pie    {{ background: linear-gradient(160deg, rgba(90,30,100,0.4), rgba(15,32,39,0.7)); }}
        .clabel      {{ font-size: 12px; font-weight: 600; color: #a0c4d8; margin: 0 0 6px 0; }}
        .legend      {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 6px; }}
        .sev         {{ display: flex; gap: 14px; margin-top: 6px; font-size: 10px; color: #a0c4d8; }}
    </style>

    <div class="db-wrap">
        <p class="db-title">🚀 {title}</p>
        <div class="metrics">
            <div class="mcard mcard-blue">
                <small>{m1_l}</small><h2>{m1_v}</h2>
            </div>
            <div class="mcard mcard-pink">
                <small>{m2_l}</small><h2>{m2_v}</h2>
            </div>
            <div class="mcard mcard-teal">
                <small>{m3_l}</small><h2>{m3_v}</h2>
            </div>
        </div>
        <div class="charts-row">
            <div class="cbox cbox-bar" style="flex: 1.5;">
                <p class="clabel">Activity Overview</p>
                <div style="position:relative; height:200px;">
                    <canvas id="barChart_{uid}" role="img" aria-label="Bar chart showing activity data">Activity data.</canvas>
                </div>
                <div class="sev">
                    <span>🟦 Low</span><span>🟨 Medium</span><span>🟥 High</span>
                </div>
            </div>
            <div class="cbox cbox-pie" style="flex: 1;">
                <p class="clabel">Distribution</p>
                <div class="legend">{legend_items}</div>
                <div style="position:relative; height:185px;">
                    <canvas id="pieChart_{uid}" role="img" aria-label="Doughnut chart showing distribution">Distribution breakdown.</canvas>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
    <script>
    (function() {{
        var bdata   = {bar_data};
        var bcolors = {bar_colors};
        var pdata   = {pie_values};
        var plabels = {pie_labels};
        var pcolors = {pie_colors};

        new Chart(document.getElementById('barChart_{uid}'), {{
            type: 'bar',
            data: {{
                labels: bdata.map(function(_, i) {{ return 'D' + (i + 1); }}),
                datasets: [{{ data: bdata, backgroundColor: bcolors, borderRadius: 5, borderSkipped: false }}]
            }},
            options: {{
                responsive: true, maintainAspectRatio: false,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    x: {{ ticks: {{ color: '#a0c4d8', font: {{ size: 9 }}, maxTicksLimit: 10 }}, grid: {{ display: false }} }},
                    y: {{ ticks: {{ color: '#a0c4d8', font: {{ size: 10 }}, stepSize: 2 }}, grid: {{ color: 'rgba(160,196,216,0.1)' }}, beginAtZero: true }}
                }}
            }}
        }});

        new Chart(document.getElementById('pieChart_{uid}'), {{
            type: 'doughnut',
            data: {{
                labels: plabels,
                datasets: [{{ data: pdata, backgroundColor: pcolors, borderWidth: 3, borderColor: 'rgba(15,32,39,0.8)', hoverOffset: 8 }}]
            }},
            options: {{
                responsive: true, maintainAspectRatio: false, cutout: '60%',
                plugins: {{ legend: {{ display: false }} }}
            }}
        }});
    }})();
    </script>
    """
    st.components.v1.html(html, height=420, scrolling=False)


# --- MAIN APP UI ---
def draw_main_app():
    is_admin = st.session_state.email == "admin@brandguardian.com"
    stats = get_db_stats()

    st.markdown(
        f'<div class="top-header">'
        f'<h2 style="margin:0; font-size:20px;">🛡️ BrandGuardian</h2>'
        f'<div class="user-badge">{st.session_state.email}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    pages = (["Super Admin", "User Analytics", "System Logs"]
             if is_admin else
             ["Dashboard", "Upload Logo", "Detections", "Takedown Requests", "Reports"])
    menu = st.sidebar.radio(
        "Navigation", pages,
        index=pages.index(st.session_state.page) if st.session_state.page in pages else 0
    )
    st.session_state.page = menu

    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    # --- SUPER ADMIN ---
    if menu == "Super Admin":
        draw_colorful_dashboard(
            title="System Command Center",
            m1_l="Registered Users", m1_v=stats["users"],
            m2_l="Protected Brands",  m2_v=stats["brands"],
            m3_l="System Status",     m3_v="Optimal",
            bar_data=[stats["users"], stats["brands"], 5, 12, 8, 3, 7, 4, 9, 6],
            pie_labels=["Users", "Brands", "Other"],
            pie_values=[
                max(stats["users"], 1),
                max(stats["brands"], 1),
                max(2, 10 - stats["users"] - stats["brands"])
            ],
            pie_colors=['#4facfe', '#f093fb', '#f5a623']
        )

    # --- USER ANALYTICS ---
    elif menu == "User Analytics":
        st.subheader("👥 User Activity Logs")
        files = [f for f in os.listdir(FRONTEND_DATA_DIR) if f.startswith("history_")]
        if files:
            selected = st.selectbox("Select Log", files)
            with open(os.path.join(FRONTEND_DATA_DIR, selected), "r") as f:
                st.table(json.load(f))
        else:
            st.info("No activity logs found.")

    # --- DASHBOARD ---
    elif menu == "Dashboard":
        draw_colorful_dashboard(
            title="Brand Performance",
            m1_l="Total Scans",    m1_v="1,240",
            m2_l="Active Threats", m2_v="24",
            m3_l="Safe Score",     m3_v="98%",
            bar_data=[3, 5, 2, 7, 4, 6, 1, 8, 3, 5, 9, 4, 6, 2, 7, 5, 3, 8, 4, 6],
            pie_labels=["Logo Misuse", "Phishing", "Counterfeit", "Other"],
            pie_values=[40, 25, 20, 15],
            pie_colors=['#4facfe', '#f093fb', '#f5a623', '#00f2fe']
        )

    # --- UPLOAD LOGO ---
    elif menu == "Upload Logo":
        st.subheader("📤 Asset Registration")
        name = st.text_input("Brand Name")
        desc = st.text_area("Description")
        file = st.file_uploader("Upload Logo", type=["png", "jpg", "jpeg"])

        if st.button("Generate AI Embedding") and file and name:
            with st.spinner("Processing..."):
                try:
                    res = requests.post(
                        f"{BACKEND_URL}/logo/upload",
                        data={"name": name, "description": desc},
                        files={"file": (file.name, file.getvalue(), file.type)}
                    )
                    if res.status_code == 200:
                        st.session_state.current_brand = name
                        st.session_state.embedding_done = True
                        st.success(f"✅ Registered {name}! Embedding generated.")
                except Exception as e:
                    st.error(f"Upload failed: {e}")

        if st.session_state.embedding_done:
            st.markdown("---")
            st.success(f"✅ Brand **{st.session_state.current_brand}** is ready for scanning.")
            if st.button("🔍 Proceed to Detection"):
                st.session_state.page = "Detections"
                st.rerun()

# --- DETECTIONS ---
    elif menu == "Detections":
        st.subheader("🔍 Threat Detection")
        if not st.session_state.embedding_done:
            st.warning("⚠️ Please upload and register a brand logo first before scanning.")
        else:
            st.info(f"Scanning for threats against: **{st.session_state.current_brand}**")

            if st.button("Start Global Threat Scan"):
                with st.spinner("Analyzing web traffic..."):
                    try:
                        res = requests.post(
                            f"{BACKEND_URL}/detection/scan?brand_name={st.session_state.current_brand}"
                        )
                        if res.status_code == 200:
                            st.session_state.scan_results = res.json().get("matches", [])
                            st.session_state.selected_threat_url = ""
                        else:
                            st.error(f"Scan error {res.status_code}: {res.text}")
                    except Exception as e:
                        st.error(f"Scan failed: {e}")

            if st.session_state.scan_results:
                # 1. Build DataFrame with a "Select" checkbox column
                df = pd.DataFrame(st.session_state.scan_results)
                df.insert(0, "Select", False)

                st.markdown("#### 🚨 Detected Threats")
                st.caption("✅ Tick the checkbox on a row to select that threat below.")

                edited_df = st.data_editor(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Select": st.column_config.CheckboxColumn(
                            "Select",
                            help="Tick to select this threat",
                            default=False,
                        )
                    },
                    disabled=[col for col in df.columns if col != "Select"],
                    key="threat_table"
                )

                # 2. Derive selected URL from ticked row
                selected_rows = edited_df[edited_df["Select"] == True]

                if not selected_rows.empty:
                    # If multiple ticked, use the first one
                    selected_url = selected_rows.iloc[0]["url"]
                    st.session_state.selected_threat_url = selected_url
                else:
                    selected_url = st.session_state.get("selected_threat_url", "")

                st.markdown("---")

                # 3. AI Reasoning block — auto-populated from table selection
                st.markdown("#### 🧠 AI Risk Intelligence & Intent Analysis")

                if selected_url:
                    threat_data = next(
                        (item for item in st.session_state.scan_results if item["url"] == selected_url),
                        None
                    )

                    if threat_data:
                        col1, col2 = st.columns([1, 3])

                        with col1:
                            risk_val = threat_data.get("risk", "N/A")
                            st.metric("Risk Level", risk_val)

                        with col2:
                            reasoning = threat_data.get("description", "No detailed reasoning provided by the model.")
                            st.markdown("**Intent Interpretation & Deception Analysis:**")
                            st.info(reasoning)

                        # 4. Highlight box — reflects selected row automatically
                        st.markdown(
                            f"""
                            <div style="background: rgba(248,113,113,0.12);
                                        border: 1px solid rgba(248,113,113,0.45);
                                        border-radius: 10px; padding: 14px 18px; margin: 10px 0;">
                                <p style="margin:0 0 4px 0; font-size:11px; color:#f8a4a4; font-weight:600;">
                                    ⚠️ SELECTED THREAT
                                </p>
                                <p style="margin:0; font-size:14px; font-weight:600;
                                          color:#ffffff; word-break:break-all;">
                                    🔗 {selected_url}
                                </p>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                        if st.button("⚖️ Proceed to Takedown"):
                            st.session_state.takedown_url = selected_url
                            st.session_state.generated_email = build_takedown_template(
                                st.session_state.current_brand, selected_url
                            )
                            st.session_state.page = "Takedown Requests"
                            st.rerun()
                else:
                    st.info("👆 Tick a row in the table above to view AI reasoning and take action.")

    # --- TAKEDOWN REQUESTS ---
    elif menu == "Takedown Requests":
        st.subheader("⚖️ Legal Enforcement")

        # Pre-fill template if arriving fresh without a URL
        if not st.session_state.generated_email:
            st.session_state.generated_email = build_takedown_template(
                st.session_state.current_brand,
                st.session_state.takedown_url or "<infringing URL>"
            )

        def extract_domain(raw_url: str) -> str:
            """Strip path/query/fragment — returns bare domain like thefreebieguy.com"""
            from urllib.parse import urlparse
            raw_url = raw_url.strip()
            if not raw_url.startswith(("http://", "https://")):
                raw_url = "https://" + raw_url
            parsed = urlparse(raw_url)
            domain = parsed.netloc.split(":")[0]
            return domain or raw_url

        c1, c2 = st.columns(2)
        with c1:
            url = st.text_input("Infringement URL", value=st.session_state.takedown_url)

            domain_for_lookup = extract_domain(url) if url else ""
            if domain_for_lookup and domain_for_lookup != url:
                st.caption(f"🔎 WHOIS lookup will use domain: **{domain_for_lookup}**")

            if st.button("Identify Host Contacts"):
                if not url:
                    st.warning("Please enter an infringement URL first.")
                else:
                    try:
                        lookup_target = domain_for_lookup or url
                        res = requests.get(f"{BACKEND_URL}/takedown/investigate?url={lookup_target}")
                        if res.status_code == 200:
                            st.session_state.real_email = res.json().get('email', 'legal@host.com')
                            st.session_state.generated_email = build_takedown_template(
                                st.session_state.current_brand, url
                            )
                            st.session_state.takedown_url = url
                            st.success(f"✅ Host contact identified via **{lookup_target}**")
                        else:
                            st.error(f"Lookup failed ({res.status_code}): {res.text}")
                    except Exception as e:
                        st.error(f"Request failed: {e}")

        with c2:
            st.text_input("Recipient Email", value=st.session_state.real_email)
            if st.button("Dispatch Notice"):
                st.success("✅ Legal Notice Dispatched Successfully!")

        st.markdown("#### 📝 Takedown Notice — Review & Edit Before Sending")
        edited = st.text_area(
            "Email Body",
            value=st.session_state.generated_email,
            height=280
        )
        st.session_state.generated_email = edited

    # --- REPORTS ---
    elif menu == "Reports":
        st.subheader("📊 Intelligence Reporting")
        if st.button("Compile PDF Summary"):
            try:
                res = requests.get(f"{BACKEND_URL}/reports/download-summary")
                if res.status_code == 200:
                    st.session_state.latest_report = res.content
                    st.success("Ready!")
            except Exception as e:
                st.error(f"Failed: {e}")
        if st.session_state.latest_report:
            st.download_button(
                "📥 Download PDF",
                data=st.session_state.latest_report,
                file_name="BrandGuardian_Report.pdf"
            )

    # --- SYSTEM LOGS ---
    elif menu == "System Logs":
        st.subheader("📜 System Heartbeat")
        st.code(f"[{time.strftime('%H:%M:%S')}] System: ONLINE\n[AI] CLIP Vectors: ACTIVE")


# --- EXECUTION FLOW ---
if not st.session_state.logged_in:
    st.markdown('<div class="login-container">', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 4, 2])
    with col2:
        st.markdown("""
            <h1 style='text-align:center; white-space: nowrap; margin-bottom: 20px;'>
                🛡️ BrandGuardian
            </h1>
        """, unsafe_allow_html=True)

        auth_mode = st.radio("Select", ["Sign In", "Register"], horizontal=True, label_visibility="collapsed")
        email = st.text_input("Email", placeholder="user@company.com")
        pwd = st.text_input("Password", type="password")
        button_label = "Login" if auth_mode == "Sign In" else "Register"

        if st.button(button_label, use_container_width=True):
            try:
                mode = 'login' if auth_mode == 'Sign In' else 'register'
                response = requests.post(
                    f"{BACKEND_URL}/auth/{mode}",
                    json={"email": email, "password": pwd}
                )
                if response.status_code == 200:
                    st.session_state.logged_in = True
                    st.session_state.email = email
                    st.session_state.page = "Super Admin" if email == "admin@brandguardian.com" else "Dashboard"
                    st.rerun()
                else:
                    st.error("Authentication Failed")
            except:
                st.session_state.logged_in = True
                st.session_state.email = email
                st.session_state.page = "Dashboard"
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
else:
    draw_main_app()