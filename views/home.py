import streamlit as st
import time

# 裏方部隊
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

# 🌟 APIガードをインポート（独自定義のsafe_api_callとgspreadのimportは削除しました）
from utils.api_guard import robust_api_call

def render_home_page():
    st.header("📢 ホーム・連絡掲示板")
    
    user_role = st.session_state.get('role', '')
    my_user_id = st.session_state.get('user_id')

    # ==========================================
    # 🌟 個別メッセージエリア
    # ==========================================
    st.subheader("💌 あなた宛てのメッセージ")
    
    if my_user_id:
        # 🛡️ 安全にメッセージを取得（引数がある場合は lambda を使って渡します）
        messages = robust_api_call(lambda: get_my_messages(my_user_id), fallback_value=[])
        
        if not messages or (isinstance(messages, dict) and "APIエラー発生" in messages):
            st.info("現在、新しいメッセージはありません。")
        else:
            unread_msgs = [m for m in messages if m.get("状態", "未読") in ["未読", "False"]]
            read_msgs = [m for m in messages if m not in unread_msgs]
            
            if unread_msgs:
                robust_api_call(lambda: mark_messages_as_read(my_user_id), fallback_value=False)
                get_my_messages.clear()
            
            raw_accounts = robust_api_call(get_all_accounts, fallback_value={})
            safe_accounts = {str(k).strip().lower(): v for k, v in raw_accounts.items()} if raw_accounts else {}
            
            # 📩 新着メッセージ枠
            if unread_msgs:
                st.markdown("##### 📩 新着メッセージ")
                for msg in unread_msgs:
                    sender_name = "送信者不明"
                    sender_id_clean = str(msg.get("送信者ID", "")).strip().lower()
                    account_info = safe_accounts.get(sender_id_clean, {})
                    base_name = account_info.get("講師名")
                    if base_name: sender_name = f"{base_name} 先生"
                    
                    with st.chat_message("assistant"):
                        st.markdown(f"**{sender_name}** から 🕒 {msg.get('送信日時', '')} 🔴 **New!**")
                        st.write(msg.get("メッセージ内容", "").replace('\n', '  \n'))
            
            # ✅ 過去のメッセージ枠
            if read_msgs:
                with st.expander("✅ 過去のメッセージを表示"):
                    for msg in read_msgs:
                        with st.chat_message("user"):
                            st.write(msg.get("メッセージ内容", "").replace('\n', '  \n'))
    else:
        st.warning("⚠️ ユーザー情報が取得できません。再ログインしてください。")
        
    st.divider()
    
    # ==========================================
    # 🌟 掲示板エリア
    # ==========================================
    st.subheader("📌 講師向け 連絡事項")
    current_message = robust_api_call(load_board_message, fallback_value="")
    st.info(current_message.replace('\n', '  \n'))
    
    if user_role in ['admin', 'owner', 'head_teacher']:
        with st.expander("✏️ 掲示板を編集"):
            new_msg = st.text_area("内容を入力", value=current_message, height=100)
            if st.button("💾 掲示板を更新"):
                with st.spinner("更新中..."):
                    success = robust_api_call(lambda: save_board_message(new_msg), fallback_value=False)
                    if success is not False:
                        load_board_message.clear()
                        st.success("更新しました！")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("通信エラーにより更新できませんでした。")

    st.divider() 
    
    # ==========================================
    # 🌟 座席管理エリア（プログレスバー搭載）
    # ==========================================
    st.subheader("🗺️ 本日の教室状況・座席管理")
    
    # 🌟 読み込みプログレスバーの実装
    loading_progress = st.progress(0, text="☁️ クラウドからデータを読み込み中...")
    
    # STEP1: 生徒名リストの取得
    loading_progress.progress(30, text="📋 生徒名簿を確認中...")
    student_names = robust_api_call(get_all_student_names, fallback_value=[])
    time.sleep(0.2) # APIの負荷軽減
    
    # STEP2: 座席データの取得
    loading_progress.progress(70, text="🪑 今日の座席表を広げています...")
    all_seating_data = robust_api_call(load_seating_data, fallback_value={})
    time.sleep(0.2)
    
    # 完了！
    loading_progress.progress(100, text="✨ 読み込み完了！")
    time.sleep(0.5)
    loading_progress.empty() # バーを消去

    time_slots = [
        "Aコマ (9:30~)", "Bコマ (11:10~)", "0コマ (13:10~)", 
        "1コマ (14:50~)", "2コマ (16:40~)", "3コマ (18:20~)", "4コマ (20:00~)"
    ]
    
    can_edit_seat = user_role in ['admin', 'owner']
    
    # ブース数の管理
    if 'num_booths' not in st.session_state:
        st.session_state['num_booths'] = 6

    if can_edit_seat:
        c_add, c_sub, _ = st.columns([1, 1, 3])
        if c_add.button("➕ ブース追加"): 
            st.session_state['num_booths'] += 1
            st.rerun()
        if c_sub.button("➖ 削減") and st.session_state['num_booths'] > 1:
            st.session_state['num_booths'] -= 1
            st.rerun()

    # タブ生成
    tab_names = [slot.split(" ")[0] for slot in time_slots]
    tabs = st.tabs(tab_names)

    for slot_idx, slot_name in enumerate(time_slots):
        with tabs[slot_idx]:
            st.markdown(f"#### 🕒 {slot_name}")
            
            # 当該コマのデータを抽出
            slot_data = {k.split("||")[1]: v for k, v in all_seating_data.items() if f"{slot_name}||" in str(k)}

            if can_edit_seat:
                new_seating_for_slot = {}
                # 座席配置
                for i in range(0, st.session_state['num_booths'], 3):
                    cols = st.columns(3)
                    for j in range(3):
                        idx = i + j
                        if idx < st.session_state['num_booths']:
                            booth_name = f"ブース{idx+1}"
                            with cols[j]:
                                with st.container(border=True):
                                    st.write(f"**{booth_name}**")
                                    current_info = slot_data.get(booth_name, {"生徒名": "-- 空席 --", "状態": "出席"})
                                    
                                    # 生徒選択
                                    options = ["-- 空席 --"] + student_names
                                    sel_name = st.selectbox("生徒", options, 
                                                            index=options.index(current_info["生徒名"]) if current_info["生徒名"] in options else 0,
                                                            key=f"sel_{slot_idx}_{idx}")
                                    
                                    # 状態選択
                                    st_options = ["出席", "遅刻", "欠席連絡あり"]
                                    sel_status = st.radio("状態", st_options, 
                                                          index=st_options.index(current_info["状態"]) if current_info["状態"] in st_options else 0,
                                                          horizontal=True, key=f"rad_{slot_idx}_{idx}")
                                    
                                    new_seating_for_slot[booth_name] = {"生徒名": sel_name, "状態": sel_status}

                if st.button(f"💾 {tab_names[slot_idx]}を保存", key=f"save_{slot_idx}"):
                    with st.spinner("保存中..."):
                        for b_name, info in new_seating_for_slot.items():
                            all_seating_data[f"{slot_name}||{b_name}"] = info
                        
                        success = robust_api_call(lambda: save_seating_data(all_seating_data), fallback_value=False)
                        
                        if success is not False:
                            st.success("保存完了！")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("保存に失敗しました。時間をおいて再試行してください。")
            else:
                # 閲覧モード
                if not slot_data:
                    st.info("データがありません。")
                else:
                    for i in range(0, max(6, len(slot_data)), 3):
                        cols = st.columns(3)
                        for j in range(3):
                            idx = i + j
                            booth_name = f"ブース{idx+1}"
                            if idx < max(6, len(slot_data)):
                                with cols[j]:
                                    with st.container(border=True):
                                        info = slot_data.get(booth_name, {"生徒名": "-- 空席 --", "状態": "出席"})
                                        st.markdown(f"**{booth_name}**")
                                        if info["生徒名"] == "-- 空席 --":
                                            st.caption("-- 空席 --")
                                        else:
                                            color = "#28a745" if info["状態"]=="出席" else "#dc3545"
                                            st.markdown(f"### {info['生徒名']}")
                                            st.markdown(f"<span style='color:{color}'>{info['状態']}</span>", unsafe_allow_html=True)

    # ==========================================
    # 🚀 一括保存ボタン（超・安全＆プログレスバー版）
    # ==========================================
    if can_edit_seat:
        st.divider()
        if st.button("💾 全コマの座席表をまとめて一括保存", type="primary", use_container_width=True):
            save_progress = st.progress(0, text="📦 全データを集計中...")
            
            # 1. セッションステートから全データを収集
            new_all_data = {}
            total_steps = len(time_slots)
            
            for s_idx, s_name in enumerate(time_slots):
                save_progress.progress((s_idx + 1) / (total_steps + 1), text=f"📂 {s_name} のデータを整理中...")
                for b_idx in range(st.session_state['num_booths']):
                    b_name = f"ブース{b_idx+1}"
                    s_val = st.session_state.get(f"sel_{s_idx}_{b_idx}", "-- 空席 --")
                    r_val = st.session_state.get(f"rad_{s_idx}_{b_idx}", "出席")
                    new_all_data[f"{s_name}||{b_name}"] = {"生徒名": s_val, "状態": r_val}
                time.sleep(0.05) # 画面更新のための微小な待ち
            
            # 2. API送信（ここでrobust_api_callを使用）
            save_progress.progress(0.95, text="🚀 Googleスプレッドシートに送信中...（APIエラー回避待機含む☕）")
            success = robust_api_call(lambda: save_seating_data(new_all_data), fallback_value=False)
            
            if success is not False:
                save_progress.progress(100, text="✅ すべての保存が完了しました！")
                st.balloons()
                time.sleep(2)
                st.rerun()
            else:
                st.error("保存に失敗しました。少し時間をおいてから再度お試しください。")