import streamlit as st
import pandas as pd
import sqlite3
import hashlib
from datetime import datetime
import easyocr
import numpy as np
from PIL import Image
import re

# --- Database Setup ---
conn = sqlite3.connect('tcb_smart_system.db', check_same_thread=False)
c = conn.cursor()

def create_tables():
    c.execute('''CREATE TABLE IF NOT EXISTS members
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, nid TEXT, tcb_no TEXT UNIQUE, 
                  ward TEXT, village TEXT, status TEXT DEFAULT 'বাকি', receive_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)''')
    conn.commit()

create_tables()

# OCR Reader Initialize (Bangla & English)
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['bn', 'en'])

reader = load_ocr()

def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# --- UI Setup ---
st.set_page_config(page_title="TCB Smart Scanner", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🔐 TCB লগইন")
    choice = st.sidebar.selectbox("মেনু", ["Login", "Sign Up"])
    if choice == "Login":
        u = st.text_input("ইউজারনেম"); p = st.text_input("পাসওয়ার্ড", type='password')
        if st.button("Login"):
            c.execute('SELECT * FROM users WHERE username =? AND password =?', (u, make_hashes(p)))
            if c.fetchone():
                st.session_state['logged_in'] = True
                st.session_state['user'] = u
                st.rerun()
            else: st.error("ভুল তথ্য!")
    elif choice == "Sign Up":
        new_u = st.text_input("নতুন ইউজারনেম"); new_p = st.text_input("পাসওয়ার্ড", type='password')
        code = st.text_input("সিক্রেট কোড (tcb2024)", type='password')
        if st.button("Sign Up") and code == "tcb2024":
            c.execute('INSERT INTO users VALUES (?,?)', (new_u, make_hashes(new_p)))
            conn.commit(); st.success("একাউন্ট তৈরি হয়েছে!")

else:
    st.sidebar.write(f"👤 {st.session_state['user']}")
    menu = ["কার্ড স্ক্যানার (OCR)", "পণ্য বিতরণ", "মেম্বার লিস্ট", "Excel আপলোড"]
    choice = st.sidebar.radio("কাজ নির্বাচন করুন", menu)

    # --- 1. কার্ড স্ক্যানার (ছবি থেকে ডাটা) ---
    if choice == "কার্ড স্ক্যানার (OCR)":
        st.header("📸 কার্ডের ছবি তুলে তথ্য যোগ করুন")
        img_file = st.camera_input("কার্ডের ছবি তুলুন") # সরাসরি মোবাইল ক্যামেরা ওপেন হবে
        
        if img_file:
            image = Image.open(img_file)
            st.image(image, caption="স্ক্যান করা হচ্ছে...", width=300)
            
            with st.spinner("ছবি থেকে তথ্য পড়া হচ্ছে... অপেক্ষা করুন।"):
                # OCR দিয়ে লেখা বের করা
                results = reader.readtext(np.array(image), detail=0)
                all_text = " ".join(results)
                
                # কিছু টেক্সট ফিল্টারিং (সহজ করার জন্য)
                # TCB নম্বর সাধারণত ১০-১৫ ডিজিটের হয়, আমরা সেটি খোঁজার চেষ্টা করি
                tcb_numbers = re.findall(r'\d{10,20}', all_text)
                found_tcb = tcb_numbers[0] if tcb_numbers else ""
                
                st.subheader("যাচাই করুন ও সেভ করুন")
                with st.form("scan_form"):
                    name = st.text_input("নাম (ছবি থেকে পাওয়া)", value="")
                    tcb_no = st.text_input("TCB নম্বর", value=found_tcb)
                    village = st.text_input("গ্রাম")
                    ward = st.text_input("ওয়ার্ড")
                    nid = st.text_input("NID নম্বর")
                    
                    if st.form_submit_button("ডাটাবেসে সেভ করুন"):
                        if tcb_no:
                            try:
                                c.execute("INSERT INTO members (name, nid, tcb_no, village, ward) VALUES (?,?,?,?,?)", 
                                          (name, nid, tcb_no, village, ward))
                                conn.commit()
                                st.success(f"সদস্য {tcb_no} সফলভাবে যুক্ত হয়েছে!")
                            except: st.error("এই TCB নম্বরটি অলরেডি আছে!")
                        else: st.error("TCB নম্বর পাওয়া যায়নি, নিজে লিখে দিন।")

    # --- 2. পণ্য বিতরণ (Last 3 Digits) ---
    elif choice == "পণ্য বিতরণ":
        st.header("🚚 পণ্য বিতরণ (শেষ ৩ ডিজিট)")
        last_3 = st.text_input("কার্ডের শেষ ৩ ডিজিট দিন", max_chars=3)
        
        if last_3:
            query = f"SELECT * FROM members WHERE tcb_no LIKE '%{last_3}'"
            df = pd.read_sql_query(query, conn)
            
            if not df.empty:
                for idx, row in df.iterrows():
                    col1, col2, col3 = st.columns([3,2,2])
                    col1.write(f"**{row['name']}** (ID: {row['tcb_no']})")
                    if row['status'] == 'বাকি':
                        if col2.button("পণ্য পেয়েছে ✅", key=row['tcb_no']):
                            c.execute("UPDATE members SET status='পেয়েছেন', receive_date=? WHERE tcb_no=?", 
                                      (datetime.now().strftime("%Y-%m-%d %H:%M"), row['tcb_no']))
                            conn.commit(); st.rerun()
                    else:
                        col2.write(f"✅ বিতরণকৃত ({row['receive_date']})")
                        if col3.button("Cancel ❌", key=f"un_{row['tcb_no']}"):
                            c.execute("UPDATE members SET status='বাকি', receive_date=NULL WHERE tcb_no=?", (row['tcb_no'],))
                            conn.commit(); st.rerun()
            else: st.warning("কোনো সদস্য পাওয়া যায়নি!")

    # --- মেম্বার লিস্ট ও রিপোর্ট ---
    elif choice == "মেম্বার লিস্ট":
        st.header("📋 সব সদস্যের তালিকা")
        df = pd.read_sql_query("SELECT * FROM members ORDER BY tcb_no ASC", conn)
        st.dataframe(df)
        
    elif choice == "Excel আপলোড":
        file = st.file_uploader("Excel ফাইল দিন", type=['xlsx'])
        if file and st.button("আপলোড"):
            df_ex = pd.read_excel(file)
            df_ex.to_sql('members', conn, if_exists='append', index=False)
            st.success("সব ডাটা যোগ হয়েছে!")
