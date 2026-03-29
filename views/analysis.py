import streamlit as st
import pandas as pd
from utils.g_sheets import (
    get_all_student_names,
    load_all_data,
    load_raw_data,          # 👈 履歴を直接いじるためのデータ取得！
    overwrite_spreadsheet   # 👈 編集したデータを上書き保存する魔法！
)

def render_analysis_page():
    st.header("📊 個別分析・履歴・振替管理")
    student_names = get_all_student_names()
    name = st.selectbox("👤 分析する生徒を選択", ["-- 選択 --"] + student_names)
    if name == "-- 選択 --": st.stop()

    df_history = load_all_data(name)
    if not df_history.empty and '出欠' in df_history.columns:
        absent_count = len(df_history[df_history['出欠'] == '欠席（後日振替あり）'])
        makeup_count = len(df_history[df_history['出欠'] == '出席（振替授業を消化）'])
        balance = absent_count - makeup_count
        if balance > 0:
            st.error(f"⚠️ **未消化の振替授業が【 {balance} コマ 】残っています！** (欠席: {absent_count}回 / 振替消化: {makeup_count}回)")
        else:
            st.success("✅ 現在、未消化の振替授業はありません。")

    tab_report, tab_history = st.tabs(["📊 グラフ＆レポート", "📚 過去の履歴 (直接編集)"])

    with tab_report:
        if df_history.empty: st.stop()
        df_history['日時'] = pd.to_datetime(df_history['日時'], format='mixed')
        df_history = df_history.sort_values('日時')
        col_g1, col_g2 = st.columns(2)
        with col_g1: st.line_chart(data=df_history, x="日時", y="ページ数")
        with col_g2:
            df_history['数値点数'] = pd.to_numeric(df_history['点数'], errors='coerce')
            df_quiz = df_history.dropna(subset=['数値点数']).copy()
            if not df_quiz.empty: st.bar_chart(data=df_quiz, x="単元", y="数値点数")

    with tab_history:
        raw_df = load_raw_data(name)
        if not raw_df.empty:
            edited_df = st.data_editor(raw_df, num_rows="dynamic", use_container_width=True)
            if st.button("💾 上書き保存", type="primary"): 
                overwrite_spreadsheet(name, edited_df)
                st.success("✨ データを上書き保存しました！") # 👈 保存成功のメッセージをオマケでつけました！