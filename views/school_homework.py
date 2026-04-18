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
    col_h, col_r = st.columns([0.8, 0.2])
    with col_h:
        st.header("🎒 学校課題管理")
    with col_r:
        if st.button("🔄 情報を更新"):
            load_school_homework_data.clear()
            st.rerun()
    # 🌟 タブを3つに増やしました！
    tab1, tab2, tab3 = st.tabs(["📋 提出アラート・進捗更新", "➕ 課題の一括登録", "📊 進捗ダッシュボード"])

    # ==========================================
    # タブ1：アラート・進捗更新（🔥ヤバさ優先ソート版）
    # ==========================================
    with tab1:
        st.write("「完了（終わった）」と「提出済（学校に出した）」を分けて管理します。")
        df = load_school_homework_data()
        
        if df.empty:
            st.info("現在、登録されている学校の課題はありません。")
        else:
            df_active = df[df["ステータス"] != "提出済"].copy()
            df_active["提出期限"] = pd.to_datetime(df_active["提出期限"], errors='coerce').dt.date
            df_active = df_active.dropna(subset=["提出期限"])

            today = date.today()

            # 🌟 新機能：優先度（ヤバさ）を計算するロジック
            def get_priority(row):
                if row["ステータス"] == "完了":
                    return 4  # すでに終わっているものは一番下（あとは出すだけ）
                
                days_left = (row["提出期限"] - today).days
                if days_left < 0:
                    return 1  # 🔥 期限超過（最優先で対応！）
                elif days_left <= 2:
                    return 2  # 🚨 期限直前（今日・明日・明後日）
                else:
                    return 3  # 🟢 まだ余裕あり

            # 優先度列を追加して、優先度 ＞ 提出期限 の順番で並び替え！
            df_active["優先度"] = df_active.apply(get_priority, axis=1)
            df_active = df_active.sort_values(["優先度", "提出期限"])

            # 画面への表示
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
                        with st.spinner("スプレッドシートに反映中..."):
                            if update_homework_status(row.name + 2, new_status):
                                # 🌟 1. まずキャッシュを明示的にクリア
                                load_school_homework_data.clear()
                                
                                # 🌟 2. Google側の反映を待つ（0.5秒だと短い場合があるので1.5秒に）
                                time.sleep(1.5)
                                
                                # 🌟 3. 再読み込みして最新データを強制取得
                                st.success(f"{row['生徒名']}さんの状況を更新しました！")
                                st.rerun()

    # ==========================================
    # タブ2：学校 × 学年 での一括登録
    # ==========================================
    with tab2:
        st.subheader("➕ 学校・学年を指定して一括登録")
        st.info("課題内容を改行して入力すると、一度に複数の課題を登録できます。")
        
        df_students = get_all_student_grades()
        
        if df_students.empty:
            st.warning("生徒データが取得できません。設定_生徒情報シートを確認してください。")
        else:
            if '学校名' in df_students.columns:
                valid_schools = sorted([s for s in df_students['学校名'].unique() if str(s).strip() != ""])
            else:
                st.error("「設定_生徒情報」シートに「学校名」列が見つかりません。")
                return

            valid_grades = sorted([g for g in df_students['学年'].unique() if str(g).strip() != ""])
            
            with st.form("simple_add_form"):
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    target_school = st.selectbox("🏫 対象の学校名", valid_schools)
                with col_f2:
                    target_grade = st.selectbox("🎯 対象の学年", valid_grades)
                
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
                
                content_text = st.text_area(
                    "課題内容 (1行に1つずつ入力してください)",
                    placeholder="数学ワーク P10-P20\n計算プリント No.5\n英単語テストの練習"
                )
                
                memo = st.text_area("メモ (全課題に共通して保存されます)")
                
                submitted = st.form_submit_button("一括登録する！", use_container_width=True)
                
                if submitted:
                    task_list = [t.strip() for t in content_text.split("\n") if t.strip()]
                    
                    if not target_student_list:
                        st.error(f"{target_school}の{target_grade}に該当する生徒がいません。")
                    elif not task_list:
                        st.error("課題内容を1つ以上入力してください！")
                    else:
                        with st.spinner("一括登録中..."):
                            is_success, error_msg = add_school_homework_multi(
                                target_student_list, subject, task_list, deadline, memo
                            )
                            if is_success:
                                st.success(f"【{target_school} {target_grade}】の{len(target_student_list)}名に、{len(task_list)}個の課題を登録しました！")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"登録失敗: {error_msg}")

    # ==========================================
    # タブ3：📊 進捗ダッシュボード（New!）
    # ==========================================
    with tab3:
        st.subheader("📊 生徒別の課題進捗状況")
        st.write("各生徒の課題消化率を棒グラフで確認できます。")
        
        # ※データ読み込みはタブ1で読んだdfがあればそれを使うこともできますが、念のため再取得
        df_dash = load_school_homework_data()
        
        if df_dash.empty:
            st.info("現在、登録されている課題はありません。")
        else:
            # 課題が登録されている生徒の一覧を取得
            students_with_hw = sorted(df_dash['生徒名'].unique())
            
            for student in students_with_hw:
                student_hw = df_dash[df_dash['生徒名'] == student]
                
                # 全課題数と、各ステータスの数をカウント
                total_hw = len(student_hw)
                completed_hw = len(student_hw[student_hw['ステータス'] == '完了'])
                submitted_hw = len(student_hw[student_hw['ステータス'] == '提出済'])
                
                # 「完了」または「提出済」を達成としてカウント
                done_hw = completed_hw + submitted_hw
                
                # 進捗率（0.0 〜 1.0）
                progress_rate = done_hw / total_hw if total_hw > 0 else 0
                progress_percent = int(progress_rate * 100)
                
                # 表示の工夫：100%なら星マークをつけて褒める
                star = "✨ 完璧！" if progress_percent == 100 else ""
                
                st.write(f"#### 👤 {student} （{done_hw} / {total_hw} 完了） **{progress_percent}%** {star}")
                st.progress(progress_rate) # これがプログレスバー（棒グラフ）！
                
                # まだ終わっていない課題があれば、折りたたみで表示
                unfinished_hw = student_hw[~student_hw['ステータス'].isin(['完了', '提出済'])]
                if not unfinished_hw.empty:
                    with st.expander("📝 残りの課題を見る"):
                        for _, row in unfinished_hw.iterrows():
                            # 期限までの日数を計算
                            try:
                                dl_date = pd.to_datetime(row["提出期限"]).date()
                                days_left = (dl_date - date.today()).days
                                warning = f"🚨(期限まで{days_left}日)" if days_left <= 3 else ""
                            except:
                                warning = ""
                            
                            st.write(f"- 【{row['教科']}】 {row['課題内容']} {warning} （現在の状態: {row['ステータス']}）")
                st.divider()