import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import base64
import os

# --- BLOCK A: SETUP ---
st.set_page_config(page_title="Muziris '26 Admin", page_icon="🎪", layout="centered")

# --- DATABASE CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)
# We load the members list to validate IDs when logging sales
member_df = conn.read(worksheet="Members", ttl=600)

# --- HELPER: LOAD LOGO ---
def load_image_base64(img_name):
    if os.path.exists(img_name):
        with open(img_name, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
            ext = "png" if img_name.lower().endswith(".png") else "jpeg"
            return f"data:image/{ext};base64,{encoded}"
    return ""

# --- STYLISH VINTAGE HEADER ---
img_muziris = load_image_base64("muziris.png")
header_html = f"""
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;1,700&display=swap" rel="stylesheet">
<div style="text-align: center; margin-bottom: 25px;">
    <h1 style="color: #E32636; font-family: 'Playfair Display', serif; font-weight: 700; display: flex; justify-content: center; align-items: center; gap: 15px; margin-bottom: 5px; font-size: 36px;">
        <img src="{img_muziris}" style="height: 50px; object-fit: contain;">
        Muziris '26 Admin
    </h1>
    <p style="color: #666; font-size: 16px; margin-top: 0;">Nightly Physical Sales & Donation Log</p>
</div>
"""
st.markdown(header_html, unsafe_allow_html=True)

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["📝 Log Sales", "🏆 Leaderboard", "💼 Head Ledger"])

# ==========================================
# TAB 1: NIGHTLY BULK ENTRY FORM
# ==========================================
with tab1:
    with st.container(border=True):
        st.markdown("### 📥 Nightly Data Entry")
        st.caption("Heads: Log the physical sales and donations for your team here.")
        
        with st.form("daily_log_form", clear_on_submit=True):
            head_id = st.text_input("👑 Your Head ID (Mandatory)", placeholder="e.g., 1001")
            
            st.divider()
            
            student_id = st.text_input("👤 Selling Student ID (Mandatory)", placeholder="e.g., 1005 (Use your own ID if you made the sale)")
            
            col1, col2 = st.columns(2)
            with col1:
                coupons = st.number_input("🎟️ Coupons Sold", min_value=0, step=1, value=0)
            with col2:
                donations = st.number_input("💵 Donations (₹)", min_value=0, step=50, value=0)
                
            submit_btn = st.form_submit_button("💾 Save to Ledger", type="primary", use_container_width=True)
            
            if submit_btn:
                # 1. Basic Validation
                if not head_id or not student_id:
                    st.error("❌ Both Head ID and Student ID are required.")
                elif coupons == 0 and donations == 0:
                    st.warning("⚠️ You must enter at least 1 coupon or some donation amount.")
                else:
                    clean_head = head_id.strip()
                    clean_student = student_id.strip()
                    
                    # 2. Verify IDs exist in the Members sheet
                    head_match = member_df[member_df['ID'].astype(str).str.split('.').str[0] == clean_head]
                    student_match = member_df[member_df['ID'].astype(str).str.split('.').str[0] == clean_student]
                    
                    if head_match.empty:
                        st.error(f"❌ Head ID {clean_head} not found in database.")
                    elif student_match.empty:
                        st.error(f"❌ Student ID {clean_student} not found in database.")
                    else:
                        # 3. Everything is good, save to Daily_Logs
                        new_log = pd.DataFrame([{
                            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "Head ID": clean_head,
                            "Student ID": clean_student,
                            "Coupons Sold": coupons,
                            "Donations": donations
                        }])
                        
                        logs_df = conn.read(worksheet="Daily_Logs", ttl=0)
                        updated_logs = pd.concat([logs_df, new_log], ignore_index=True)
                        conn.update(worksheet="Daily_Logs", data=updated_logs)
                        
                        student_name = student_match.iloc[0]['Name']
                        st.success(f"✅ Logged successfully! {coupons} coupons and ₹{donations} credited to {student_name}.")

# ==========================================
# TAB 2 & 3: LEADERBOARD & LEDGER LOGIC
# ==========================================
with tab2:
    st.markdown("<h3 style='text-align: center; color: #E32636;'>🔥 Top Fundraisers 🔥</h3>", unsafe_allow_html=True)
    
    if st.button("🔄 Refresh Data", type="primary", use_container_width=True, key="btn_refresh"):
        with st.spinner("Crunching the numbers..."):
            logs_df = conn.read(worksheet="Daily_Logs", ttl=0)
            
            if not logs_df.empty:
                # Ensure columns are numeric
                logs_df['Coupons Sold'] = pd.to_numeric(logs_df['Coupons Sold'], errors='coerce').fillna(0).astype(int)
                logs_df['Donations'] = pd.to_numeric(logs_df['Donations'], errors='coerce').fillna(0).astype(int)
                
                # ----------------------------------------
                # PROCESS STUDENT LEADERBOARD (TAB 2)
                # ----------------------------------------
                student_summary = logs_df.groupby('Student ID').agg({
                    'Coupons Sold': 'sum',
                    'Donations': 'sum',
                    'Timestamp': 'max' # Get latest entry time for tie-breakers
                }).reset_index()
                
                # Fetch Names from member_df
                student_summary['Student Name'] = student_summary['Student ID'].apply(
                    lambda x: member_df[member_df['ID'].astype(str).str.split('.').str[0] == str(x)]['Name'].iloc[0] 
                    if not member_df[member_df['ID'].astype(str).str.split('.').str[0] == str(x)].empty else f"ID: {x}"
                )
                
                # Calculate Totals and Sort
                student_summary['Total (₹)'] = (student_summary['Coupons Sold'] * 100) + student_summary['Donations']
                student_summary = student_summary.sort_values(by=['Total (₹)', 'Timestamp'], ascending=[False, False]).reset_index(drop=True)
                
                st.session_state['leaderboard_data'] = student_summary
                
                # ----------------------------------------
                # PROCESS HEAD LEDGER (TAB 3)
                # ----------------------------------------
                head_summary = logs_df.groupby('Head ID').agg({
                    'Coupons Sold': 'sum',
                    'Donations': 'sum'
                }).reset_index()
                
                head_summary['Head Name'] = head_summary['Head ID'].apply(
                    lambda x: member_df[member_df['ID'].astype(str).str.split('.').str[0] == str(x)]['Name'].iloc[0] 
                    if not member_df[member_df['ID'].astype(str).str.split('.').str[0] == str(x)].empty else f"ID: {x}"
                )
                
                head_summary['Total Owed (₹)'] = (head_summary['Coupons Sold'] * 100) + head_summary['Donations']
                head_summary = head_summary.sort_values(by='Total Owed (₹)', ascending=False).reset_index(drop=True)
                
                st.session_state['ledger_data'] = head_summary
                
            else:
                st.info("No data logged yet!")

    # --- RENDER LEADERBOARD UI ---
    if 'leaderboard_data' in st.session_state:
        df = st.session_state['leaderboard_data']
        
        # The Fire Progress Bar
        TOTAL_TARGET = 2000
        current_sold = df['Coupons Sold'].sum()
        percentage = min((current_sold / TOTAL_TARGET) * 100, 100)
        
        progress_html = f"""
        <style>
        @keyframes glow {{ 0% {{ box-shadow: 0 0 5px #ff4500; }} 100% {{ box-shadow: 0 0 15px #ff8c00; }} }}
        </style>
        <div style="margin-bottom: 25px; margin-top: 15px;">
            <p style="text-align: center; font-weight: bold; color: #444; margin-bottom: 5px;">Festival Goal: {current_sold} / {TOTAL_TARGET} Coupons ✨</p>
            <div style="width: 100%; background-color: #e0e0e0; border-radius: 15px; height: 25px; overflow: hidden; border: 1px solid #ccc;">
                <div style="width: {percentage}%; height: 100%; background: linear-gradient(90deg, #ff0000, #ff8c00, #ffcc00); border-radius: 15px; text-align: right; display: flex; align-items: center; justify-content: flex-end; padding-right: 8px; animation: glow 1.5s infinite alternate;">
                    <span style="font-size: 16px;">🔥</span>
                </div>
            </div>
        </div>
        """
        st.markdown(progress_html, unsafe_allow_html=True)
        st.divider()

        # The Metallic Podiums
        def make_podium_card(bg_gradient, border_color, text_dark, text_light, emoji, title, name, total, coupons, donations):
            return f"""
            <div style="background: {bg_gradient}; padding: 15px; border-radius: 10px; margin-bottom: 15px; border: 1px solid {border_color}; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <h4 style="margin: 0; color: {text_dark}; font-size: 18px; font-family: sans-serif;">{emoji} {title} • {name}</h4>
                <h2 style="margin: 5px 0; color: {text_dark}; font-size: 32px; font-family: sans-serif; font-weight: bold;">₹{total}</h2>
                <p style="margin: 0; color: {text_light}; font-size: 14px; font-family: sans-serif; font-weight: bold;">{coupons} Coupons | ₹{donations} Donations</p>
            </div>
            """

        if len(df) > 0: st.markdown(make_podium_card("linear-gradient(135deg, #FFF9D6, #FFD700)", "#E6C200", "#4D4000", "#806A00", "🥇", "1st Place", df.iloc[0]["Student Name"], df.iloc[0]["Total (₹)"], df.iloc[0]["Coupons Sold"], df.iloc[0]["Donations"]), unsafe_allow_html=True)
        if len(df) > 1: st.markdown(make_podium_card("linear-gradient(135deg, #F8F9FA, #E0E0E0)", "#BDBDBD", "#333333", "#666666", "🥈", "2nd Place", df.iloc[1]["Student Name"], df.iloc[1]["Total (₹)"], df.iloc[1]["Coupons Sold"], df.iloc[1]["Donations"]), unsafe_allow_html=True)
        if len(df) > 2: st.markdown(make_podium_card("linear-gradient(135deg, #FFF0E6, #EBA87A)", "#CD7F32", "#5C3A21", "#8A5A33", "🥉", "3rd Place", df.iloc[2]["Student Name"], df.iloc[2]["Total (₹)"], df.iloc[2]["Coupons Sold"], df.iloc[2]["Donations"]), unsafe_allow_html=True)

        # The Heatmap Top 10 Table
        st.markdown("#### Top 10 Rankings")
        top_10_df = df.head(10).copy()
        display_df = top_10_df[['Student Name', 'Coupons Sold', 'Donations', 'Total (₹)']]
        styled_df = display_df.style.background_gradient(subset=['Total (₹)'], cmap='Reds').format({"Total (₹)": "₹{:.0f}"})
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        st.divider()

        # The Individual Search Bar
        with st.expander("🔍 Check Your Specific Stats"):
            search_query = st.text_input("Type your name to find your rank and totals:", placeholder="e.g., Muhammed")
            if search_query:
                user_result = df[df['Student Name'].str.contains(search_query, case=False, na=False)]
                if not user_result.empty:
                    user_result = user_result.copy()
                    user_result['Current Rank'] = user_result.index + 1
                    display_result = user_result[['Current Rank', 'Student Name', 'Coupons Sold', 'Donations', 'Total (₹)']]
                    st.dataframe(display_result, use_container_width=True, hide_index=True)
                else:
                    st.warning("No records found. If you recently logged a sale, hit Refresh Data above!")

# ==========================================
# TAB 3: THE HEAD LEDGER UI
# ==========================================
with tab3:
    st.markdown("### 💼 Head Collection Ledger")
    st.caption("This tab groups all sales by Head ID. It shows exactly how much cash each Head is responsible for handing over to the Admin.")
    
    if 'ledger_data' in st.session_state:
        ledger = st.session_state['ledger_data']
        
        display_ledger = ledger[['Head Name', 'Coupons Sold', 'Donations', 'Total Owed (₹)']]
        styled_ledger = display_ledger.style.background_gradient(subset=['Total Owed (₹)'], cmap='Blues').format({"Total Owed (₹)": "₹{:.0f}"})
        
        st.dataframe(styled_ledger, use_container_width=True, hide_index=True)
        
        total_cash_expected = ledger['Total Owed (₹)'].sum()
        st.success(f"**💰 Grand Total to collect from all Heads: ₹{int(total_cash_expected)}**")
    else:
        st.info("Click 'Refresh Data' on the Leaderboard tab to generate the ledger.")