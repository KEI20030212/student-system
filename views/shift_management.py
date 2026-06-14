import streamlit as st
import pandas as pd
import datetime
import time

from utils.api_guard import robust_api_call
# 🚨 新しく追加した save_fixed_shift_master を忘れずにインポート！
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
    # 0. 本番マスタデータのロード
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
        st.info("対象のメンバーを選択すると、シフト入力フォームが表示されます。")
        st.stop()

    st.divider()

    # 🌟 目的が混ざらないように「タブ」で画面を分割！
    tab_weekly, tab_fixed = st.tabs(["📝 毎週のシフト提出", "⚙️ 基本の固定シフト設定"])

    # 共通で使う定数
    days_of_week = ["月", "火", "水", "木", "金", "土", "日"]
    slot_info = [
        ("Aコマ", "9:30~11:00"), ("Bコマ", "11:10~12:40"), ("0コマ", "13:10~14:40"),
        ("1コマ", "14:50~16:20"), ("2コマ", "16:40~18:10"), ("3コマ", "18:20~19:50"), ("4コマ", "20:00~21:30")
    ]
    status_map_display = {"": "ー", "〇": "〇", "×": "×"}
    status_map_save = {"ー": "", "〇": "〇", "×": "×"}
    options = ["ー", "〇", "×"]

    # ==========================================
    # 🌟 タブ1：毎週のシフト提出（今までの機能）
    # ==========================================
    with tab_weekly:
        st.subheader("今週以降のシフト提出・変更")
        st.caption("設定済みの固定シフトが自動反映されます。変更・追加がある週のみ修正してください。")
        
        # 2. 対象の「週」を選択
        today = datetime.date.today()
        start_of_week = today - datetime.timedelta(days=today.weekday()) 
        
        week_options = []
        for i in range(-2, 9): 
            w_start = start_of_week + datetime.timedelta(weeks=i)
            w_end = w_start + datetime.timedelta(days=6)
            label = f"{w_start.strftime('%Y/%m/%d')} (月) 〜 {w_end.strftime('%m/%d')} (日)"
            week_options.append((w_start, label))
            
        selected_week_idx = st.selectbox(
            "📅 対象の週を選択", 
            range(len(week_options)), 
            index=2, 
            format_func=lambda x: week_options[x][1],
            key="weekly_selectbox"
        )
        target_start_date = week_options[selected_week_idx][0]

        columns = ["日付", "曜日", "Aコマ", "Bコマ", "0コマ", "1コマ", "2コマ", "3コマ", "4コマ"]
        
        # 既存の提出済みデータをロード
        with st.spinner("既存のシフトデータを読み込み中..."):
            df_existing = robust_api_call(
                lambda: load_shift_records(target_type, selected_member, target_start_date),
                fallback_value=pd.DataFrame()
            )
        
        # まだその週のシフトデータが無い場合（新規）
        if df_existing.empty:
            df_fixed = robust_api_call(
                lambda: load_fixed_shift_master(target_type, selected_member),
                fallback_value=pd.DataFrame()
            )
            
            fixed_dict = {}
            if not df_fixed.empty and "曜日" in df_fixed.columns:
                fixed_dict = df_fixed.set_index("曜日").to_dict("index")

            init_data = []
            for i in range(7):
                current_date = target_start_date + datetime.timedelta(days=i)
                day_str = days_of_week[i]
                
                day_data = {
                    "日付": current_date.strftime("%Y/%m/%d"), "曜日": day_str,
                    "Aコマ": "", "Bコマ": "", "0コマ": "", "1コマ": "", "2コマ": "", "3コマ": "", "4コマ": ""
                }
                
                if day_str in fixed_dict:
                    for col in ["Aコマ", "Bコマ", "0コマ", "1コマ", "2コマ", "3コマ", "4コマ"]:
                        if col in fixed_dict[day_str] and pd.notna(fixed_dict[day_str][col]):
                            day_data[col] = fixed_dict[day_str][col]
                            
                init_data.append(day_data)
            df_shift_base = pd.DataFrame(init_data)
        else:
            for col in columns:
                if col not in df_existing.columns:
                    df_existing[col] = ""
            df_shift_base = df_existing[columns].copy()

        edited_rows = []
        is_current_week = (target_start_date <= today <= target_start_date + datetime.timedelta(days=6))
        current_weekday_idx = today.weekday() if is_current_week else 0

        # アコーディオン形式で1週間分描画
        for i in range(7):
            row = df_shift_base.iloc[i]
            date_str = row["日付"]
            day_str = row["曜日"]
            
            is_expanded = (i == current_weekday_idx)
            
            with st.expander(f"📅 {date_str} ({day_str}曜日)", expanded=is_expanded):
                day_data = {"日付": date_str, "曜日": day_str}
                for slot_name, slot_time in slot_info:
                    current_val = row[slot_name]
                    display_val = status_map_display.get(current_val, "ー")
                    idx = options.index(display_val)
                    
                    chosen = st.radio(
                        f"**{slot_name}** ({slot_time})",
                        options=options, index=idx, horizontal=True,
                        key=f"weekly_{i}_{slot_name}"
                    )
                    day_data[slot_name] = status_map_save[chosen]
                edited_rows.append(day_data)
                
        edited_df = pd.DataFrame(edited_rows)

        st.write("") 
        if st.button(f"💾 {target_start_date.strftime('%m/%d')}〜 のシフトを保存", type="primary", use_container_width=True, key="btn_weekly"):
            with st.spinner("スプレッドシートに書き込み中..."):
                success = robust_api_call(
                    lambda: save_shift_records(target_type, selected_member, edited_df),
                    fallback_value=False
                )
                if success:
                    st.success("🎉 今週のシフトを正常に保存しました！")
                    st.cache_data.clear()
                    time.sleep(1)
                    st.rerun() 
                else:
                    st.error("保存に失敗しました。ネットワークを確認してください。")

    # ==========================================
    # 🌟 タブ2：基本の固定シフト設定（新規追加）
    # ==========================================
    with tab_fixed:
        st.subheader("基本シフト（ベース）の設定")
        st.info("💡 毎週必ず入る曜日・コマを設定してください。ここで設定した内容が、左のタブの『初期値』として自動入力されます。")

        # 現在の固定シフトをロード
        with st.spinner("固定シフトデータを読み込み中..."):
            df_fixed_master = robust_api_call(
                lambda: load_fixed_shift_master(target_type, selected_member),
                fallback_value=pd.DataFrame()
            )
            
        fixed_master_dict = {}
        if not df_fixed_master.empty and "曜日" in df_fixed_master.columns:
            fixed_master_dict = df_fixed_master.set_index("曜日").to_dict("index")

        edited_rows_fixed = []

        # 日付は不要なので、月曜〜日曜の曜日だけでアコーディオンを描画
        for i in range(7):
            day_str = days_of_week[i]
            # 固定シフトデータがあれば反映、なければ空
            existing_day_data = fixed_master_dict.get(day_str, {})
            
            with st.expander(f"🔄 {day_str}曜日 の基本シフト"):
                day_data = {"曜日": day_str}
                for slot_name, slot_time in slot_info:
                    current_val = existing_day_data.get(slot_name, "")
                    display_val = status_map_display.get(current_val, "ー")
                    idx = options.index(display_val) if display_val in options else 0
                    
                    chosen = st.radio(
                        f"**{slot_name}** ({slot_time})",
                        options=options, index=idx, horizontal=True,
                        key=f"fixed_{i}_{slot_name}"
                    )
                    day_data[slot_name] = status_map_save[chosen]
                edited_rows_fixed.append(day_data)

        edited_df_fixed = pd.DataFrame(edited_rows_fixed)

        st.write("") 
        if st.button(f"⚙️ {selected_member} さんの固定シフトを更新", type="primary", use_container_width=True, key="btn_fixed"):
            with st.spinner("固定マスタを更新中..."):
                success = robust_api_call(
                    lambda: save_fixed_shift_master(target_type, selected_member, edited_df_fixed),
                    fallback_value=False
                )
                if success:
                    st.success("🎉 固定シフトのベースを更新しました！次回からこの内容が初期値になります。")
                    st.cache_data.clear()
                    time.sleep(1)
                    st.rerun() 
                else:
                    st.error("保存に失敗しました。")