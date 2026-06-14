import streamlit as st
import pandas as pd
import datetime
import time

from utils.api_guard import robust_api_call
# 🚨 作成した本番用関数をインポート
from utils.g_sheets import (
    save_shift_records, 
    load_shift_records,
    get_student_master,
    get_all_teacher_names,
    load_fixed_shift_master,
    save_fixed_shift_master
)

def render_shift_management_page():
    st.header("📅 講習シフト入力フォーム")
    st.write("講師と生徒の講習シフトを登録・更新できます。スマホからでも押しやすい快適UIです🚀")

    # ------------------------------------------
    # 0. 本番マスタデータのロード (メンバーの選択肢用)
    # ------------------------------------------
    with st.spinner("マスタデータを読み込み中..."):
        df_students = robust_api_call(get_student_master, fallback_value=pd.DataFrame())
        teacher_names = robust_api_call(get_all_teacher_names, fallback_value=[])
        
    # ------------------------------------------
    # 1. 対象（講師 or 生徒）とメンバーの選択
    # ------------------------------------------
    st.subheader("👤 1. 入力対象を選択")
    target_type = st.radio("入力を開始する対象を選んでください", ["講師", "生徒"], horizontal=True)
    
    col1, col2 = st.columns(2)
    
    if target_type == "講師":
        member_options = teacher_names if teacher_names else []
        if not teacher_names:
            st.warning("⚠️ 講師マスタにデータがありません。")
    else:
        member_options = df_students["生徒名"].dropna().unique().tolist() if not df_students.empty and "生徒名" in df_students.columns else []
        if not member_options:
            st.warning("⚠️ 生徒マスタにデータがありません。")

    selected_member = col1.selectbox(
        f"👨‍🏫 担当の{target_type}名を選択", 
        ["-- 選択してください --"] + member_options
    )
    
    if selected_member == "-- 選択してください --":
        # メンバー未選択時は、古いキャッシュキーを念のため削除
        st.session_state.pop("fixed_cache_key", None)
        st.session_state.pop("weekly_cache_key", None)
        st.info("対象のメンバーを選択すると、シフト入力フォームが表示されます。")
        st.stop()

    # 2. 対象の「週」を選択（月曜日を基準にする）
    today = datetime.date.today()
    start_of_week = today - datetime.timedelta(days=today.weekday()) 
    
    week_options = []
    for i in range(-2, 9): 
        w_start = start_of_week + datetime.timedelta(weeks=i)
        w_end = w_start + datetime.timedelta(days=6)
        label = f"{w_start.strftime('%Y/%m/%d')} (月) 〜 {w_end.strftime('%m/%d')} (日)"
        week_options.append((w_start, label))
        
    selected_week_idx = col2.selectbox(
        "📅 対象の週を選択", 
        range(len(week_options)), 
        index=2, 
        format_func=lambda x: week_options[x][1],
        key="weekly_selectbox"
    )
    target_start_date = week_options[selected_week_idx][0]

    st.divider()

    # 共通で使う定数・マップ定義
    days_of_week = ["月", "火", "水", "木", "金", "土", "日"]
    slot_info = [
        ("Aコマ", "9:30~11:00"), ("Bコマ", "11:10~12:40"), ("0コマ", "13:10~14:40"),
        ("1コマ", "14:50~16:20"), ("2コマ", "16:40~18:10"), ("3コマ", "18:20~19:50"), ("4コマ", "20:00~21:30")
    ]
    status_map_display = {"": "ー", "〇": "〇", "×": "×"}
    status_map_save = {"ー": "", "〇": "〇", "×": "×"}
    options = ["ー", "〇", "×"]

    # ==========================================
    # ⚡ 【最重要】データの初回一括ロード ＆ セッション状態の管理
    # ==========================================
    
    # ① 固定シフトマスタのロード（メンバー変更時の最初の一度だけ通信する）
    fixed_cache_key = f"fixed_{target_type}_{selected_member}"
    if st.session_state.get("fixed_cache_key") != fixed_cache_key:
        with st.spinner("スプレッドシートから現在の固定シフトを読み込み中..."):
            df_fixed_master = robust_api_call(
                lambda: load_fixed_shift_master(target_type, selected_member),
                fallback_value=pd.DataFrame()
            )
            fixed_master_dict = {}
            if not df_fixed_master.empty and "曜日" in df_fixed_master.columns:
                fixed_master_dict = df_fixed_master.set_index("曜日").to_dict("index")
                
            # 各曜日・各コマの現在の設定値をセッション状態にガッツリ注入
            for i, day_str in enumerate(days_of_week):
                existing_day_data = fixed_master_dict.get(day_str, {})
                for slot_name, _ in slot_info:
                    current_val = existing_day_data.get(slot_name, "")
                    st.session_state[f"fixed_{i}_{slot_name}"] = status_map_display.get(current_val, "ー")
                    
            st.session_state["fixed_cache_key"] = fixed_cache_key

    # ② 毎週のシフトデータのロード（メンバーや週が変わった最初の1回だけ通信する）
    weekly_cache_key = f"weekly_{target_type}_{selected_member}_{target_start_date.strftime('%Y%m%d')}"
    if st.session_state.get("weekly_cache_key") != weekly_cache_key:
        with st.spinner("スプレッドシートから今週の既存データを読み込み中..."):
            df_existing = robust_api_call(
                lambda: load_shift_records(target_type, selected_member, target_start_date),
                fallback_value=pd.DataFrame()
            )
            
            init_data = {}
            for i, day_str in enumerate(days_of_week):
                init_data[day_str] = {}
                row_match = df_existing[df_existing["曜日"] == day_str] if not df_existing.empty else pd.DataFrame()
                
                # 💡【改善】すべて「ー」の空データかどうかを判定する
                has_real_data = False
                if not row_match.empty:
                    row = row_match.iloc[0]
                    for slot_name, _ in slot_info:
                        val = row.get(slot_name, "")
                        if pd.notna(val) and val not in ["", "ー"]:
                            has_real_data = True
                            break
                
                if has_real_data:
                    # すでに〇や×など「意味のある提出データ」があるならそれを最優先で反映
                    row = row_match.iloc[0]
                    for slot_name, _ in slot_info:
                        val = row.get(slot_name, "")
                        init_data[day_str][slot_name] = status_map_display.get(val, "ー")
                else:
                    # 完全に未提出、または空（すべて「ー」）の場合は、最新の固定シフトをベースにする
                    for slot_name, _ in slot_info:
                        init_data[day_str][slot_name] = st.session_state.get(f"fixed_{i}_{slot_name}", "ー")
            
            # 毎週のシフト用のラジオボタンに初期値を一気に注入
            for i, day_str in enumerate(days_of_week):
                for slot_name, _ in slot_info:
                    st.session_state[f"weekly_{i}_{slot_name}"] = init_data[day_str][slot_name]
                    
            st.session_state["weekly_cache_key"] = weekly_cache_key

    # 🌟 目的別に切り替えるタブ
    tab_weekly, tab_fixed = st.tabs(["📝 毎週のシフト提出", "⚙️ 基本の固定シフト設定"])

    # ==========================================
    # 🌟 タブ1：毎週のシフト提出
    # ==========================================
    with tab_weekly:
        st.subheader("今週以降のシフト提出・変更")
        st.caption("基本の固定シフトが自動反映されています。予定が変わる日だけ修正してください。")

        # 💡【改善】ワンクリックで固定シフトを強制反映するボタン
        if st.button("🔄 固定シフトの最新状態をこの週に上書きコピー", use_container_width=True):
            for i in range(7):
                for slot_name, _ in slot_info:
                    # 固定シフト側の現在の状態を、毎週のシフト側に強制上書きする
                    st.session_state[f"weekly_{i}_{slot_name}"] = st.session_state.get(f"fixed_{i}_{slot_name}", "ー")
            st.rerun()

        edited_rows = []
        is_current_week = (target_start_date <= today <= target_start_date + datetime.timedelta(days=6))
        current_weekday_idx = today.weekday() if is_current_week else 0

        for i in range(7):
            day_str = days_of_week[i]
            current_date = target_start_date + datetime.timedelta(days=i)
            date_str = current_date.strftime("%Y/%m/%d")
            
            is_expanded = (i == current_weekday_idx)
            
            with st.expander(f"📅 {date_str} ({day_str}曜日)", expanded=is_expanded):
                day_data = {"日付": date_str, "曜日": day_str}
                for slot_name, slot_time in slot_info:
                    chosen = st.radio(
                        f"**{slot_name}** ({slot_time})",
                        options=options,
                        horizontal=True,
                        key=f"weekly_{i}_{slot_name}"
                    )
                    day_data[slot_name] = status_map_save[chosen]
                edited_rows.append(day_data)
                
        edited_df = pd.DataFrame(edited_rows)

        st.write("") 
        if st.button(f"💾 {target_start_date.strftime('%m/%d')}〜 のシフトを保存", type="primary", use_container_width=True, key="btn_weekly"):
            with st.spinner("スプレッドシートに保存中..."):
                success = robust_api_call(
                    lambda: save_shift_records(target_type, selected_member, edited_df),
                    fallback_value=False
                )
                if success:
                    st.success("🎉 シフトデータを正常に保存しました！")
                    st.cache_data.clear()
                    # 保存成功したらこの週のキャッシュを消し、次回最新状態で再ロードさせる
                    st.session_state.pop("weekly_cache_key", None)
                    time.sleep(1)
                    st.rerun() 
                else:
                    st.error("保存に失敗しました。ネットワークを確認してください。")

    # ==========================================
    # 🌟 タブ2：基本の固定シフト設定
    # ==========================================
    with tab_fixed:
        st.subheader("基本シフト（ベース）の設定")
        st.info("💡 毎週必ず入れる曜日・コマを登録してください。保存されている内容が最初から選択されています。")

        edited_rows_fixed = []

        for i in range(7):
            day_str = days_of_week[i]
            
            with st.expander(f"🔄 {day_str}曜日 の基本シフト"):
                day_data = {"曜日": day_str}
                for slot_name, slot_time in slot_info:
                    chosen = st.radio(
                        f"**{slot_name}** ({slot_time})",
                        options=options,
                        horizontal=True,
                        key=f"fixed_{i}_{slot_name}"
                    )
                    day_data[slot_name] = status_map_save[chosen]
                edited_rows_fixed.append(day_data)

        edited_df_fixed = pd.DataFrame(edited_rows_fixed)

        st.write("") 
        if st.button(f"⚙️ {selected_member} さんの固定シフトを更新", type="primary", use_container_width=True, key="btn_fixed"):
            with st.spinner("固定シフトマスタを更新中...（これ以外の操作では通信しません）"):
                success = robust_api_call(
                    lambda: save_fixed_shift_master(target_type, selected_member, edited_df_fixed),
                    fallback_value=False
                )
                if success:
                    st.success("🎉 固定シフトのベースを更新しました！次回からこの内容が初期値になります。")
                    st.cache_data.clear()
                    # 更新成功時にキャッシュを両方消去して、最新の固定シフト状態を強制再読込させる
                    st.session_state.pop("fixed_cache_key", None)
                    st.session_state.pop("weekly_cache_key", None)
                    time.sleep(1)
                    st.rerun() 
                else:
                    st.error("保存に失敗しました。シートの権限等を確認してください。")