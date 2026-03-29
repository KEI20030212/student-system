import streamlit as st

# 裏方部隊から、座席データを読み書きする関数などを呼び出します
from utils.g_sheets import (
    get_all_student_names,
    load_seating_data,
    save_seating_data
)

def render_attendance_seat_page():
    st.header("✅ 本日の出欠・座席管理")
    st.write("今日の授業の座席割り当てと、生徒の出欠状況を一画面で管理します。")
    
    student_names = get_all_student_names()
    if not student_names: return
    
    seating_data = load_seating_data()
    
    if 'num_booths' not in st.session_state:
        st.session_state['num_booths'] = max(6, len(seating_data))

    st.subheader("🗺️ 教室レイアウト (座席表)")

    col_add, col_sub, _ = st.columns([1, 1, 3])
    with col_add:
        if st.button("➕ ブースを追加", use_container_width=True):
            st.session_state['num_booths'] += 1
            st.rerun()
    with col_sub:
        if st.button("➖ ブースを減らす", use_container_width=True):
            if st.session_state['num_booths'] > 1:
                st.session_state['num_booths'] -= 1
                st.rerun()
            else:
                st.warning("これ以上減らせません！")

    new_seating = {}
    cols = st.columns(3) 
    
    for i in range(st.session_state['num_booths']):
        booth_name = f"ブース{i+1}"
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"**🪑 {booth_name}**")
                
                current_info = seating_data.get(booth_name, {"生徒名": "-- 空席 --", "状態": "出席"})
                current_seat = current_info["生徒名"]
                current_status = current_info["状態"]
                
                options = ["-- 空席 --"] + student_names
                
                new_occupant = st.selectbox(
                    "生徒名", 
                    options, 
                    index=options.index(current_seat) if current_seat in options else 0, 
                    key=f"seat_{i}"
                )
                
                if new_occupant != "-- 空席 --":
                    status_options = ["出席", "遅刻", "欠席連絡あり"]
                    new_status = st.radio(
                        "状態", 
                        status_options, 
                        index=status_options.index(current_status) if current_status in status_options else 0,
                        horizontal=True, 
                        key=f"status_{i}"
                    )
                else:
                    new_status = "出席" 
                    
                new_seating[booth_name] = {"生徒名": new_occupant, "状態": new_status}
    
    st.divider()
    if st.button("💾 本日の座席表を確定・共有する", type="primary", use_container_width=True):
        with st.spinner('スプレッドシートに保存中...'):
            save_seating_data(new_seating)
            st.session_state['num_booths'] = len(new_seating)
            st.success(f"✨ 全 {len(new_seating)} ブースの座席表をクラウドに保存しました！")
            st.rerun()
