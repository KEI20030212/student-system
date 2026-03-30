import streamlit as st

# 裏方部隊（utils/g_sheets.py）から必要な関数を呼び出します
# ※今はまだ app.py にある関数（load_board_messageなど）も、
# 次のステップで utils に移動させるので、先取りしてここで import しておきます！
from utils.g_sheets import (
    load_seating_data,
    load_board_message,
    save_board_message
)

def render_home_page():
    st.header("📢 ホーム・連絡掲示板")
    st.subheader("🗺️ 現在の教室状況 (座席マップ)")
    
    try:
        seating_data = load_seating_data()
        num_booths = len(seating_data)
        
        if num_booths == 0:
             st.info("座席データがまだありません。左のメニューから登録してください。")
        else:
            for i in range(0, num_booths, 3):
                cols = st.columns(3) # 1行ごとに3つの列を作る！
                
                for j in range(3):
                    # ブースの数が半端な場合（例：10個）のエラーを防ぐ
                    if i + j < num_booths:
                        booth_index = i + j
                        booth_name = f"ブース{booth_index+1}"
                        info = seating_data.get(booth_name, {"生徒名": "-- 空席 --", "状態": "出席"})
                        student = info.get("生徒名", "-- 空席 --")
                        status = info.get("状態", "出席")
                        
                        with cols[j]:
                            with st.container(border=True):
                                st.markdown(f"**🪑 {booth_name}**")
                                if student == "-- 空席 --":
                                    st.markdown("<div style='text-align:center; color:#ccc; padding:10px;'>-- 空席 --</div>", unsafe_allow_html=True)
                                else:
                                    if status == "出席": status_html = "<span style='color:#28a745; font-weight:bold;'>🟢 出席</span>"
                                    elif status == "遅刻": status_html = "<span style='color:#ffc107; font-weight:bold;'>🟡 遅刻</span>"
                                    else: status_html = "<span style='color:#dc3545; font-weight:bold;'>🔴 欠席</span>"
                                    st.markdown(f"<div style='text-align:center; padding:5px; font-weight:bold; font-size:1.2em; color:#1E90FF;'>{student}</div>", unsafe_allow_html=True)
                                    st.markdown(f"<div style='text-align:center; font-size:0.9em; padding-bottom:5px;'>{status_html}</div>", unsafe_allow_html=True)
    except Exception as e:
        st.error("データの読み込みに失敗しました。")

    st.divider()
    
    st.subheader("📌 講師向け 連絡事項・掲示板")
    current_message = load_board_message()
    st.info(current_message)
    
    if st.session_state.get('role') == 'admin':
        with st.expander("✏️ 掲示板を編集する (教室長のみ)"):
            new_msg = st.text_area("先生たちへのメッセージを入力", value=current_message, height=150)
            if st.button("💾 掲示板を更新", type="primary"):
                save_board_message(new_msg)
                st.success("掲示板を更新しました！全先生のホーム画面に反映されます。")
                st.rerun()
