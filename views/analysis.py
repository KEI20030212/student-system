import streamlit as st
import pandas as pd
import time 
import gspread 

from utils.g_sheets import (
    load_all_data,
    load_raw_data,          
    overwrite_spreadsheet,
    load_quiz_records  # 🌟 追加
)

# 🌟 APIガードをインポート
from utils.api_guard import robust_api_call

def render_analysis_page(name):
    # 🌟 APIエラー対策付きの読み込み
    with st.spinner("📊 データを取得中..."):
        # 1. 指導報告書などの履歴データ
        df_history = robust_api_call(lambda: load_all_data(name), fallback_value=pd.DataFrame())
        
        # 2. 🌟 小テスト記録シートの全データ取得
        df_all_quizzes = robust_api_call(load_quiz_records, fallback_value=pd.DataFrame())

    # --- 振替授業の計算 (df_historyを使用) ---
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
        # --- ページ進捗グラフ (df_historyを使用) ---
        if df_history.empty: 
            st.info("進捗データがありません。")
        else:
            st.markdown("**📖 ページ進捗グラフ**")
            df_history['日時'] = pd.to_datetime(df_history['日時'], format='mixed')
            df_history = df_history.sort_values('日時')
            st.line_chart(data=df_history, x="日時", y="ページ数")

        st.divider()

        # --- 🌟 小テスト点数グラフ (df_all_quizzesを使用) ---
        st.markdown("**💯 単元別小テスト点数**")
        
        if df_all_quizzes.empty:
            st.info("小テストの記録が見つかりません。")
        else:
            # 「名前」列で現在の生徒のみに絞り込み
            df_student_quiz = df_all_quizzes[df_all_quizzes['名前'] == name].copy()
            
            if df_student_quiz.empty:
                st.info(f"{name}さんの小テスト記録はまだありません。")
            else:
                # 「点数」列を数値に変換（エラーはNaNにする）
                df_student_quiz['数値点数'] = pd.to_numeric(df_student_quiz['点数'], errors='coerce')
                # グラフ表示用に、点数が入っていない行を削除
                df_quiz_chart = df_student_quiz.dropna(subset=['数値点数'])
                
                if not df_quiz_chart.empty:
                    # 棒グラフを表示（「単元」列があると仮定しています）
                    # 列名が「テスト名」などの場合は適宜書き換えてください
                    chart_x = "単元" if "単元" in df_quiz_chart.columns else "日時"
                    st.bar_chart(data=df_quiz_chart, x=chart_x, y="数値点数")
                else:
                    st.info("有効な点数データがありません。")

    with tab_history:
        # 🌟 APIエラー対策付きの生データ読み込み
        raw_df = robust_api_call(lambda: load_raw_data(name), fallback_value=pd.DataFrame())

        if not raw_df.empty:
            st.info("💡 以下の表のセルを直接クリックして書き換え、下の「上書き保存」ボタンを押してください。")
            edited_df = st.data_editor(raw_df, num_rows="dynamic", use_container_width=True)
            
            if st.button("💾 上書き保存", type="primary"): 
                with st.spinner("☁️ データを上書き保存中..."):
                    def _overwrite():
                        overwrite_spreadsheet(name, edited_df)
                        return True
                    
                    success = robust_api_call(_overwrite, fallback_value=False)
                    if success:
                        st.success("✨ データを上書き保存しました！")
                    else:
                        st.error("保存に失敗しました。時間をおいてやり直してください。")