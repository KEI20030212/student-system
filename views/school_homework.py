import streamlit as st
import pandas as pd
from datetime import date, datetime
from utils.g_sheets import load_school_homework_data, update_homework_status, add_school_homework_multi, get_all_student_grades

def render_school_homework_page():
    st.header("🎒 学校課題管理（内申点対策）")
    
    tab1, tab2 = st.tabs(["📋 提出アラート・進捗更新", "➕ 課題の一括登録"])

    # ==========================================
    # タブ1：アラート・進捗更新（そのまま）
    # ==========================================
    with tab1:
        st.write("「完了（終わった）」と「提出済（学校に出した）」を分けて管理します。")
        df = load_school_homework_data()
        
        if df.empty:
            st.info("現在、登録されている学校の課題はありません。")
        else:
            df_active = df[df["ステータス"] != "提出済"].copy()
            df_active["提出期限"] = pd.to_datetime(df_active["提出期限"]).dt.date
            df_active = df_active.sort_values("提出期限")

            today = date.today()

            for idx, row in df_active.iterrows():
                days_left = (row["提出期限"] - today).days
                
                if row["ステータス"] == "完了":
                    label, icon = "【提出確認】学校に出しましたか？", "🟦"
                elif days_left < 0:
                    label, icon = f"【期限超過！】 {abs(days_left)}日経過", "🔴"
                elif days_left <= 2:
                    label, icon = f"【期限直前】 あと{days_left}日", "🟡"
                else:
                    label, icon = f"あと{days_left}日", "🟢"

                with st.expander(f"{icon} {row['生徒名']} : {row['教科']} ({label})"):
                    st.write(f"**課題内容:** {row['課題内容']}")
                    st.write(f"**提出期限:** {row['提出期限']}")
                    st.write(f"**メモ:** {row['メモ']}")
                    
                    new_status = st.selectbox(
                        "ステータスを更新", 
                        ["未着手", "進行中", "完了", "提出済"],
                        index=["未着手", "進行中", "完了", "提出済"].index(row["ステータス"]),
                        key=f"status_{idx}"
                    )
                    
                    if st.button("更新を保存", key=f"btn_{idx}"):
                        if update_homework_status(idx + 2, new_status):
                            st.success(f"{row['生徒名']}さんのステータスを「{new_status}」に更新しました！")
                            st.rerun()

    # ==========================================
    # タブ2：学校 × 学年 での一括登録
    # ==========================================
    with tab2:
        st.subheader("➕ 複数人に同じ課題を一括登録")
        
        df_students = get_all_student_grades()
        
        if df_students.empty:
            st.warning("生徒データが取得できません。少し待ってから再読み込みしてください。")
        else:
            # 🏫 学校と学年のリストを作成
            # ※「設定_生徒情報」シートに「学校」という列がある前提です
            if '学校' in df_students.columns:
                valid_schools = [s for s in df_students['学校'].unique() if str(s).strip() != ""]
            else:
                valid_schools = []
                st.error("「設定_生徒情報」シートに「学校」という列が見つかりません！")

            valid_grades = [g for g in df_students['学年'].unique() if str(g).strip() != ""]
            
            col_filter1, col_filter2 = st.columns(2)
            with col_filter1:
                selected_school = st.selectbox("🏫 対象の学校", ["すべて"] + valid_schools)
            with col_filter2:
                selected_grade = st.selectbox("🎯 対象の学年", ["すべて"] + valid_grades)
            
            # 学校と学年でフィルターをかける
            filtered_df = df_students.copy()
            if selected_school != "すべて":
                filtered_df = filtered_df[filtered_df['学校'] == selected_school]
            if selected_grade != "すべて":
                filtered_df = filtered_df[filtered_df['学年'] == selected_grade]

            filtered_students = filtered_df['生徒名'].tolist()

            with st.form("add_multi_hw_form"):
                st.write(f"**該当する生徒: {len(filtered_students)}名**")
                selected_students = st.multiselect(
                    "👤 対象の生徒（×で外したり、追加できます）", 
                    options=df_students['生徒名'].tolist(),
                    default=filtered_students
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    subject = st.selectbox("教科", ["英語", "数学", "国語", "理科", "社会", "音楽", "美術", "保体", "技家", "その他"])
                with col2:
                    deadline = st.date_input("提出期限", date.today())
                    
                content = st.text_input("課題内容 (例: 学校ワーク P10〜P25)")
                memo = st.text_area("メモ (LINEでの補足情報など)")
                
                if st.form_submit_button("一括登録する！"):
                    if not selected_students:
                        st.error("生徒を1人以上選択してください！")
                    elif not content:
                        st.error("課題内容は必須です！")
                    else:
                        with st.spinner("スプレッドシートに一括登録しています..."):
                            # 返り値が2つ（成否, エラー文）になったので受け取る
                            is_success, error_msg = add_school_homework_multi(selected_students, subject, content, deadline, memo)
                            
                            if is_success:
                                st.success(f"{len(selected_students)}名に {subject} の課題を登録しました！")
                                import time
                                time.sleep(1)
                                st.rerun()
                            else:
                                # ⚠️ ここで具体的なエラーメッセージを表示します！
                                st.error(f"登録に失敗しました。詳細エラー: {error_msg}")