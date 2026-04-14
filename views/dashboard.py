import streamlit as st
import pandas as pd
import altair as alt
import datetime 
import time 
import random
import gspread # 🌟 APIエラーを検知するために追加
import re

from utils.g_sheets import (
    get_all_student_names,
    get_all_student_info_dict,
    load_all_data,
    load_quiz_records
)
from utils.calc_logic import calculate_quiz_points 

def render_dashboard_page():
    st.subheader("🌐 クラス全体ダッシュボード") # 親にヘッダーがあるので少し小さく変更

    today = datetime.date.today()
    month_options = [(today - datetime.timedelta(days=i*30)).strftime("%Y年%m月") for i in range(12)]
    month_options.insert(0, "全期間") # 「全期間」という選択肢も追加
    selected_period = st.selectbox("📅 集計期間を選択", month_options)

    student_names = get_all_student_names()
    if not student_names: return
    
    all_grades = ["すべて"]
    all_subjects = ["すべて"]
    
    with st.spinner("☁️ 生徒基本データを一括読み込み中...（通信は1回だけ！一瞬で終わります🚀）"):
        student_info_dict = get_all_student_info_dict() 
        
        for s_name in student_names:
            info = student_info_dict.get(s_name, {})
            
            grade = info.get('学年', '未設定')
            if grade not in all_grades and grade != "未設定" and str(grade).strip() != "":
                all_grades.append(grade)
                
            subject_raw = str(info.get('受講科目', '未設定'))
            if subject_raw != "未設定" and subject_raw.strip() != "":
                for sub in subject_raw.replace('、', ',').split(','):
                    sub = sub.strip()
                    if sub and sub not in all_subjects:
                        all_subjects.append(sub)
            
    col1, col2 = st.columns(2)
    with col1:
        selected_grade = st.selectbox("🎯 学年で絞り込み", all_grades)
    with col2:
        selected_subject = st.selectbox("📚 科目で絞り込み", all_subjects)
    
    target_students = []
    for s in student_names:
        info = student_info_dict.get(s, {})
        
        match_grade = (selected_grade == "すべて" or info.get('学年') == selected_grade)
        student_subject_str = str(info.get('受講科目', ''))
        match_subject = (selected_subject == "すべて" or selected_subject in student_subject_str)
        
        if match_grade and match_subject:
            target_students.append(s)

    if not target_students:
        st.warning("該当する生徒がいません。")
        return

    st.markdown(f"**🗺️ 教室全体 俯瞰マトリクス ({selected_grade} / {selected_subject})**")
    
    matrix_data = []
    for s_name in target_students:
        info = student_info_dict.get(s_name, {})
        matrix_data.append({
            "生徒名": s_name,
            "能力 (X)": int(info.get('能力', 3) or 3),
            "やる気 (Y)": int(info.get('やる気', 3) or 3)
        })
    df_matrix = pd.DataFrame(matrix_data)
    
    chart = alt.Chart(df_matrix).mark_circle(size=400, opacity=0.8, color="#1E90FF").encode(
        x=alt.X('能力 (X)', scale=alt.Scale(domain=[0.5, 5.5]), title="🧠 能力 (1〜5)"),
        y=alt.Y('やる気 (Y)', scale=alt.Scale(domain=[0.5, 5.5]), title="🔥 やる気 (1〜5)"),
        tooltip=['生徒名', '能力 (X)', 'やる気 (Y)']
    )
    text = chart.mark_text(align='left', baseline='middle', dx=15, dy=0, fontSize=12, fontWeight='bold').encode(text='生徒名')
    rule_x = alt.Chart(pd.DataFrame({'x': [3]})).mark_rule(color='gray', strokeDash=[5,5]).encode(x='x')
    rule_y = alt.Chart(pd.DataFrame({'y': [3]})).mark_rule(color='gray', strokeDash=[5,5]).encode(y='y')
    st.altair_chart(chart + text + rule_x + rule_y, use_container_width=True)

    current_month_str = datetime.date.today().strftime("%Y年%m月")
    summary_data = []
    with st.spinner('☁️ 全生徒の共通テスト記録を読み込み中...'):
        df_all_quizzes = pd.DataFrame()
        for attempt in range(3): # ここにもバックオフを入れておくと安心
            try:
                df_all_quizzes = load_quiz_records()
                if not df_all_quizzes.empty and '日時' in df_all_quizzes.columns:
                    df_all_quizzes['日時'] = pd.to_datetime(df_all_quizzes['日時'], format='mixed', errors='coerce')
                break
            except:
                time.sleep(2)

    with st.spinner(f'☁️ {current_month_str} のデータを集計中...（※途中でAPIが混み合っても自動復帰します）'):
        progress_bar_data = st.progress(0)
        total_targets = len(target_students)
        
        for i, s_name in enumerate(target_students):
            # 🌟 APIエラー対策：各生徒のデータ取得時に最大3回リトライ！
            df_personal = pd.DataFrame()

            max_retries = 4 # 最大4回挑戦する（0, 1, 2, 3）
            for attempt in range(max_retries):
                try:
                    df_personal = load_all_data(s_name)
                    break 
                except gspread.exceptions.APIError:
                    if attempt < max_retries - 1:
                        # 待機時間を指数関数的に増やす (1秒 → 2秒 → 4秒) + ランダムなズレ(0〜1秒)
                        sleep_time = (2 ** attempt) + random.uniform(0, 1)
                        time.sleep(sleep_time)
                    else:
                        st.toast(f"{s_name}さんのデータ取得に失敗しました", icon="⚠️")
                except Exception:
                    break # その他のエラーは抜ける
            if i == 0 and not df_personal.empty:
                st.write(f"デバッグ用（{s_name}さんのシートの列名）:", df_personal.columns.tolist())

            # B. 小テストとポイントは、共通シート(df_all_quizzes)からその子の分だけ抜き出す
            if not df_all_quizzes.empty and '名前' in df_all_quizzes.columns:
                # その生徒の名前でフィルタリング
                df_student_quizzes = df_all_quizzes[df_all_quizzes['名前'] == s_name].copy()
            else:
                df_student_quizzes = pd.DataFrame()
            
            adv_pages, avg_score, total_points = 0, None, 0
            
            # --- ポイント・平均点の計算 (共通シートから抜き出したデータを使用) ---
            if not df_student_quizzes.empty:
                # 期間絞り込み
                if selected_period == "全期間":
                    q_filtered = df_student_quizzes
                else:
                    q_filtered = df_student_quizzes[df_student_quizzes['日時'].dt.strftime("%Y年%m月") == selected_period]

                if not q_filtered.empty and '点数' in q_filtered.columns:
                    scores = pd.to_numeric(q_filtered['点数'], errors='coerce').dropna()
                    for s_val in scores:
                        total_points += calculate_quiz_points(s_val)
                    avg_score = scores.mean()

            # --- 進捗の計算 (個別シートを使用) ---
            if not df_personal.empty:
                # ページ進捗は日付で絞り込んで計算
                df_p_filtered = df_personal.copy()

                # 2. 科目で絞り込み (重要！他の科目のページが混ざらないように)
                if selected_subject != "すべて" and '科目' in df_p_filtered.columns:
                    # シートの「科目」列に、選択中の科目名が含まれる行だけにする
                    df_p_filtered = df_p_filtered[df_p_filtered['科目'].str.contains(selected_subject, na=False)]
                
                # 3. 期間で絞り込み
                if '日時' in df_p_filtered.columns:
                    df_p_filtered['日時'] = pd.to_datetime(df_p_filtered['日時'], format='mixed', errors='coerce')
                    if selected_period != "全期間":
                        df_p_filtered = df_p_filtered[df_p_filtered['日時'].dt.strftime("%Y年%m月") == selected_period]
                        
                # 🌟 4. 進捗（ページ数）の計算（複数行・範囲指定対応バージョン！）
                try:
                    if '終了ページ' in df_p_filtered.columns:
                        # 各行のテキストから進捗を計算する専用の関数をその場で作る
                        def calc_pages_from_text(text):
                            if pd.isna(text): return 0
                            # 「数字」+「〜 や - など」+「数字」 のペアをすべて見つけ出す
                            matches = re.findall(r'(\d+)\s*[~〜\-ー]\s*(\d+)', str(text))
                            total = 0
                            for start_str, end_str in matches:
                                # 右の数字 - 左の数字 を計算（逆に書いてあっても大丈夫なように絶対値をとる）
                                total += abs(int(end_str) - int(start_str)) + 1
                            return total

                        # 各行の「終了ページ」に上の関数を適用して、「今回の進捗」というデータを作る
                        df_p_filtered['今回の進捗'] = df_p_filtered['終了ページ'].apply(calc_pages_from_text)
                        
                        # その期間の進捗をすべて合計する
                        adv_pages = int(df_p_filtered['今回の進捗'].sum())
                    else:
                        adv_pages = 0
                except Exception as e:
                    adv_pages = 0

            summary_data.append({
                "生徒名": s_name, 
                "選択期間の進捗(ページ)": adv_pages, 
                "選択期間の平均点": round(avg_score, 1) if pd.notna(avg_score) else None, 
                "選択期間の獲得ポイント": total_points 
            })
            
            time.sleep(0.5) # 元からある息継ぎ
            progress_bar_data.progress((i + 1) / total_targets)
            
        progress_bar_data.empty()

    if summary_data:
        df_summary = pd.DataFrame(summary_data)
        st.markdown(f"**🏆 累計獲得ポイント ランキング TOP3 ({selected_grade} / {selected_subject})**")
        df_ranking = df_summary.sort_values(by="選択期間の獲得ポイント", ascending=False).head(3).reset_index(drop=True)
        
        cols = st.columns(3)
        colors, medals = ["#FFD700", "#C0C0C0", "#CD7F32"], ["🥇 1位", "🥈 2位", "🥉 3位"]
        
        for i in range(min(3, len(df_ranking))):
            with cols[i]:
                st.markdown(f"<div style='background-color:{colors[i]}15; padding:15px; border-radius:10px; border: 2px solid {colors[i]}; text-align:center;'><h3>{medals[i]}</h3><h2>{df_ranking.loc[i, '生徒名']}</h2><h1>{df_ranking.loc[i, '選択期間の獲得ポイント']} <span style='font-size:0.4em;'>pt</span></h1></div>", unsafe_allow_html=True)

        st.divider()
        st.markdown(f"**📊 選択期間の状況 ({selected_grade} / {selected_subject})**")
        c1, c2 = st.columns(2)
        
        with c1: 
            st.write("**📖 進捗ランキング**")
            st.dataframe(df_summary.sort_values(by="選択期間の進捗(ページ)", ascending=False)[["生徒名", "選択期間の進捗(ページ)"]], hide_index=True, use_container_width=True)
            
        with c2: 
            st.write("**💯 小テスト平均点**")
            st.dataframe(df_summary.dropna(subset=["選択期間の平均点"]).sort_values(by="選択期間の平均点", ascending=False)[["生徒名", "選択期間の平均点"]], hide_index=True, use_container_width=True)