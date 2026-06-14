import streamlit as st
import pandas as pd
import datetime
import time

from utils.api_guard import robust_api_call
# 🚨 本物の関数を読み込みます！（マスタ取得用も追加）
from utils.g_sheets import (
    save_shift_records, 
    load_shift_records,
    get_student_master,
    get_all_teacher_names  # 👈 講師マスタを取得する関数も追加想定
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
    
    # マスタデータから動的にプルダウンの選択肢を生成
    if target_type == "講師":
        if teacher_names:
            member_options = teacher_names
        else:
            st.warning("⚠️ 講師マスタにデータがありません。")
            member_options = []
    else:
        if not df_students.empty and "生徒名" in df_students.columns:
            member_options = df_students["生徒名"].dropna().unique().tolist()
        else:
            st.warning("⚠️ 生徒マスタにデータがありません。")
            member_options = []

    selected_member = col1.selectbox(
        f"👨‍🏫 担当の{target_type}名を選択", 
        ["-- 選択してください --"] + member_options
    )
    
    if selected_member == "-- 選択してください --":
        st.info("対象のメンバーを選択すると、シフト入力フォームが表示されます。")
        st.stop()

    # ------------------------------------------
    # 2. 対象の「週」を選択（月曜日を基準にする）
    # ------------------------------------------
    today = datetime.date.today()
    start_of_week = today - datetime.timedelta(days=today.weekday()) 
    
    week_options = []
    for i in range(-2, 9): # 過去2週間 〜 未来8週間まで拡張
        w_start = start_of_week + datetime.timedelta(weeks=i)
        w_end = w_start + datetime.timedelta(days=6)
        label = f"{w_start.strftime('%Y/%m/%d')} (月) 〜 {w_end.strftime('%m/%d')} (日)"
        week_options.append((w_start, label))
        
    selected_week_idx = col2.selectbox(
        "📅 対象の週を選択", 
        range(len(week_options)), 
        index=2, # デフォルトは「今週」
        format_func=lambda x: week_options[x][1]
    )
    target_start_date = week_options[selected_week_idx][0]

    st.divider()

    # ------------------------------------------
    # 3. 1週間分のシフト編集フォーム（スマホ最適化版 🌟）
    # ------------------------------------------
    st.subheader(f"📝 {selected_member} さんのシフト入力")
    st.caption("日付をタップして開き、各コマの状況（〇：入れる、×：入れない、ー：未定）をタップしてください。")
    
    # 曜日定義
    days_of_week = ["月", "火", "水", "木", "金", "土", "日"]
    columns = ["日付", "曜日", "Aコマ", "Bコマ", "0コマ", "1コマ", "2コマ", "3コマ", "4コマ"]
    
    # 🚨 既存データをスプレッドシートから安全にロード
    with st.spinner("既存のシフトデータを読み込み中..."):
        df_existing = robust_api_call(
            lambda: load_shift_records(target_type, selected_member, target_start_date),
            fallback_value=pd.DataFrame()
        )
    
    # スプレッドシートにデータがまだ無い場合は、すべて空欄の7日分の初期データを作成
    if df_existing.empty:
        init_data = []
        for i in range(7):
            current_date = target_start_date + datetime.timedelta(days=i)
            init_data.append({
                "日付": current_date.strftime("%Y/%m/%d"),
                "曜日": days_of_week[i],
                "Aコマ": "", "Bコマ": "", "0コマ": "", "1コマ": "", "2コマ": "", "3コマ": "", "4コマ": ""
            })
        df_shift_base = pd.DataFrame(init_data)
    else:
        # 🚨 【エラー回避の魔法】スプレッドシート側に足りない列があれば、自動で空欄として補ってエラーを防ぐ！
        for col in columns:
            if col not in df_existing.columns:
                df_existing[col] = ""
                
        # 既存データがある場合は、表示に必要な列だけを順番通りに並び替える
        df_shift_base = df_existing[columns].copy()

    # スマホ入力用のデータ受け皿とマッピング定義
    edited_rows = []
    status_map_display = {"": "ー", "〇": "〇", "×": "×"}
    status_map_save = {"ー": "", "〇": "〇", "×": "×"}
    options = ["ー", "〇", "×"]
    
    # コマ名と時間帯の対応リスト
    slot_info = [
        ("Aコマ", "9:30~11:00"),
        ("Bコマ", "11:10~12:40"),
        ("0コマ", "13:10~14:40"),
        ("1コマ", "14:50~16:20"),
        ("2コマ", "16:40~18:10"),
        ("3コマ", "18:20~19:50"),
        ("4コマ", "20:00~21:30")
    ]
    
    # 選択した週に「今日」が含まれるか判定し、スマホを開いたときの初期展開を最適化する
    is_current_week = (target_start_date <= today <= target_start_date + datetime.timedelta(days=6))
    current_weekday_idx = today.weekday() if is_current_week else 0

    # 1日ずつ縦にカード（Expander）として配置
    for i in range(7):
        row = df_shift_base.iloc[i]
        date_str = row["日付"]
        day_str = row["曜日"]
        
        # 今週なら「今日」の曜日を自動展開、それ以外の週なら「月曜日」を自動展開（画面をスッキリさせる工夫）
        is_expanded = (i == current_weekday_idx)
        
        with st.expander(f"📅 {date_str} ({day_str}曜日)", expanded=is_expanded):
            day_data = {"日付": date_str, "曜日": day_str}
            
            # 各コマをスマホで押しやすい横並びのラジオボタンに変換
            for slot_name, slot_time in slot_info:
                current_val = row[slot_name]
                display_val = status_map_display.get(current_val, "ー")
                idx = options.index(display_val)
                
                chosen = st.radio(
                    f"**{slot_name}** ({slot_time})",
                    options=options,
                    index=idx,
                    horizontal=True,
                    key=f"shift_{i}_{slot_name}"
                )
                # スプレッドシート保存用の値（空文字、〇、×）に戻す
                day_data[slot_name] = status_map_save[chosen]
                
            edited_rows.append(day_data)
            
    # スマホでバラバラに入力されたデータを、元のエクセルと同じDataFrame型に完全復元！
    edited_df = pd.DataFrame(edited_rows)

    # ------------------------------------------
    # 4. 保存処理
    # ------------------------------------------
    st.write("") # 微調整用スペース
    submit_btn = st.button(f"💾 {selected_member} さんのシフトを保存", type="primary", use_container_width=True)
    
    if submit_btn:
        with st.spinner("スプレッドシートにシフトデータを書き込み中..."):
            
            # 🚨 復元したデータをそのまま関数に渡して保存！（中身はエクセル形式と同じなのでそのまま動きます）
            success = robust_api_call(
                lambda: save_shift_records(target_type, selected_member, edited_df),
                fallback_value=False
            )
            
            if success:
                st.success(f"🎉 {selected_member} さんのシフトを正常に保存しました！")
                
                # 🚨 キャッシュをクリアして、次回開いたときに確実に最新データが読み込まれるようにする
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()  # 画面を再読み込みして保存結果を反映
            else:
                st.error("スプレッドシートへの保存に失敗しました。ネットワーク状況やシートの列名を確認してください。")