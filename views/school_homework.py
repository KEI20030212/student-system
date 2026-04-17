# views/school_homework.py として新規作成

import streamlit as st
import pandas as pd
from datetime import date, datetime
from utils.g_sheets import load_school_homework_data, add_school_homework, update_homework_status

def render_school_homework_page():
    st.header("🎒 学校課題管理（内申点対策）")
    
    tab1, tab2 = st.tabs(["📋 提出期限アラート・更新", "➕ 新規課題登録"])

    with tab1:
        df = load_school_homework_data()
        
        if df.empty:
            st.info("現在、登録されている学校の課題はありません。")
        else:
            # 提出済以外のものを優先表示
            df_active = df[df["ステータス"] != "提出済"].copy()
            df_active["提出期限"] = pd.to_datetime(df_active["提出期限"]).dt.date
            df_active = df_active.sort_values("提出期限")

            st.subheader("🚨 未提出の課題")
            today = date.today()

            for idx, row in df_active.iterrows():
                days_left = (row["提出期限"] - today).days
                
                # 期限に応じたラベルと色
                if days_left < 0:
                    label, color = f"【期限超過！】 {abs(days_left)}日経過", "red"
                    icon = "🔴"
                elif days_left <= 2:
                    label, color = f"【期限直前】 あと{days_left}日", "orange"
                    icon = "🟡"
                else:
                    label, color = f"あと{days_left}日", "green"
                    icon = "🟢"

                with st.expander(f"{icon} {row['生徒名']} : {row['教科']} - {row['課題内容']} ({label})"):
                    st.write(f"**提出期限:** {row['提出期限']}")
                    st.write(f"**内容:** {row['課題内容']}")
                    st.write(f"**メモ:** {row['メモ']}")
                    
                    # 更新用UI
                    new_status = st.selectbox(
                        "ステータス更新", 
                        ["未着手", "進行中", "完了", "提出済"],
                        index=["未着手", "進行中", "完了", "提出済"].index(row["ステータス"]),
                        key=f"status_{idx}"
                    )
                    
                    if st.button("更新を保存", key=f"btn_{idx}"):
                        # スプレッドシートは1行目がヘッダー、かつ1-indexなので idx + 2
                        if update_homework_status(idx + 2, new_status):
                            st.success("更新しました！")
                            st.rerun()

    with tab2:
        st.subheader("➕ LINE情報から課題を登録")
        # 既存の生徒リストを取得（utilsの関数を適宜使ってください）
        # ここでは簡易的に全データから生徒名を取得
        all_df = load_school_homework_data() # 本来は生徒名簿から取るのがベスト
        student_list = sorted(all_df["生徒名"].unique()) if not all_df.empty else ["生徒を登録してください"]

        with st.form("add_hw_form"):
            col1, col2 = st.columns(2)
            with col1:
                student = st.selectbox("生徒名", student_list)
                subject = st.selectbox("教科", ["英語", "数学", "国語", "理科", "社会", "音楽", "美術", "保体", "技家", "その他"])
            with col2:
                deadline = st.date_input("提出期限", date.today())
                
            content = st.text_input("課題内容 (例: ワークP10-P25)")
            memo = st.text_area("メモ (LINEでの補足情報など)")
            
            if st.form_submit_button("この内容で登録する"):
                if content:
                    if add_school_homework(student, subject, content, deadline, memo):
                        st.success(f"{student}さんの課題を登録しました。")
                        st.rerun()
                else:
                    st.error("課題内容は必須です。")