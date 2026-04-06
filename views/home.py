import streamlit as st

# 裏方部隊（すべての関数を1つにまとめてインポートします）
from utils.g_sheets import (
    load_board_message,
    save_board_message,
    get_my_messages,
    get_all_accounts,
    mark_messages_as_read,
    get_all_student_names,
    load_seating_data,
    save_seating_data
)

def render_home_page():
    st.header("📢 ホーム・連絡掲示板")
    
    user_role = st.session_state.get('role', '')
    
    # ==========================================
    # 🌟 個別メッセージエリア (変更なし)
    # ==========================================
    st.subheader("💌 あなた宛てのメッセージ")
    
    my_user_id = st.session_state.get('user_id')
    if my_user_id:
        messages = get_my_messages(my_user_id)
        
        if not messages:
            st.info("現在、新しいメッセージはありません。")
        else:
            unread_msgs = [m for m in messages if m.get("状態", "未読") in ["未読", "False"]]
            read_msgs = [m for m in messages if m not in unread_msgs]
            
            if unread_msgs:
                mark_messages_as_read(my_user_id)
                get_my_messages.clear()
            
            raw_accounts = get_all_accounts()
            safe_accounts = {str(k).strip().lower(): v for k, v in raw_accounts.items()}
            
            # 📩 新着メッセージ枠
            if unread_msgs:
                st.markdown("##### 📩 新着メッセージ")
                for msg in unread_msgs:
                    date_str = msg.get("送信日時", "")
                    raw_sender_id = msg.get("送信者ID", "")
                    text = msg.get("メッセージ内容", "")
                    sender_id_clean = str(raw_sender_id).strip().lower()
                    
                    account_info = safe_accounts.get(sender_id_clean, {})
                    base_name = account_info.get("講師名")
                    role = str(account_info.get("権限", "")).strip().lower()
                    
                    if sender_id_clean == "admin": sender_name = "教室長"
                    elif sender_id_clean == "owner": sender_name = "社長"
                    elif sender_id_clean == "head_teacher": sender_name = "主任講師"
                    elif base_name:
                        if role == "admin": sender_name = f"{base_name} 教室長"
                        elif role == "owner": sender_name = f"{base_name} 社長"
                        elif role == "head_teacher": sender_name = f"{base_name} 主任講師"
                        else: sender_name = f"{base_name} 先生"
                    else: sender_name = f"ID:{raw_sender_id} (名前未設定)"
                    
                    with st.chat_message("assistant"):
                        st.markdown(f"**{sender_name}** からのメッセージ 🕒 {date_str} 🔴 **New!**")
                        formatted_text = text.replace('\n', '  \n')
                        st.write(formatted_text)
            
            # ✅ 過去のメッセージ枠（検索機能つき）
            if read_msgs:
                is_expanded = len(unread_msgs) == 0
                
                with st.expander("✅ 過去のメッセージ (既読) を見る", expanded=is_expanded):
                    search_query = st.text_input("🔍 受信メッセージを検索", placeholder="送り主の名前や、メッセージのキーワードを入力...")
                    
                    with st.container(height=300):
                        found_count = 0
                        for msg in read_msgs:
                            date_str = msg.get("送信日時", "")
                            raw_sender_id = msg.get("送信者ID", "")
                            text = msg.get("メッセージ内容", "")
                            sender_id_clean = str(raw_sender_id).strip().lower()
                            
                            account_info = safe_accounts.get(sender_id_clean, {})
                            base_name = account_info.get("講師名")
                            role = str(account_info.get("権限", "")).strip().lower()
                            
                            if sender_id_clean == "admin": sender_name = "教室長"
                            elif sender_id_clean == "owner": sender_name = "社長"
                            elif sender_id_clean == "head_teacher": sender_name = "主任講師"
                            elif base_name:
                                if role == "admin": sender_name = f"{base_name} 教室長"
                                elif role == "owner": sender_name = f"{base_name} 社長"
                                elif role == "head_teacher": sender_name = f"{base_name} 主任講師"
                                else: sender_name = f"{base_name} 先生"
                            else: sender_name = f"ID:{raw_sender_id} (名前未設定)"
                            
                            if search_query:
                                if search_query.lower() not in text.lower() and search_query.lower() not in sender_name.lower():
                                    continue
                            
                            found_count += 1
                            with st.chat_message("user"):
                                st.markdown(f"**{sender_name}** からのメッセージ 🕒 {date_str}")
                                formatted_text = text.replace('\n', '  \n')
                                st.write(formatted_text)
                        
                        if search_query and found_count == 0:
                            st.info(f"「{search_query}」を含むメッセージは見つかりませんでした。")
    else:
        st.warning("⚠️ ユーザー情報が取得できません。一度ログアウトして入り直してください。")
        
    st.divider()
    
    # ==========================================
    # 🌟 掲示板エリア (変更なし)
    # ==========================================
    st.subheader("📌 講師向け 連絡事項・掲示板")
    current_message = load_board_message()
    
    formatted_message = current_message.replace('\n', '  \n')
    st.info(formatted_message)
    
    if user_role in ['admin', 'owner', 'head_teacher']:
        with st.expander("✏️ 掲示板を編集する"):
            new_msg = st.text_area("先生たちへのメッセージを入力", value=current_message, height=150)
            if st.button("💾 掲示板を更新", type="primary"):
                save_board_message(new_msg)
                load_board_message.clear()
                st.success("掲示板を更新しました！全先生のホーム画面に反映されます。")
                st.rerun()

    st.divider() 
    
    # ==========================================
    # 🌟 【新機能】 時間割別 本日の出欠・座席管理エリア
    # ==========================================
    st.subheader("🗺️ 本日の教室状況・座席管理")
    
    # 時間割リスト
    time_slots = [
        "Aコマ目 (9:30~11:00)", "Bコマ目 (11:10~12:40)",
        "0コマ目 (13:10~14:40)", "1コマ目 (14:50~16:20)",
        "2コマ目 (16:40~18:10)", "3コマ目 (18:20~19:50)", "4コマ目 (20:00~21:30)"
    ]
    
    # 生徒名と全座席データの取得
    student_names = get_all_student_names()
    if not student_names: student_names = []
    
    try:
        all_seating_data = load_seating_data()
    except Exception:
        all_seating_data = {}
        st.error("座席データの読み込みに失敗しました。")

    # 管理者（教室長・オーナー）かどうかの判定
    can_edit_seat = user_role in ['admin', 'owner']
    
    if can_edit_seat:
        st.write("時間帯のタブを切り替えて、各コマの座席・出欠を管理できます。")
    else:
        st.write("時間帯のタブを切り替えて、各コマの座席表を確認できます。")

    # ブース数の決定（過去のデータから最大ブース数を推測、デフォルト6）
    if 'num_booths' not in st.session_state:
        max_b = 6
        for key in all_seating_data.keys():
            if "||" in str(key):
                b_name = str(key).split("||")[1]
                b_num_str = b_name.replace("ブース", "")
                if b_num_str.isdigit() and int(b_num_str) > max_b:
                    max_b = int(b_num_str)
        st.session_state['num_booths'] = max_b

    # 管理者のみ「ブースの増減」ボタンを表示
    if can_edit_seat:
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

    # 見やすいように「Aコマ目」など短い名前でタブを作成
    tab_names = [slot.split(" ")[0] for slot in time_slots]
    tabs = st.tabs(tab_names)

    # 各コマごとの処理ループ
    for slot_idx, slot_name in enumerate(time_slots):
        with tabs[slot_idx]:
            st.markdown(f"#### 🕒 {slot_name} の座席表")
            
            # --- 今のコマのデータだけを抽出 ---
            slot_data = {}
            for key, info in all_seating_data.items():
                if f"{slot_name}||" in str(key):
                    b_name = key.split("||")[1]
                    slot_data[b_name] = info
                elif "||" not in str(key) and slot_idx == 0:
                    # 古い仕様のデータ（||が含まれていない）はとりあえず最初のコマに割り当てる
                    slot_data[key] = info

            # ==========================================
            # ✍️ 編集モード（教室長・オーナー専用）
            # ==========================================
            if can_edit_seat:
                new_seating_for_slot = {}
                assigned_students = set()
                
                # 既にこのコマで選ばれている生徒をリストアップ
                for i in range(st.session_state['num_booths']):
                    s_key = f"seat_{slot_idx}_{i}"
                    if s_key in st.session_state:
                        seat_val = st.session_state[s_key]
                        if seat_val != "-- 空席 --":
                            assigned_students.add(seat_val)
                    else:
                        booth_name = f"ブース{i+1}"
                        info = slot_data.get(booth_name, {"生徒名": "-- 空席 --"})
                        if info.get("生徒名") != "-- 空席 --":
                            assigned_students.add(info["生徒名"])

                # 3つずつ行を作る
                for i in range(0, st.session_state['num_booths'], 3):
                    cols = st.columns(3)
                    for j in range(3):
                        if i + j < st.session_state['num_booths']:
                            booth_idx = i + j
                            booth_name = f"ブース{booth_idx+1}"
                            
                            with cols[j]:
                                with st.container(border=True):
                                    st.markdown(f"**🪑 {booth_name}**")
                                    
                                    current_info = slot_data.get(booth_name, {"生徒名": "-- 空席 --", "状態": "出席"})
                                    current_seat = st.session_state.get(f"seat_{slot_idx}_{booth_idx}", current_info["生徒名"])
                                    current_status = st.session_state.get(f"status_{slot_idx}_{booth_idx}", current_info["状態"])
                                    
                                    options = ["-- 空席 --"]
                                    for s in student_names:
                                        if (s not in assigned_students) or (s == current_seat):
                                            options.append(s)
                                            
                                    new_occupant = st.selectbox(
                                        "生徒名", options, 
                                        index=options.index(current_seat) if current_seat in options else 0, 
                                        key=f"seat_{slot_idx}_{booth_idx}"
                                    )
                                    
                                    if new_occupant != "-- 空席 --":
                                        status_options = ["出席", "遅刻", "欠席連絡あり"]
                                        new_status = st.radio(
                                            "状態", status_options, 
                                            index=status_options.index(current_status) if current_status in status_options else 0,
                                            horizontal=True, key=f"status_{slot_idx}_{booth_idx}"
                                        )
                                    else:
                                        new_status = "出席" 
                                        
                                    new_seating_for_slot[booth_name] = {"生徒名": new_occupant, "状態": new_status}
                
                # 保存ボタン（コマごと）
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button(f"💾 {tab_names[slot_idx]}の座席表を確定・共有する", type="primary", key=f"save_btn_{slot_idx}", use_container_width=True):
                    with st.spinner(f'{tab_names[slot_idx]} の座席を保存中...'):
                        # 新しいデータを全データに合成して上書き保存する
                        for b_name, info in new_seating_for_slot.items():
                            all_seating_data[f"{slot_name}||{b_name}"] = info
                            
                        save_seating_data(all_seating_data)
                        st.success(f"✨ {slot_name} の座席表をクラウドに保存しました！")
                        st.rerun()

            # ==========================================
            # 👀 閲覧モード（一般講師など、全員）
            # ==========================================
            else:
                num_booths_view = max(6, len(slot_data)) # データがない場合は最低6枠表示
                
                if not slot_data:
                    st.info(f"{slot_name} の座席データはまだ登録されていません。")
                else:
                    for i in range(0, num_booths_view, 3):
                        cols = st.columns(3)
                        for j in range(3):
                            if i + j < num_booths_view:
                                booth_idx = i + j
                                booth_name = f"ブース{booth_idx+1}"
                                info = slot_data.get(booth_name, {"生徒名": "-- 空席 --", "状態": "出席"})
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

    # ==========================================
    # 🚀 一括保存ボタン（タブの外側＝一番下に配置）
    # ==========================================
    if can_edit_seat:
        st.divider()
        if st.button("💾 全コマの座席表をまとめて確定・共有する", type="primary", use_container_width=True):
            with st.spinner("全コマの座席データを保存中..."):
                
                # すべてのタブのセッションステート（入力状態）を回収してデータを作成
                for slot_idx, slot_name in enumerate(time_slots):
                    for booth_idx in range(st.session_state['num_booths']):
                        booth_name = f"ブース{booth_idx+1}"
                        
                        # 画面上の選択肢を取得（まだ表示されていない場合はデフォルト値）
                        seat_val = st.session_state.get(f"seat_{slot_idx}_{booth_idx}", "-- 空席 --")
                        status_val = st.session_state.get(f"status_{slot_idx}_{booth_idx}", "出席")
                        
                        if seat_val == "-- 空席 --":
                            status_val = "出席"
                            
                        # "コマ名||ブース名" の形式で保存
                        all_seating_data[f"{slot_name}||{booth_name}"] = {"生徒名": seat_val, "状態": status_val}
                
                # スプレッドシートに一括保存
                save_seating_data(all_seating_data)
                st.success("✨ 全コマの座席表をクラウドにまとめて保存しました！")
                st.rerun()