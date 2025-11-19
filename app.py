import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns

# --- 1. ตั้งค่า Database (SQLite) ---
def init_db():
    conn = sqlite3.connect('tennis_court.db')
    c = conn.cursor()
    # ตารางสมาชิก
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (phone TEXT PRIMARY KEY, name TEXT, line_id TEXT)''')
    # ตารางการจอง
    c.execute('''CREATE TABLE IF NOT EXISTS bookings 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  user_phone TEXT, court_id TEXT, coach TEXT, 
                  date TEXT, time_slot TEXT, 
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def get_db_connection():
    return sqlite3.connect('tennis_court.db')

# --- 2. ตั้งค่า Config สนาม ---
COURTS = {
    'A1': 'A1 (ผู้ใหญ่)', 'A2': 'A2 (ผู้ใหญ่)', 'A3': 'A3 (ผู้ใหญ่)',
    'B1': 'B1 (เด็ก)', 'B2': 'B2 (เด็ก)'
}
TIMES = [f"{h}:00" for h in range(6, 24)] # 6.00 - 23.00
COACHES = ['ไม่รับครู', 'ครูสมชาย', 'ครูสมหญิง', 'ครูจอห์น']

# --- 3. ฟังก์ชันหลัก ---
def main():
    st.set_page_config(page_title="Tennis Booking", layout="wide")
    init_db()
    
    st.title("🎾 ระบบจองสนามเทนนิส")

    # Sidebar: เข้าสู่ระบบ / สมัครสมาชิก
    with st.sidebar:
        st.header("สมาชิก")
        menu = st.radio("เลือกรายการ", ["จองสนาม", "สมัครสมาชิก", "Admin Dashboard"])
        
        user_session = None
        if menu == "จองสนาม":
            phone_input = st.text_input("เบอร์โทรศัพท์ (เพื่อเข้าสู่ระบบ)")
            if phone_input:
                conn = get_db_connection()
                user = conn.execute('SELECT * FROM users WHERE phone = ?', (phone_input,)).fetchone()
                conn.close()
                if user:
                    st.success(f"สวัสดีคุณ {user[1]}")
                    user_session = user
                else:
                    st.error("ไม่พบข้อมูลสมาชิก กรุณาสมัครก่อน")

    # --- ส่วนที่ 1: สมัครสมาชิก ---
    if menu == "สมัครสมาชิก":
        st.subheader("📝 สมัครสมาชิกใหม่")
        with st.form("register_form"):
            new_name = st.text_input("ชื่อ-นามสกุล")
            new_phone = st.text_input("เบอร์โทรศัพท์")
            new_line = st.text_input("Line ID")
            submitted = st.form_submit_button("ยืนยันการสมัคร")
            
            if submitted:
                if new_name and new_phone:
                    try:
                        conn = get_db_connection()
                        conn.execute('INSERT INTO users VALUES (?,?,?)', (new_phone, new_name, new_line))
                        conn.commit()
                        conn.close()
                        st.success("สมัครสมาชิกสำเร็จ! ไปที่เมนู 'จองสนาม' เพื่อเริ่มใช้งาน")
                    except sqlite3.IntegrityError:
                        st.error("เบอร์โทรนี้มีในระบบแล้ว")
                else:
                    st.warning("กรุณากรอกข้อมูลให้ครบ")

    # --- ส่วนที่ 2: หน้าจองสนาม (ตาราง) ---
    elif menu == "จองสนาม":
        selected_date = st.date_input("เลือกวันที่", datetime.now())
        st.subheader(f"ตารางสนามวันที่ {selected_date.strftime('%d/%m/%Y')}")
        
        # โหลดข้อมูลการจอง
        conn = get_db_connection()
        bookings = pd.read_sql(f"SELECT * FROM bookings WHERE date = '{selected_date}'", conn)
        conn.close()

        # สร้างตาราง Grid แสดงผล
        schedule_data = {c_name: ["ว่าง"] * len(TIMES) for c_id, c_name in COURTS.items()}
        df_schedule = pd.DataFrame(schedule_data, index=TIMES)

        # เติมข้อมูลที่ไม่ว่าง
        for _, row in bookings.iterrows():
            c_name = COURTS[row['court_id']]
            t_idx = row['time_slot']
            status_text = "❌ จองแล้ว"
            if row['coach'] != 'ไม่รับครู':
                status_text += f"\n({row['coach']})"
            
            try:
                df_schedule.at[t_idx, c_name] = status_text
            except:
                pass

        # แสดงตารางสีสัน
        st.dataframe(df_schedule.style.applymap(
            lambda x: 'background-color: #ffcccc' if 'จองแล้ว' in x else 'background-color: #ccffcc'
        ), use_container_width=True, height=600)

        # Form การจอง
        if user_session:
            st.divider()
            st.info(f"ผู้จอง: {user_session[1]}")
            c1, c2, c3 = st.columns(3)
            with c1:
                court_choice = st.selectbox("เลือกสนาม", list(COURTS.keys()), format_func=lambda x: COURTS[x])
            with c2:
                time_choice = st.selectbox("เลือกเวลา", TIMES)
            with c3:
                coach_choice = st.selectbox("เลือกครูฝึก", COACHES)
            
            if st.button("ยืนยันการจอง"):
                conn = get_db_connection()
                # เช็คว่าว่างไหม
                exist = conn.execute("SELECT * FROM bookings WHERE date=? AND time_slot=? AND court_id=?", 
                                     (str(selected_date), time_choice, court_choice)).fetchone()
                
                if exist:
                    st.error("เวลานี้สนามนี้ไม่ว่างแล้วครับ")
                else:
                    conn.execute("INSERT INTO bookings (user_phone, court_id, coach, date, time_slot) VALUES (?,?,?,?,?)",
                                 (user_session[0], court_choice, coach_choice, str(selected_date), time_choice))
                    conn.commit()
                    st.success("จองสำเร็จ!")
                    st.rerun() # <--- แก้ตรงนี้เป็น st.rerun() แล้วครับ
                conn.close()

    # --- ส่วนที่ 3: Admin Dashboard ---
    elif menu == "Admin Dashboard":
        st.warning("ส่วนสำหรับผู้ดูแลระบบ")
        pwd = st.text_input("รหัสผ่าน Admin", type="password")
        
        if pwd == "1234":
            st.success("Login สำเร็จ")
            
            export_date = st.date_input("เลือกวันที่ต้องการ Export รูปภาพ", datetime.now())
            
            if st.button("สร้างรูปภาพตารางงาน"):
                conn = get_db_connection()
                bookings_df = pd.read_sql(f"SELECT * FROM bookings WHERE date = '{export_date}'", conn)
                conn.close()
                
                fig, ax = plt.subplots(figsize=(10, 6))
                data_matrix = []
                for t in TIMES:
                    row = []
                    for c_id in COURTS.keys():
                        found = bookings_df[(bookings_df['time_slot'] == t) & (bookings_df['court_id'] == c_id)]
                        if not found.empty:
                            val = 1
                        else:
                            val = 0
                        row.append(val)
                    data_matrix.append(row)
                
                sns.heatmap(data_matrix, annot=True, fmt="d", cmap="RdYlGn_r", 
                            xticklabels=list(COURTS.values()), yticklabels=TIMES, cbar=False, ax=ax)
                
                plt.title(f"Schedule: {export_date}")
                st.pyplot(fig)
                st.caption("0 = ว่าง (เขียว), 1 = จองแล้ว (แดง)")
                
            st.subheader("ประวัติการจองทั้งหมด (Database)")
            conn = get_db_connection()
            all_bookings = pd.read_sql("SELECT * FROM bookings ORDER BY date DESC, time_slot ASC", conn)
            st.dataframe(all_bookings)
            conn.close()

if __name__ == "__main__":
    main()
