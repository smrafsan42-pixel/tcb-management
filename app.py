import streamlit as st
import pandas as pd
import sqlite3
import hashlib
from datetime import datetime
from fpdf import FPDF
import qrcode
from io import BytesIO

# --- Database Setup ---
conn = sqlite3.connect('tcb_web_system.db', check_same_thread=False)
c = conn.cursor()

def create_tables():
    # সদস্যদের টেবিল
    c.execute('''CREATE TABLE IF NOT EXISTS members
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, nid TEXT, tcb_no TEXT UNIQUE, 
                  ward TEXT, village TEXT, union_name TEXT, thana TEXT, district TEXT, 
                  status TEXT DEFAULT 'বাকি', receive_date TEXT)''')
    # ইউজারদের টেবিল (Login/Signup এর জন্য)
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, password TEXT)''')
    conn.commit()

create_tables()

# পাসওয়ার্ড হ্যাশিং (নিরাপত্তার জন্য)
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    if make_hashes(password) == hashed_text:
        return hashed_text
    return False

# --- Helper Functions ---
def print_receipt(row):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="TCB Distribution Receipt", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    pdf.cell(200, 10, txt=f"Name: {row['name']}", ln=True)
    pdf.cell(200, 10, txt=f"TCB No: {row['tcb_no']}", ln=True)
    pdf.cell(200, 10, txt=f"Date: {row['receive_date']}", ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- UI Setup ---
st.set_page_config(page_title="TCB Website Dashboard", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# --- Login / Signup Page ---
if not st.session_state['logged_in']:
    st.title("🔐 TCB ম্যানেজমেন্ট সিস্টেম")
    choice = st.sidebar.selectbox("লগইন/সাইনআপ", ["Login", "Sign Up"])

    if choice == "Login":
        st.subheader("লগইন করুন")
        username = st.text_input("ইউজারনেম")
        password = st.text_input("পাসওয়ার্ড", type='password')
        if st.button("Login"):
            hashed_pswd = make_hashes(password)
            c.execute('SELECT * FROM users WHERE username =? AND password =?', (username, hashed_pswd))
            result = c.fetchone()
            if result:
                st.session_state['logged_in'] = True
                st.session_state['user'] = username
                st.success(f"স্বাগতম {username}!")
                st.rerun()
            else:
                st.error("ভুল ইউজারনেম অথবা পাসওয়ার্ড")

    elif choice == "Sign Up":
        st.subheader("নতুন একাউন্ট তৈরি করুন")
        new_user = st.text_input("ইউজারনেম দিন")
        new_password = st.text_input("পাসওয়ার্ড দিন", type='password')
        secret_code = st.text_input("সিক্রেট রেজিস্ট্রেশন কোড (যাতে সবাই একাউন্ট খুলতে না পারে)", type="password")
        
        if st.button("Sign Up"):
            # নিরাপত্তার জন্য একটি সিক্রেট কোড সেট করে দিন (যেমন: 'tcb2024')
            if secret_code == "tcb2024": 
                hashed_new_password = make_hashes(new_password)
                try:
                    c.execute('INSERT INTO users(username, password) VALUES (?,?)', (new_user, hashed_new_password))
                    conn.commit()
                    st.success("একাউন্ট তৈরি হয়েছে! এখন লগইন করুন।")
                except:
                    st.error("এই ইউজারনেমটি আগে থেকেই আছে।")
            else:
                st.error("ভুল সিক্রেট কোড! আপনি একাউন্ট খুলতে পারবেন না।")

else:
    # --- Main Website Dashboard (Logged In) ---
    st.sidebar.write(f"👤 ইউজার: {st.session_state['user']}")
    menu = ["বিতরণ সেন্টার", "মেম্বার লিস্ট (Search)", "নতুন এন্ট্রি / Excel", "ডেইলি রিপোর্ট"]
    choice = st.sidebar.radio("কাজ নির্বাচন করুন", menu)

    # 1. বিতরণ সেন্টার
    if choice == "বিতরণ সেন্টার":
        st.header("🛒 পণ্য বিতরণ বোর্ড")
        last_3 = st.text_input("কার্ডের শেষ ৩ ডিজিট দিয়ে সার্চ করুন", max_chars=3)
        
        if last_3:
            query = f"SELECT * FROM members WHERE tcb_no LIKE '%{last_3}' ORDER BY tcb_no ASC"
            df = pd.read_sql_query(query, conn)
            
            if not df.empty:
                for index, row in df.iterrows():
                    col1, col2, col3, col4 = st.columns([2,2,2,2])
                    col1.write(f"**{row['name']}**")
                    col2.write(f"ID: {row['tcb_no']}")
                    
                    if row['status'] == 'বাকি':
                        if col3.button("Confirm ✅", key=row['tcb_no']):
                            now = datetime.now().strftime("%Y-%m-%d %H:%M")
                            c.execute("UPDATE members SET status='পেয়েছেন', receive_date=? WHERE tcb_no=?", (now, row['tcb_no']))
                            conn.commit()
                            st.rerun()
                    else:
                        col3.write(f"✅ বিতরণকৃত ({row['receive_date']})")
                        if col4.button("Cancel ❌", key=f"undo_{row['tcb_no']}"):
                            c.execute("UPDATE members SET status='বাকি', receive_date=NULL WHERE tcb_no=?", (row['tcb_no'],))
                            conn.commit()
                            st.rerun()
            else:
                st.info("এই ৩ ডিজিট দিয়ে কোনো সদস্য পাওয়া যায়নি।")

    # 2. মেম্বার লিস্ট
    elif choice == "মেম্বার লিস্ট (Search)":
        st.header("🔍 মেম্বার ডাটাবেস")
        search = st.text_input("নাম/NID/TCB নম্বর দিয়ে সার্চ")
        df = pd.read_sql_query("SELECT * FROM members ORDER BY CAST(tcb_no AS INTEGER) ASC", conn)
        if search:
            df = df[df.apply(lambda r: search in str(r.values), axis=1)]
        st.dataframe(df, use_container_width=True)

    # 3. নতুন এন্ট্রি / Excel
    elif choice == "নতুন এন্ট্রি / Excel":
        tab1, tab2 = st.tabs(["ম্যানুয়াল এন্ট্রি", "Excel আপলোড"])
        with tab1:
            with st.form("entry"):
                n = st.text_input("নাম"); nid = st.text_input("NID")
                tcb = st.text_input("TCB নম্বর"); v = st.text_input("গ্রাম")
                w = st.text_input("ওয়ার্ড"); u = st.text_input("ইউনিয়ন")
                submit = st.form_submit_button("সেভ করুন")
                if submit:
                    try:
                        c.execute("INSERT INTO members (name, nid, tcb_no, village, ward, union_name) VALUES (?,?,?,?,?,?)", (n, nid, tcb, v, w, u))
                        conn.commit()
                        st.success("সফলভাবে যোগ হয়েছে!")
                    except: st.error("এই TCB নম্বর আগে থেকেই আছে!")
        with tab2:
            file = st.file_uploader("Excel ফাইল দিন", type=['xlsx'])
            if file:
                if st.button("সব ডাটা ইমপোর্ট করুন"):
                    df_excel = pd.read_excel(file)
                    df_excel.to_sql('members', conn, if_exists='append', index=False)
                    st.success("সব ডাটা যোগ হয়েছে!")

    # 4. রিপোর্ট
    elif choice == "ডেইলি রিপোর্ট":
        st.header("📊 আজকের বিতরণ রিপোর্ট")
        today = datetime.now().strftime("%Y-%m-%d")
        df_today = pd.read_sql_query(f"SELECT * FROM members WHERE receive_date LIKE '{today}%'", conn)
        st.metric("আজকে পণ্য নিয়েছে", f"{len(df_today)} জন")
        st.table(df_today[['tcb_no', 'name', 'village', 'receive_date']])

    if st.sidebar.button("Log Out"):
        st.session_state['logged_in'] = False
        st.rerun()
