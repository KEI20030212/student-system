import streamlit as st
import pandas as pd
import altair as alt
import datetime 

# 裏方部隊から、スプレッドシートのデータを読み込む関数を呼び出します
from utils.g_sheets import (
    get_all_student_names,
    get_student_info,
    load_all_data
)
# 計算ロジック部隊からポイント計算関数を呼び出します
from utils.calc_logic import calculate_quiz_points 

def render_dashboard_page():
    st.header("🌐 クラス全体ダッシュボード")
    student_names = get_all_student_names()
    if not student_names: return
    
    all_grades = ["すべて"]
    all_subjects = ["すべて"] # 📚 追加：科目のリスト
    student_info_dict = {}
    
    for s_name in student_names:
        info = get_student_info(s_name)
        student_info_dict[s_name] = info
        
        # 学年リストの作成
        grade = info.get('学年', '未設定')
        if grade not in all_grades and grade != "未設定" and str(grade).strip() != "":
            all_grades.append(grade)
            
        # 科目リストの作成（追加！）
        # 「英語,数学」など複数書かれている場合を考慮して分割します
        subject_raw = str(info.get('受講科目', '未設定'))
        if subject_raw != "未設定" and subject_raw.strip() != "":
            for sub in subject_raw.replace('、', ',').split(','):
                sub = sub.strip()
                if sub and sub not in all_subjects:
                    all_subjects.append(sub)
            
    # 🎛️ 学年と科目のコントローラーを横並びで配置
    col1, col2 = st.columns(2)
    with col1:
        selected_grade = st.selectbox("🎯 学年で絞り込み", all_grades)
    with col2:
        selected_subject = st.selectbox("📚 科目で絞り込み", all_subjects)
    
    # 🎯 ターゲット生徒の絞り込み（学年 ＆ 科目のダブルフィルター！）
    target_students = []
    for s in student_names:
        info = student_info_dict[s]
        
        # 1. 学年の判定
        match_grade = (selected_grade == "すべて" or info.get('学年') == selected_grade)
        
        # 2. 科目の判定（「すべて」か、生徒の科目欄に選択した科目の文字が含まれているか）
        student_subject_str = str(info.get('受講科目', ''))
        match_subject = (selected_subject == "すべて" or selected_subject in student_subject_str)
        
        if match_grade and match_subject:
            target_students.append(s)

    if not target_students:
        st.warning("該当する生徒がいません。")
        return

    # 🗺️ マトリクスのタイトルにも科目を反映！
    st.subheader(f"🗺️ 教室全体 俯瞰マトリクス ({selected_grade} / {selected_subject})")
    
    matrix_data = []
    for s_name in target_students:
        info = student_info_dict[s_name]
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
    
    with st.spinner('データを集計中...'):
        for s_name in target_students:
            df = load_all_data(s_name)
            adv_pages, avg_score, total_points = 0, None, 0
            
            if not df.empty:
                if '点数' in df.columns:
                    for s in pd.to_numeric(df['点数'], errors='coerce').dropna():
                        total_points += calculate_quiz_points(s)
                
                if '日時' in df.columns:
                    df['日時'] = pd.to_datetime(df['日時'], format='mixed', errors='coerce')
                    df_month = df[df['日時'].dt.strftime("%Y年%m月") == current_month_str]
                    
                    if not df_month.empty:
                        adv_pages = int(df_month['ページ数'].max() - df_month['ページ数'].min())
                        avg_score = pd.to_numeric(df_month['点数'], errors='coerce').mean()

            summary_data.append({
                "生徒名": s_name, 
                "今月の進捗(ページ)": adv_pages, 
                "小テスト平均点": round(avg_score, 1) if pd.notna(avg_score) else None, 
                "累計ポイント": total_points
            })

    if summary_data:
        df_summary = pd.DataFrame(summary_data)
        st.subheader(f"🏆 累計獲得ポイント ランキング TOP3 ({selected_grade} / {selected_subject})")
        df_ranking = df_summary.sort_values(by="累計ポイント", ascending=False).head(3).reset_index(drop=True)
        
        cols = st.columns(3)
        colors, medals = ["#FFD700", "#C0C0C0", "#CD7F32"], ["🥇 1位", "🥈 2位", "🥉 3位"]
        
        for i in range(min(3, len(df_ranking))):
            with cols[i]:
                st.markdown(f"<div style='background-color:{colors[i]}15; padding:15px; border-radius:10px; border: 2px solid {colors[i]}; text-align:center;'><h3>{medals[i]}</h3><h2>{df_ranking.loc[i, '生徒名']}</h2><h1>{df_ranking.loc[i, '累計ポイント']} <span style='font-size:0.4em;'>pt</span></h1></div>", unsafe_allow_html=True)

        st.divider()
        st.subheader(f"📊 {current_month_str} の状況 ({selected_grade} / {selected_subject})")
        c1, c2 = st.columns(2)
        
        with c1: 
            st.write("**📖 進捗ランキング**")
            st.dataframe(df_summary.sort_values(by="今月の進捗(ページ)", ascending=False)[["生徒名", "今月の進捗(ページ)"]], hide_index=True, use_container_width=True)
            
        with c2: 
            st.write("**💯 小テスト平均点**")
            st.dataframe(df_summary.dropna(subset=["小テスト平均点"]).sort_values(by="小テスト平均点", ascending=False)[["生徒名", "小テスト平均点"]], hide_index=True, use_container_width=True)