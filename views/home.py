import streamlit as st

# 裏方部隊（utils/g_sheets.py）から必要な関数を呼び出します
from utils.g_sheets import (
    load_seating_data,
    load_board_message,
    save_board_message,
    get_my_messages,   # 追加
    get_all_accounts   # 追加
)

def render_home_page():
    st.header("📢 ホーム・連絡掲示板")
    
    # ==========================================
    # 🌟 個別メッセージエリア
    # ==========================================
    st.subheader("💌 あなた宛てのメッセージ")
    
    my_user_id = st.session_state.get('user_id')
    if my_user_id:
        messages = get_my_messages(my_user_id)
        
        if not messages:
            st.info("現在、新しいメッセージはありません。")
        else:
            raw_accounts = get_all_accounts()
            # IDを小文字に統一し、余計な空白を消す
            safe_accounts = {str(k).strip().lower(): v for k, v in raw_accounts.items()}
            
            with st.container(height=350):
                for msg in messages:
                    date_str = msg.get("送信日時", "")
                    
                    # 👇 おそらくこの行が消えてしまっていました！
                    raw_sender_id = msg.get("送信者ID", "") 
                    text = msg.get("メッセージ内容", "")
                    
                    sender_id_clean = str(raw_sender_id).strip().lower()
                    
                    # 講師名を取得
                    account_info = safe_accounts.get(sender_id_clean, {})
                    sender_name = account_info.get("講師名")
                    role = account_info.get("権限", "")

                    if sender_id_clean == "admin":
                        sender_name = "教室長"
                    elif sender_id_clean == "owner":
                        sender_name = "社長"
                    elif sender_id_clean == "head_teacher":
                        sender_name = "主任講師"
                    elif base_name:
                        # 権限に応じて後ろにつける敬称を変える
                        if role == "admin":
                            sender_name = f"{base_name} 教室長"
                        elif role == "owner":
                            sender_name = f"{base_name} 社長"
                        elif role == "head_teacher":
                            sender_name = f"{base_name} 主任"
                        else:
                            sender_name = f"{base_name} 先生"
                    else:
                        sender_name = f"ID:{raw_sender_id} (名前未設定)"

                    
                    
                    with st.chat_message("user"):
                        st.markdown(f"**{sender_name}** 🕒 {date_str}")
                        st.write(text)
    else:
        st.warning("⚠️ ユーザー情報が取得できません。一度ログアウトして入り直してください。")
        
    st.divider()
    
    # ==========================================
    # 🌟 掲示板エリア
    # ==========================================
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

    st.divider() 
    
    # ==========================================
    # 🌟 座席表エリア
    # ==========================================
    st.subheader("🗺️ 現在の教室状況 (座席マップ)")
    
    try:
        seating_data = load_seating_data()
        num_booths = len(seating_data)
        
        if num_booths == 0:
             st.info("座席データがまだありません。左のメニューから登録してください。")
        else:
            for i in range(0, num_booths, 3):
                cols = st.columns(3)
                for j in range(3):
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