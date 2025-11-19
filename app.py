import streamlit as st
import pandas as pd
import sqlite3
import os
import io
from datetime import datetime
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib import font_manager

# --- 1. ตั้งค่า Database (SQLite) ---
def init_db():
    # *** เปลี่ยนชื่อ DB เพื่อเริ่มกระดานใหม่ ***
    conn = sqlite3.connect('tennis_court_v2.db') 
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (phone TEXT PRIMARY KEY, name TEXT, line_id TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS bookings 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  user_phone TEXT, court_id TEXT, coach TEXT, 
                  date TEXT, time_slot TEXT, 
                  status TEXT DEFAULT 'pending', 
                  slip_image BLOB,
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
    # *** ต้องเปลี่ยนชื่อตรงนี้ให้ตรงกันด้วย ***
    return sqlite3.connect('tennis_court_v2.db')

# --- 2. Helper Functions ---
def compress_image(uploaded_file):
    if uploaded_file is not None:
        try:
            image = Image.open(uploaded_file)
            if image.mode in ("RGBA", "P"): 
                image = image.convert("RGB")
            image.thumbnail((800, 800)) 
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG', quality=70)
            return img_byte_arr.getvalue()
        except Exception as e:
            return None
    return None

def get_coach_list():
    conn = get_db_connection()
    try:
        coaches = pd.read_sql("SELECT name FROM coaches", conn)
        return coaches['name'].tolist()
    except:
        return []
    finally:
        conn.close()

# --- 3. Config ---
COURTS = {
    'A1': 'A1 (ผู้ใหญ่)', 'A2': 'A2 (ผู้ใหญ่)', 'A3': 'A3 (ผู้ใหญ่)',
    'B1': 'B1 (เด็ก)', 'B2': 'B2 (เด็ก)'
}
TIMES = [f"{h}:00" for h in range(6, 24)]

# --- 4. Main ---
def main():
    st.set_page_config(page_title="Tennis Booking", layout="wide")
    init_db()
    
    st.title("🎾 ระบบจองสนามเทนนิส")

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

    if menu == "สมัครสมาชิก":
        st.subheader("📝 สมัครสมาชิกใหม่")
        with st.form("register_form"):
            new_name = st.text_input("ชื่อเล่น/ชื่อจริง")
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
                        st.success("สมัครสำเร็จ!")
                    except sqlite3.IntegrityError:
                        st.error("เบอร์โทรนี้มีในระบบแล้ว")
                else:
                    st.warning("กรุณากรอกข้อมูลให้ครบ")

    elif menu == "จองสนาม":
        selected_date = st.date_input("เลือกวันที่", datetime.now())
        st.subheader(f"📅 ตารางสนามวันที่ {selected_date.strftime('%d/%m/%Y')}")
        st.caption("สีเหลือง = รออนุมัติ | สีแดง = จองแล้ว (อนุมัติแล้ว)")
        
        conn = get_db_connection()
        query = f"""
            SELECT b.*, u.name as user_name 
            FROM bookings b 
            LEFT JOIN users u ON b.user_phone = u.phone 
            WHERE date = '{selected_date}'
        """
        try:
            bookings = pd.read_sql(query, conn)
        except Exception:
            bookings = pd.DataFrame() # Fallback ถ้า DB มีปัญหา
        conn.close()

        schedule_data = {c_name: ["ว่าง"] * len(TIMES) for c_id, c_name in COURTS.items()}
        df_schedule = pd.DataFrame(schedule_data, index=TIMES)

        if not bookings.empty:
            for _, row in bookings.iterrows():
                c_name = COURTS[row['court_id']]
                t_idx = row['time_slot']
                
                display_text = f"คุณ{row['user_name']}"
                if row['coach'] != 'ไม่รับครู':
                    display_text += f"\n({row['coach']})"
                
                symbol = "✅ " if row['status'] == 'confirmed' else "⏳ "

                try:
                    df_schedule.at[t_idx, c_name] = symbol + display_text
                except:
                    pass
        
        def color_map(val):
            if '✅' in val: return 'background-color: #ffcccc'
            elif '⏳' in val: return 'background-color: #fff4cc'
            return 'background-color: #ccffcc'

        st.dataframe(df_schedule.style.applymap(color_map), use_container_width=True, height=600)

        if user_session:
            st.divider()
            st.info(f"ผู้จอง: {user_session[1]}")
            with st.form("booking_form"):
                c1, c2, c3 = st.columns(3)
                with c1: court_choice = st.selectbox("เลือกสนาม", list(COURTS.keys()), format_func=lambda x: COURTS[x])
                with c2: time_choice = st.selectbox("เลือกเวลา", TIMES)
                with c3: coach_choice = st.selectbox("เลือกครูฝึก", get_coach_list())
                
                st.markdown("---")
                st.write("📸 **หลักฐานการโอนเงิน**")
                uploaded_slip = st.file_uploader("อัปโหลดสลิป (รูปภาพ)", type=['png', 'jpg', 'jpeg'])

                submitted = st.form_submit_button("ส่งคำขอจอง")
                
                if submitted:
                    if uploaded_slip is None:
                        st.error("กรุณาแนบสลิปโอนเงิน")
                    else:
                        conn = get_db_connection()
                        exist = conn.execute("""
                            SELECT * FROM bookings 
                            WHERE date=? AND time_slot=? AND court_id=? AND status='confirmed'
                        """, (str(selected_date), time_choice, court_choice)).fetchone()
                        
                        if exist:
                            st.error("เวลานี้มีคนจองและอนุมัติไปแล้ว")
                        else:
                            compressed_slip = compress_image(uploaded_slip)
                            conn.execute("""
                                INSERT INTO bookings 
                                (user_phone, court_id, coach, date, time_slot, status, slip_image) 
                                VALUES (?,?,?,?,?,?,?)
                            """, (user_session[0], court_choice, coach_choice, str(selected_date), time_choice, 'pending', compressed_slip))
                            conn.commit()
                            st.success("ส่งคำขอเรียบร้อย รอแอดมินอนุมัติ")
                            st.rerun()
                        conn.close()

    elif menu == "Admin Dashboard":
        st.warning("🔒 ส่วนสำหรับผู้ดูแลระบบ")
        pwd = st.text_input("รหัสผ่าน Admin", type="password")
        
        if pwd == "1234":
            st.success("Access Granted")
            tab1, tab2, tab3, tab4 = st.tabs(["⏳ อนุมัติการจอง", "📸 Export รูปภาพ", "👥 จัดการครูฝึก", "📋 ประวัติทั้งหมด"])
            
            with tab1:
                st.header("รายการรออนุมัติ (Pending)")
                conn = get_db_connection()
                try:
                    pending_bookings = pd.read_sql("""
                        SELECT b.*, u.name as user_name, u.phone as user_contact 
                        FROM bookings b 
                        LEFT JOIN users u ON b.user_phone = u.phone 
                        WHERE status = 'pending'
                        ORDER BY date, time_slot
                    """, conn)
                except:
                    pending_bookings = pd.DataFrame()
                
                if pending_bookings.empty:
                    st.info("ไม่มีรายการรออนุมัติ")
                else:
                    for index, row in pending_bookings.iterrows():
                        with st.expander(f"{row['date']} | {row['time_slot']} | {COURTS[row['court_id']]} ({row['user_name']})"):
                            c1, c2 = st.columns([1, 2])
                            with c1:
                                if row['slip_image']: st.image(row['slip_image'], caption="หลักฐานการโอน", width=250)
                                else: st.warning("ไม่มีรูปสลิป")
                            with c2:
                                st.write(f"ลูกค้า: {row['user_name']} ({row['user_contact']})")
                                st.write(f"ครูฝึก: {row['coach']}")
                                cb1, cb2 = st.columns(2)
                                if cb1.button("✅ อนุมัติ", key=f"app_{row['id']}"):
                                    conn.execute("UPDATE bookings SET status='confirmed' WHERE id=?", (row['id'],))
                                    conn.commit()
                                    st.success("อนุมัติแล้ว")
                                    st.rerun()
                                if cb2.button("❌ ลบ", key=f"rej_{row['id']}"):
                                    conn.execute("DELETE FROM bookings WHERE id=?", (row['id'],))
                                    conn.commit()
                                    st.error("ลบแล้ว")
                                    st.rerun()
                conn.close()

            with tab2:
                export_date = st.date_input("เลือกวันที่ Export", datetime.now())
                if st.button("สร้างรูปตารางงาน"):
                    font_path = 'Sarabun-Regular.ttf'
                    if os.path.exists(font_path):
                        thai_font = font_manager.FontProperties(fname=font_path, size=12)
                        header_font = font_manager.FontProperties(fname=font_path, size=12, weight='bold')
                    else:
                        thai_font = None
                        header_font = None

                    conn = get_db_connection()
                    query = f"""
                        SELECT b.*, u.name as user_name 
                        FROM bookings b 
                        LEFT JOIN users u ON b.user_phone = u.phone 
                        WHERE date = '{export_date}' AND status = 'confirmed'
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
                                if info['coach'] != 'ไม่รับครู': txt += f"({info['coach']})"
                                row_data.append(txt)
                            else:
                                row_data.append("-")
                        cell_text.append(row_data)

                    fig, ax = plt.subplots(figsize=(12, 12))
                    ax.axis('off')
                    table = ax.table(cellText=cell_text, rowLabels=TIMES, colLabels=list(COURTS.values()), loc='center', cellLoc='center')
                    table.auto_set_font_size(False)
                    table.set_fontsize(12)
                    table.scale(1, 2.5)
                    for (row, col), cell in table.get_celld().items():
                        if thai_font:
                            if row == 0: cell.set_text_props(fontproperties=header_font, color='white')
                            else: cell.set_text_props(fontproperties=thai_font)
                        if row == 0:
                            cell.set_facecolor('#40466e')
                            cell.set_edgecolor('white')
                    st.pyplot(fig)

            with tab3:
                conn = get_db_connection()
                try:
                    coaches_df = pd.read_sql("SELECT * FROM coaches", conn)
                except: coaches_df = pd.DataFrame()
                conn.close()
                for index, row in coaches_df.iterrows():
                    c1, c2 = st.columns([3, 1])
                    c1.text(f"{index+1}. {row['name']}")
                    if st.button(f"ลบ", key=f"del_{row['id']}"):
                        conn = get_db_connection()
                        conn.execute("DELETE FROM coaches WHERE id = ?", (row['id'],))
                        conn.commit()
                        st.rerun()
                with st.form("add_coach"):
                    new_coach = st.text_input("ชื่อครูฝึก")
                    if st.form_submit_button("เพิ่ม"):
                        conn = get_db_connection()
                        conn.execute("INSERT INTO coaches (name) VALUES (?)", (new_coach,))
                        conn.commit()
                        st.rerun()

            with tab4:
                conn = get_db_connection()
                all_bookings = pd.read_sql("SELECT * FROM bookings ORDER BY date DESC", conn)
                st.dataframe(all_bookings)
                conn.close()

if __name__ == "__main__":
    main()
