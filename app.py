import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib import font_manager

# --- 1. ตั้งค่า Database (SQLite) ---
def init_db():
    conn = sqlite3.connect('tennis_court.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (phone TEXT PRIMARY KEY, name TEXT, line_id TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bookings 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  user_phone TEXT, court_id TEXT, coach TEXT, 
                  date TEXT, time_slot TEXT, 
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS coaches 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)''')
    
    c.execute('SELECT count(*) FROM coaches')
    if c.fetchone()[0] == 0:
        default_coaches = [('ไม่รับครู',), ('ครูสมชาย',), ('ครูสมหญิง',), ('ครูจอห์น',)]
        c.executemany('INSERT INTO coaches (name) VALUES (?)', default_coaches)
        
    conn.commit()
    conn.close()

def get_db_connection():
    return sqlite3.connect('tennis_court.db')

# --- 2. Helper Functions ---
def get_coach_list():
    conn = get_db_connection()
    coaches = pd.read_sql("SELECT name FROM coaches", conn)
    conn.close()
    return coaches['name'].tolist()

# --- 3. ตั้งค่า Config สนาม ---
COURTS = {
    'A1': 'A1 (ผู้ใหญ่)', 'A2': 'A2 (ผู้ใหญ่)', 'A3': 'A3 (ผู้ใหญ่)',
    'B1': 'B1 (เด็ก)', 'B2': 'B2 (เด็ก)'
}
TIMES = [f"{h}:00" for h in range(6, 24)]

# --- 4. ฟังก์ชันหลัก ---
def main():
    st.set_page_config(page_title="Tennis Booking", layout="wide")
    init_db()
    
    st.title("🎾 ระบบจองสนามเทนนิส")

    # Sidebar
    with st.sidebar:
        st.header("เมนูหลัก")
        menu = st.radio("เลือกรายการ", ["จองสนาม", "สมัครสมาชิก", "Admin Dashboard"])
        
        user_session = None
        if menu == "จองสนาม":
            st.divider()
            phone_input = st.text_input("เบอร์โทรศัพท์ (เพื่อเข้าสู่ระบบ)")
            if phone_input:
                conn = get_db_connection()
                user = conn.execute('SELECT * FROM users WHERE phone = ?', (phone_input,)).fetchone()
                conn.close()
                if user:
                    st.success(f"ยินดีต้อนรับ: {user[1]}")
                    user_session = user
                else:
                    st.error("ไม่พบข้อมูลสมาชิก")

    # --- ส่วนที่ 1: สมัครสมาชิก ---
    if menu == "สมัครสมาชิก":
        st.subheader("📝 สมัครสมาชิกใหม่")
        with st.form("register_form"):
            new_name = st.text_input("ชื่อเล่น/ชื่อจริง (สำหรับการแสดงผล)")
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
                        st.success("สมัครสำเร็จ! ไปที่เมนู 'จองสนาม' ได้เลย")
                    except sqlite3.IntegrityError:
                        st.error("เบอร์โทรนี้มีในระบบแล้ว")
                else:
                    st.warning("กรุณากรอกข้อมูลให้ครบ")

    # --- ส่วนที่ 2: จองสนาม ---
    elif menu == "จองสนาม":
        selected_date = st.date_input("เลือกวันที่", datetime.now())
        st.subheader(f"📅 ตารางสนามวันที่ {selected_date.strftime('%d/%m/%Y')}")
        
        conn = get_db_connection()
        query = f"""
            SELECT b.*, u.name as user_name 
            FROM bookings b 
            LEFT JOIN users u ON b.user_phone = u.phone 
            WHERE date = '{selected_date}'
        """
        bookings = pd.read_sql(query, conn)
        conn.close()

        schedule_data = {c_name: ["ว่าง"] * len(TIMES) for c_id, c_name in COURTS.items()}
        df_schedule = pd.DataFrame(schedule_data, index=TIMES)

        for _, row in bookings.iterrows():
            c_name = COURTS[row['court_id']]
            t_idx = row['time_slot']
            display_text = f"คุณ{row['user_name']}"
            if row['coach'] != 'ไม่รับครู':
                display_text += f"\n({row['coach']})"
            try:
                df_schedule.at[t_idx, c_name] = "❌ " + display_text
            except:
                pass

        st.dataframe(df_schedule.style.applymap(
            lambda x: 'background-color: #ffcccc' if '❌' in x else 'background-color: #ccffcc'
        ), use_container_width=True, height=600)

        if user_session:
            st.divider()
            st.info(f"ผู้จอง: {user_session[1]}")
            c1, c2, c3 = st.columns(3)
            with c1:
                court_choice = st.selectbox("เลือกสนาม", list(COURTS.keys()), format_func=lambda x: COURTS[x])
            with c2:
                time_choice = st.selectbox("เลือกเวลา", TIMES)
            with c3:
                current_coaches = get_coach_list()
                coach_choice = st.selectbox("เลือกครูฝึก", current_coaches)
            
            if st.button("ยืนยันการจอง"):
                conn = get_db_connection()
                exist = conn.execute("SELECT * FROM bookings WHERE date=? AND time_slot=? AND court_id=?", 
                                     (str(selected_date), time_choice, court_choice)).fetchone()
                if exist:
                    st.error("ไม่ว่างแล้วครับ")
                else:
                    conn.execute("INSERT INTO bookings (user_phone, court_id, coach, date, time_slot) VALUES (?,?,?,?,?)",
                                 (user_session[0], court_choice, coach_choice, str(selected_date), time_choice))
                    conn.commit()
                    st.success("จองสำเร็จ!")
                    st.rerun()
                conn.close()

    # --- ส่วนที่ 3: Admin Dashboard ---
    elif menu == "Admin Dashboard":
        st.warning("🔒 ส่วนสำหรับผู้ดูแลระบบ")
        pwd = st.text_input("รหัสผ่าน Admin", type="password")
        
        if pwd == "1234":
            st.success("Access Granted")
            
            tab1, tab2, tab3 = st.tabs(["📸 Export รูปภาพ", "👥 จัดการครูฝึก", "📋 ประวัติการจอง"])
            
            with tab1:
                export_date = st.date_input("เลือกวันที่ Export", datetime.now())
                if st.button("สร้างรูปตารางงาน"):
                    
                    # --- Load Thai Font ---
                    font_path = 'Sarabun-Regular.ttf' # ชื่อไฟล์ที่อัปโหลด
                    if os.path.exists(font_path):
                        thai_font = font_manager.FontProperties(fname=font_path, size=12)
                        header_font = font_manager.FontProperties(fname=font_path, size=12, weight='bold')
                    else:
                        st.error("ไม่พบไฟล์ฟอนต์ Sarabun-Regular.ttf ในระบบ กรุณาอัปโหลดขึ้น GitHub")
                        thai_font = None
                        header_font = None

                    conn = get_db_connection()
                    query = f"""
                        SELECT b.*, u.name as user_name 
                        FROM bookings b 
                        LEFT JOIN users u ON b.user_phone = u.phone 
                        WHERE date = '{export_date}'
                    """
                    bookings_df = pd.read_sql(query, conn)
                    conn.close()

                    cell_text = []
                    for t in TIMES:
                        row_data = []
                        for c_id, c_name in COURTS.items():
                            found = bookings_df[(bookings_df['time_slot'] == t) & (bookings_df['court_id'] == c_id)]
                            if not found.empty:
                                info = found.iloc[0]
                                txt = f"{info['user_name']}\n"
                                if info['coach'] != 'ไม่รับครู':
                                    txt += f"({info['coach']})"
                                row_data.append(txt)
                            else:
                                row_data.append("-")
                        cell_text.append(row_data)

                    fig, ax = plt.subplots(figsize=(12, 12))
                    ax.axis('off')
                    
                    table = ax.table(
                        cellText=cell_text,
                        rowLabels=TIMES,
                        colLabels=list(COURTS.values()),
                        loc='center',
                        cellLoc='center'
                    )
                    
                    table.auto_set_font_size(False)
                    table.set_fontsize(12)
                    table.scale(1, 2.5)
                    
                    # จัดฟอนต์ไทยและสี
                    for (row, col), cell in table.get_celld().items():
                        # ถ้ามีฟอนต์ไทย ให้ใช้ฟอนต์ไทย
                        if thai_font:
                            if row == 0:
                                cell.set_text_props(fontproperties=header_font, color='white')
                            else:
                                cell.set_text_props(fontproperties=thai_font)
                        
                        if row == 0:
                            cell.set_facecolor('#40466e')
                            cell.set_edgecolor('white')
                    
                    st.pyplot(fig)
                    st.caption(f"ตารางงานวันที่ {export_date}")

            with tab2:
                st.subheader("รายชื่อครูฝึกปัจจุบัน")
                conn = get_db_connection()
                coaches_df = pd.read_sql("SELECT * FROM coaches", conn)
                conn.close()
                for index, row in coaches_df.iterrows():
                    c1, c2 = st.columns([3, 1])
                    c1.text(f"{index+1}. {row['name']}")
                    if st.button(f"ลบ", key=f"del_{row['id']}"):
                        conn = get_db_connection()
                        conn.execute("DELETE FROM coaches WHERE id = ?", (row['id'],))
                        conn.commit()
                        conn.close()
                        st.rerun()
                
                st.divider()
                st.subheader("เพิ่มครูฝึกใหม่")
                with st.form("add_coach"):
                    new_coach_name = st.text_input("ชื่อครูฝึก")
                    if st.form_submit_button("เพิ่มรายชื่อ"):
                        if new_coach_name:
                            conn = get_db_connection()
                            conn.execute("INSERT INTO coaches (name) VALUES (?)", (new_coach_name,))
                            conn.commit()
                            conn.close()
                            st.success("เพิ่มเรียบร้อย")
                            st.rerun()

            with tab3:
                conn = get_db_connection()
                all_bookings = pd.read_sql("SELECT * FROM bookings ORDER BY date DESC", conn)
                st.dataframe(all_bookings)
                conn.close()

if __name__ == "__main__":
    main()
