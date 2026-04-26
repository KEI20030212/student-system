import streamlit as st
import pandas as pd
import altair as alt
import datetime 
import time 
import random
import gspread 
import re

# 🌟 api_guard.py から robust_api_call を呼び出す（ファイルの場所に合わせて変更してください）
from utils.api_guard import robust_api_call 

from utils.g_sheets import (
    get_all_student_names,
    get_all_student_info_dict,
    load_all_data,
    load_quiz_records,
    get_quiz_maker_sheets,
    get_student_self_study_points,
    load_test_scores
)
from utils.calc_logic import (
    calculate_quiz_points,
    calculate_ability_rank,
    calculate_motivation_rank
)

def calc_pages_from_text(text):
    if pd.isna(text): return 0
    matches = re.findall(r'(\d+)\s*[~〜\-ー]\s*(\d+)', str(text))
    total = 0
    for start_str, end_str in matches:
        total += abs(int(end_str) - int(start_str)) + 1
    return total

def render_dashboard_page():
    st.subheader("🌐 クラス全体ダッシュボード") 

    today = datetime.date.today()
    month_options = [(today - datetime.timedelta(days=i*30)).strftime("%Y年%m月") for i in range(12)]
    month_options.insert(0, "全期間") 

    # 🛡️ ガード適用 1: 生徒名リストの取得
    student_names = robust_api_call(get_all_student_names, fallback_value=[])
    if not student_names: return
    
    all_grades = ["すべて"]
    all_subjects = ["すべて"]
    
    with st.spinner("☁️ 生徒基本データを一括読み込み中...（通信は1回だけ！一瞬で終わります🚀）"):
        # 🛡️ ガード適用 2: 生徒情報の取得
        student_info_dict = robust_api_call(get_all_student_info_dict, fallback_value={})
        
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
            
    with st.form("dashboard_filter_form"):
        selected_period = st.selectbox("📅 集計期間を選択", month_options)
        
        col1, col2 = st.columns(2)
        with col1:
            selected_grade = st.selectbox("🎯 学年で絞り込み", all_grades)
        with col2:
            selected_subject = st.selectbox("📚 科目で絞り込み", all_subjects)
            
        submit_button = st.form_submit_button("🚀 この条件で集計を開始する")

    if not submit_button:
        st.info("👆 上のメニューから条件を選んで、「集計を開始する」ボタンを押してください。")
        return
    
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
    
    matrix_placeholder = st.empty()

    current_month_str = datetime.date.today().strftime("%Y年%m月")
    summary_data = []
    matrix_data = []

    with st.spinner('☁️ 全生徒の共通テスト記録を読み込み中...'):
        # 🛡️ ガード適用 3: 小テスト記録（ごちゃごちゃしたtry-exceptは削除し、一行に！）
        df_all_quizzes = robust_api_call(load_quiz_records, fallback_value=pd.DataFrame())
        # APIエラーで返ってきたダミーのDataFrameじゃないか確認してから処理する
        if not df_all_quizzes.empty and '日時' in df_all_quizzes.columns and 'APIエラー発生' not in df_all_quizzes.columns:
            df_all_quizzes['日時'] = pd.to_datetime(df_all_quizzes['日時'], format='mixed', errors='coerce')

    with st.spinner("☁️ 小テストの満点データを読み込み中..."):
        # 🛡️ ガード適用 4: 小テスト設定データの取得
        quiz_master_dict = robust_api_call(get_quiz_maker_sheets, fallback_value={})

    with st.spinner("☁️ 模試・内申点データを照合中..."):
        # 🛡️ ガード適用 5: 模試・内申データの取得
        df_all_tests = robust_api_call(load_test_scores, fallback_value=pd.DataFrame())

    with st.spinner(f'☁️ {current_month_str} のデータを集計中...（※途中でAPIが混み合っても自動復帰します）'):
        progress_bar_data = st.progress(0)
        total_targets = len(target_students)
        
        for i, s_name in enumerate(target_students):
            info = student_info_dict.get(s_name, {})
            
            # 🛡️ ガード適用 6: 個人データの取得（引数s_nameを渡す）
            # 万が一ダメでも、画面が止まらないように notify=False にしてトースト通知だけに留めることも可能ですが、
            # dashboardの根幹なので通常の通知（notify=True）でお任せします。
            df_personal = robust_api_call(load_all_data, s_name, fallback_value=pd.DataFrame())

            # B. 小テストとポイントは、共通シート(df_all_quizzes)からその子の分だけ抜き出す
            if not df_all_quizzes.empty and '名前' in df_all_quizzes.columns:
                df_student_quizzes = df_all_quizzes[df_all_quizzes['名前'] == s_name].copy()
            else:
                df_student_quizzes = pd.DataFrame()
            
            adv_pages = 0
            avg_score = None
            total_quiz_pts = 0

            if not df_student_quizzes.empty:
                if selected_period == "全期間":
                    q_filtered = df_student_quizzes
                else:
                    q_filtered = df_student_quizzes[df_student_quizzes['日時'].dt.strftime("%Y年%m月") == selected_period]

                if not q_filtered.empty and '点数' in q_filtered.columns:
                    valid_scores = []
                    for index, row in q_filtered.iterrows():
                        score_val = row['点数']
                        quiz_name = row.get('テキスト', '') 

                        if pd.isna(score_val) or str(score_val).strip() == "":
                            continue
                            
                        try:
                            numeric_score = float(score_val)
                            valid_scores.append(numeric_score)
                            total_quiz_pts += calculate_quiz_points(numeric_score, quiz_name, quiz_master_dict)
                        except ValueError:
                            pass 

                    if valid_scores:
                        avg_score = sum(valid_scores) / len(valid_scores)
            
            # 🛡️ ガード適用 7: 自習ポイントの取得
            self_study_pts = robust_api_call(get_student_self_study_points, s_name, fallback_value=0)

            final_total_points = total_quiz_pts + self_study_pts

            # --- 進捗の計算 (個別シートを使用) ---
            if not df_personal.empty and 'APIエラー発生' not in df_personal.columns:
                df_p_filtered = df_personal.copy()

                if selected_subject != "すべて" and '科目' in df_p_filtered.columns:
                    df_p_filtered = df_p_filtered[df_p_filtered['科目'].str.contains(selected_subject, na=False)]
                
                if '日時' in df_p_filtered.columns:
                    df_p_filtered['日時'] = pd.to_datetime(df_p_filtered['日時'], format='mixed', errors='coerce')
                    if selected_period != "全期間":
                        df_p_filtered = df_p_filtered[df_p_filtered['日時'].dt.strftime("%Y年%m月") == selected_period]
                        
                try:
                    if '終了ページ' in df_p_filtered.columns:
                        df_p_filtered['今回の進捗'] = df_p_filtered['終了ページ'].apply(calc_pages_from_text)
                        adv_pages = int(df_p_filtered['今回の進捗'].sum())
                    else:
                        adv_pages = 0
                except Exception as e:
                    adv_pages = 0

            # ① 能力 (X) を計算する
            latest_dev, latest_naishin = 50.0, 3 
            if not df_all_tests.empty and '生徒名' in df_all_tests.columns and 'APIエラー発生' not in df_all_tests.columns:
                df_s = df_all_tests[df_all_tests['生徒名'] == s_name]
                if not df_s.empty:
                    df_moshi = df_s[df_s['テスト種別'] == "外部模試"]
                    if not df_moshi.empty and f"{selected_subject} 偏差値" in df_moshi.columns:
                        val = df_moshi.iloc[-1][f"{selected_subject} 偏差値"]
                        if pd.notna(val) and str(val).replace('.','',1).isdigit(): latest_dev = float(val)
                    
                    df_naishin = df_s[df_s['テスト種別'] == "通知表（内申点）"]
                    if not df_naishin.empty and f"{selected_subject} 内申" in df_naishin.columns:
                        val = df_naishin.iloc[-1][f"{selected_subject} 内申"]
                        if pd.notna(val) and str(val).isdigit(): latest_naishin = int(val)
            
            ability_x = calculate_ability_rank(latest_naishin, latest_dev)

            # ② やる気 (Y) を計算する
            raw_hw_rate = str(info.get('宿題履行率', '0.0')).replace('%', '').strip()
            try: hw_rate = float(raw_hw_rate)
            except ValueError: hw_rate = 0.0
            
            motivation_y = calculate_motivation_rank(hw_rate, final_total_points, self_study_pts)

            # ③ マトリクス用のリストに追加
            matrix_data.append({
                "生徒名": s_name,
                "能力 (X)": ability_x,
                "やる気 (Y)": motivation_y
            })

            summary_data.append({
                "生徒名": s_name, 
                "選択期間の進捗(ページ)": adv_pages, 
                "選択期間の平均点": round(avg_score, 1) if pd.notna(avg_score) else None, 
                "選択期間の獲得ポイント": final_total_points 
            })
            
            progress_bar_data.progress((i + 1) / total_targets)
            
        progress_bar_data.empty()

    if matrix_data:
        df_matrix = pd.DataFrame(matrix_data)
        chart = alt.Chart(df_matrix).mark_circle(size=400, opacity=0.8, color="#1E90FF").encode(
            x=alt.X('能力 (X)', scale=alt.Scale(domain=[0.5, 5.5]), axis=alt.Axis(values=[1, 2, 3, 4, 5]), title="🧠 能力 (1〜5)"),
            y=alt.Y('やる気 (Y)', scale=alt.Scale(domain=[0.5, 5.5]), axis=alt.Axis(values=[1, 2, 3, 4, 5]), title="🔥 やる気 (1〜5)"),
            tooltip=['生徒名', '能力 (X)', 'やる気 (Y)']
        )
        text = chart.mark_text(align='left', baseline='middle', dx=15, dy=0, fontSize=12, fontWeight='bold').encode(text='生徒名')
        rule_x = alt.Chart(pd.DataFrame({'x': [3]})).mark_rule(color='gray', strokeDash=[5,5]).encode(x='x')
        rule_y = alt.Chart(pd.DataFrame({'y': [3]})).mark_rule(color='gray', strokeDash=[5,5]).encode(y='y')

        matrix_placeholder.altair_chart(chart + text + rule_x + rule_y, use_container_width=True)    

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