import streamlit as st
import pandas as pd
from datetime import date, datetime
import time
from utils.g_sheets import (
    load_school_homework_data, 
    update_homework_status, 
    add_school_homework_multi, 
    get_all_student_grades
)

def render_school_homework_page():
    st.header("🎒 学校課題管理（内申点対策）")
    
    tab1, tab2 = st.tabs(["📋 提出アラート・進捗更新", "➕ 課題の一括登録（学校・学年指定）"])

    # ==========================================
    # タブ1：アラート・進捗更新（生徒ごとの状況確認）
    # ==========================================
    with tab1:
        st.write("「完了（終わった）」と「提出済（学校に出した）」を分けて管理します。")
        df = load_school_homework_data()
        
        if df.empty:
            st.info("現在、登録されている学校の課題はありません。")
        else:
            df_active = df[df["ステータス"] != "提出済"].copy()
            # 日付変換のエラー対策
            df_active["提出期限"] = pd.to_datetime(df_active["提出期限"], errors='coerce').dt.date
            df_active = df_active.dropna(subset=["提出期限"]).sort_values("提出期限")

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
                            st.success(f"{row['生徒名']}さんの状況を更新しました！")
                            st.rerun()

    # ==========================================
    # タブ2：学校 × 学年 での超シンプル一括登録
    # ==========================================
    with tab2:
        st.subheader("➕ 学校・学年を指定して一括登録")
        st.info("生徒を一人ずつ選ぶ必要はありません。指定した条件に合う生徒全員に一括で課題を追加します。")
        
        df_students = get_all_student_grades()
        
        if df_students.empty:
            st.warning("生徒データが取得できません。設定_生徒情報シートを確認してください。")
        else:
            # 🏫 フィルターの準備
            if '学校名' in df_students.columns:
                valid_schools = sorted([s for s in df_students['学校名'].unique() if str(s).strip() != ""])
            else:
                st.error("「設定_生徒情報」シートに「学校名」列がありません。")
                return

            valid_grades = sorted([g for g in df_students['学年'].unique() if str(g).strip() != ""])
            
            # --- 入力フォーム ---
            with st.form("simple_add_form"):
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    target_school = st.selectbox("🏫 対象の学校", valid_schools)
                with col_f2:
                    target_grade = st.selectbox("🎯 対象の学年", valid_grades)
                
                # この時点で該当する生徒を裏でリストアップ
                target_student_list = df_students[
                    (df_students['学校名'] == target_school) & 
                    (df_students['学年'] == target_grade)
                ]['生徒名'].tolist()
                
                st.write(f"💡 **対象生徒:** {', '.join(target_student_list) if target_student_list else '該当者なし'}")
                
                st.divider()
                
                col1, col2 = st.columns(2)
                with col1:
                    subject = st.selectbox("教科", ["英語", "数学", "国語", "理科", "社会", "音楽", "美術", "保体", "技家", "その他"])
                with col2:
                    deadline = st.date_input("提出期限", date.today())
                    
                content = st.text_input("課題内容 (例: 学校ワーク P10〜P25)")
                memo = st.text_area("メモ (LINEでの補足情報など)")
                
                submitted = st.form_submit_button("この学校・学年の全員に登録！", use_container_width=True)
                
                if submitted:
                    if not target_student_list:
                        st.error(f"{target_school}の{target_grade}に該当する生徒がいません。")
                    elif not content:
                        st.error("課題内容は必須です！")
                    else:
                        with st.spinner("一括登録中..."):
                            is_success, error_msg = add_school_homework_multi(
                                target_student_list, subject, content, deadline, memo
                            )
                            if is_success:
                                st.success(f"【{target_school} {target_grade}】の{len(target_student_list)}名に登録完了！")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"登録失敗: {error_msg}")