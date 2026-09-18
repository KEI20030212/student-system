import streamlit as st
import pandas as pd
import altair as alt
import datetime 
import io  # 🌟 Excelダウンロード用に追加
import re

from utils.api_guard import robust_api_call 

# 🌟 自習時間のインポート（load_self_study_data）を追加
from utils.g_sheets import (
    get_student_master,
    get_all_logs,
    load_quiz_records,
    get_quiz_maker_sheets,
    get_student_self_study_points,
    load_test_scores,
    load_self_study_data 
)
from utils.calc_logic import (
    calculate_quiz_points,
    calculate_ability_rank,
    calculate_motivation_rank,
    calc_pages_from_text
)

def render_dashboard_page():
    st.subheader("🌐 クラス全体ダッシュボード（司令塔）") 
    st.caption("教室全体の状況を俯瞰し、「次の一手」を見つけるためのマネジメント画面です。")

    # ==========================================
    # 🔐 権限の確認（To-Doリストの表示制限）
    # ==========================================
    # ※システム（セッション）に保存されている役職情報を取得します。
    # ※設定がない場合のデフォルトは、テスト用に一時的に 'admin' にしています。
    user_role = str(st.session_state.get('role', st.session_state.get('user_role', 'admin'))).lower()
    has_manager_access = user_role in ['admin', 'am', 'owner']

    # --- 期間設定 ---
    today = datetime.date.today()
    month_options = [(today.replace(day=1) - pd.DateOffset(months=i)).strftime('%Y年%m月') for i in range(12)]
    
    all_grades = ["すべて"]
    all_subjects = ["すべて"]
    
    # 🌟 生徒マスターの一括読み込み
    with st.spinner("☁️ 生徒基本データを一括読み込み中..."):
        df_students = robust_api_call(get_student_master, fallback_value=pd.DataFrame())
        if df_students.empty:
            st.warning("生徒データが見つかりません。設定シートを確認してください。")
            return
            
        for _, row in df_students.iterrows():
            grade = row.get('学年', '未設定')
            if grade not in all_grades and grade != "未設定" and str(grade).strip() != "":
                all_grades.append(grade)
                
            subject_raw = str(row.get('受講科目', '未設定'))
            if subject_raw != "未設定" and subject_raw.strip() != "":
                for sub in subject_raw.replace('、', ',').split(','):
                    sub = sub.strip()
                    if sub and sub not in all_subjects:
                        all_subjects.append(sub)
            
    with st.form("dashboard_filter_form"):
        selected_period = st.selectbox("📅 集計期間（当月）を選択", month_options)
        
        col1, col2 = st.columns(2)
        with col1:
            selected_grade = st.selectbox("🎯 学年で絞り込み", all_grades)
        with col2:
            selected_subject = st.selectbox("📚 科目で絞り込み", all_subjects)
            
        submit_button = st.form_submit_button("🚀 この条件で集計を開始する")

    if not submit_button:
        st.info("👆 上のメニューから条件を選んで、「集計を開始する」ボタンを押してください。")
        return
    
    # 前月の算出
    try:
        current_idx = month_options.index(selected_period)
        prev_period = month_options[current_idx + 1] if current_idx + 1 < len(month_options) else None
    except ValueError:
        prev_period = None

    # ターゲット生徒のリストアップ
    target_students = []
    for _, row in df_students.iterrows():
        match_grade = (selected_grade == "すべて" or row.get('学年') == selected_grade)
        student_subject_str = str(row.get('受講科目', ''))
        match_subject = (selected_subject == "すべて" or selected_subject in student_subject_str)
        
        if match_grade and match_subject:
            target_students.append({
                "id": str(row.get('生徒ID', '')).strip(),
                "name": str(row.get('生徒名', '')).strip(),
                "info": row 
            })

    if not target_students:
        st.warning("該当する生徒がいません。")
        return

    # 🌟 必要なデータすべてを一括取得（超高速処理）
    with st.spinner('☁️ 授業ログ・自習・小テスト・模試データを一括集計中...'):
        df_all_logs = robust_api_call(get_all_logs, fallback_value=pd.DataFrame())
        if not df_all_logs.empty and '日時' in df_all_logs.columns:
            df_all_logs['日時'] = pd.to_datetime(df_all_logs['日時'], format='mixed', errors='coerce')
            df_all_logs['年月'] = df_all_logs['日時'].dt.strftime('%Y年%m月')

        df_all_quizzes = robust_api_call(load_quiz_records, fallback_value=pd.DataFrame())
        if not df_all_quizzes.empty and '日時' in df_all_quizzes.columns:
            df_all_quizzes['日時'] = pd.to_datetime(df_all_quizzes['日時'], format='mixed', errors='coerce')
            df_all_quizzes['年月'] = df_all_quizzes['日時'].dt.strftime('%Y年%m月')

        df_ss = robust_api_call(load_self_study_data, fallback_value=pd.DataFrame())
        if not df_ss.empty and '日付' in df_ss.columns:
            df_ss['日付'] = pd.to_datetime(df_ss['日付'], errors='coerce')
            df_ss['年月'] = df_ss['日付'].dt.strftime('%Y年%m月')

        quiz_master_dict = robust_api_call(get_quiz_maker_sheets, fallback_value={})
        df_all_tests = robust_api_call(load_test_scores, fallback_value=pd.DataFrame())

    # --- 集計用データの箱 ---
    summary_data = []
    matrix_data = []
    
    todo_praise = []
    todo_encourage = []
    todo_warn = []
    todo_contact = []

    progress_bar_data = st.progress(0)
    total_targets = len(target_students)
    
    for i, student in enumerate(target_students):
        s_id = student["id"]
        s_name = student["name"]

        # ==========================================
        # 【データ抽出】当月 ＆ 前月 のデータを切り出し
        # ==========================================
        # ログ（宿題計算用）
        logs_curr = df_all_logs[(df_all_logs['年月'] == selected_period) & (df_all_logs['名前' if '名前' in df_all_logs.columns else '生徒名'] == s_name)] if not df_all_logs.empty else pd.DataFrame()
        logs_prev = df_all_logs[(df_all_logs['年月'] == prev_period) & (df_all_logs['名前' if '名前' in df_all_logs.columns else '生徒名'] == s_name)] if not df_all_logs.empty and prev_period else pd.DataFrame()

        # 小テスト
        quiz_curr = df_all_quizzes[(df_all_quizzes['年月'] == selected_period) & (df_all_quizzes['名前'] == s_name)] if not df_all_quizzes.empty else pd.DataFrame()
        
        # 自習時間
        ss_curr = df_ss[(df_ss['年月'] == selected_period) & (df_ss['名前'] == s_name)] if not df_ss.empty else pd.DataFrame()
        ss_prev = df_ss[(df_ss['年月'] == prev_period) & (df_ss['名前'] == s_name)] if not df_ss.empty and prev_period else pd.DataFrame()

        # ==========================================
        # 【計算】当月の実績
        # ==========================================
        # 宿題達成率
        hw_rate_curr = 0
        if not logs_curr.empty and '出した宿題P' in logs_curr.columns and 'やった宿題P' in logs_curr.columns:
            assigned = pd.to_numeric(logs_curr['出した宿題P'], errors='coerce').fillna(0).sum()
            done = pd.to_numeric(logs_curr['やった宿題P'], errors='coerce').fillna(0).sum()
            if assigned > 0: hw_rate_curr = min(int((done / assigned) * 100), 100)
            else: hw_rate_curr = -1 # 宿題なし

        # 自習時間
        ss_min_curr = pd.to_numeric(ss_curr['自習時間(分)'], errors='coerce').sum() if not ss_curr.empty else 0
        
        # 小テスト平均とポイント
        quiz_avg_curr = 0
        quiz_pts_curr = 0
        if not quiz_curr.empty and '点数' in quiz_curr.columns:
            valid_scores = pd.to_numeric(quiz_curr['点数'], errors='coerce').dropna().tolist()
            if valid_scores: quiz_avg_curr = sum(valid_scores) / len(valid_scores)
            
            for _, r in quiz_curr.iterrows():
                try: quiz_pts_curr += calculate_quiz_points(float(r['点数']), r.get('テキスト', ''), quiz_master_dict)
                except: pass

        # 総合ポイント
        ss_pts_total = robust_api_call(get_student_self_study_points, s_name, fallback_value=0)
        final_points = quiz_pts_curr + ss_pts_total

        # ==========================================
        # 【計算】前月の実績（比較用）
        # ==========================================
        hw_rate_prev = 0
        if not logs_prev.empty and '出した宿題P' in logs_prev.columns:
            assigned_p = pd.to_numeric(logs_prev['出した宿題P'], errors='coerce').fillna(0).sum()
            done_p = pd.to_numeric(logs_prev['やった宿題P'], errors='coerce').fillna(0).sum()
            if assigned_p > 0: hw_rate_prev = min(int((done_p / assigned_p) * 100), 100)
            else: hw_rate_prev = -1

        ss_min_prev = pd.to_numeric(ss_prev['自習時間(分)'], errors='coerce').sum() if not ss_prev.empty else 0

        # ==========================================
        # 【能力(X) と やる気(Y) の算出】
        # ==========================================
        latest_dev, latest_naishin = 50.0, 3 
        if not df_all_tests.empty and '生徒名' in df_all_tests.columns:
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
        # ※やる気の計算には、今月のリアルな宿題達成率を使用（-1の場合はマスタのデフォルト等を使用する設計ですが、今回は0として計算）
        motivation_y = calculate_motivation_rank(max(hw_rate_curr, 0), final_points, ss_pts_total)

        # マトリクス用保存
        matrix_data.append({
            "生徒名": s_name, "能力 (X)": ability_x, "やる気 (Y)": motivation_y
        })

        # ==========================================
        # 🚨 【司令塔ロジック】To-Doミッションの自動判定
        # ==========================================
        ss_diff = ss_min_curr - ss_min_prev
        hw_diff = hw_rate_curr - hw_rate_prev if hw_rate_curr != -1 and hw_rate_prev != -1 else 0

        # 🟢 褒めるリスト（急上昇）
        if ss_diff >= 300: # 前月比+5時間
            todo_praise.append(f"**{s_name}**：自習時間が前月比 +{int(ss_diff/60)}時間です！隠れヒーローを褒めましょう。")
        elif hw_diff >= 20:
            todo_praise.append(f"**{s_name}**：宿題達成率が前月比 +{hw_diff}%改善しています！")

        # 🟡 励ますリスト（空回り）
        if hw_rate_curr >= 80 and quiz_avg_curr > 0 and quiz_avg_curr < 60:
            todo_encourage.append(f"**{s_name}**：宿題は{hw_rate_curr}%やっていますが、小テスト平均が{int(quiz_avg_curr)}点です。勉強のやり方の面談が必要です。")

        # 🔴 引き締めるリスト（サボり）
        if ss_diff <= -300:
            todo_warn.append(f"**{s_name}**：自習時間が前月から {int(abs(ss_diff)/60)}時間 減少しています。油断しているかも？")
        elif hw_diff <= -20:
            todo_warn.append(f"**{s_name}**：宿題達成率が前月から {abs(hw_diff)}% も落ちています。お尻を叩きましょう。")

        # 📞 保護者連絡リスト（要フォロー）
        if not logs_curr.empty and ss_min_curr == 0:
            todo_contact.append(f"**{s_name}**：今月授業を受けていますが、自習時間が0分です。ご家庭へ様子伺いの連絡を！")
        elif hw_rate_curr != -1 and hw_rate_curr < 50:
            todo_contact.append(f"**{s_name}**：宿題達成率が {hw_rate_curr}% です。ご家庭に注意喚起のLINEを推奨。")

        # --- ランキング・トレンド用保存 ---
        summary_data.append({
            "生徒名": s_name,
            "今月自習(分)": ss_min_curr,
            "前月比自習(分)": ss_diff,
            "今月宿題(%)": hw_rate_curr if hw_rate_curr != -1 else "-",
            "前月比宿題(%)": hw_diff,
            "小テスト平均": round(quiz_avg_curr, 1) if quiz_avg_curr > 0 else "-",
            "今月の獲得pt": final_points
        })

        progress_bar_data.progress((i + 1) / total_targets)
        
    progress_bar_data.empty()

    # ==========================================
    # 🎨 画面描画セクション
    # ==========================================
    
    # 🌟 柱1: 役職限定 To-Doリスト
    if has_manager_access:
        st.markdown("### 🚨 本日のマネジメント・ミッション（管理者専用）")
        st.caption("システムがデータから自動判定した、今日あなたがアクションを起こすべき生徒リストです。")
        
        col_todo1, col_todo2 = st.columns(2)
        with col_todo1:
            st.success(f"🗣️ **褒める・励ます ({len(todo_praise) + len(todo_encourage)}件)**")
            for msg in todo_praise: st.markdown(f"🟢 {msg}")
            for msg in todo_encourage: st.markdown(f"🟡 {msg}")
            if not todo_praise and not todo_encourage: st.write("（現在対象者はいません）")

        with col_todo2:
            st.error(f"📞 **注意・保護者連絡 ({len(todo_warn) + len(todo_contact)}件)**")
            for msg in todo_warn: st.markdown(f"🔴 {msg}")
            for msg in todo_contact: st.markdown(f"📞 {msg}")
            if not todo_warn and not todo_contact: st.write("（現在対象者はいません）")
        st.divider()

    # 🌟 柱2: 4象限マトリクス
    st.markdown(f"### 🗺️ クラス俯瞰マトリクス ({selected_grade} / {selected_subject})")
    if matrix_data:
        df_matrix = pd.DataFrame(matrix_data)
        
        # 散布図
        chart = alt.Chart(df_matrix).mark_circle(size=400, opacity=0.8, color="#1E90FF").encode(
            x=alt.X('能力 (X)', scale=alt.Scale(domain=[0.5, 5.5]), axis=alt.Axis(values=[1, 2, 3, 4, 5]), title="🧠 能力（内申・偏差値）"),
            y=alt.Y('やる気 (Y)', scale=alt.Scale(domain=[0.5, 5.5]), axis=alt.Axis(values=[1, 2, 3, 4, 5]), title="🔥 やる気（自習・宿題）"),
            tooltip=['生徒名', '能力 (X)', 'やる気 (Y)']
        )
        text = chart.mark_text(align='left', baseline='middle', dx=15, dy=0, fontSize=12, fontWeight='bold').encode(text='生徒名')
        
        # 4象限の十字線と透かし文字
        rule_x = alt.Chart(pd.DataFrame({'x': [3]})).mark_rule(color='gray', strokeDash=[5,5], strokeWidth=2).encode(x='x')
        rule_y = alt.Chart(pd.DataFrame({'y': [3]})).mark_rule(color='gray', strokeDash=[5,5], strokeWidth=2).encode(y='y')
        
        # 象限ラベル
        labels = pd.DataFrame([
            {"x": 4.5, "y": 5.0, "t": "🏃‍♂️ 自走・エース"},
            {"x": 1.5, "y": 5.0, "t": "💦 空回り・要指導"},
            {"x": 4.5, "y": 1.0, "t": "😴 サボり・ポテンシャル"},
            {"x": 1.5, "y": 1.0, "t": "⚠️ 離脱危機・要ケア"}
        ])
        label_chart = alt.Chart(labels).mark_text(fontSize=24, opacity=0.15, fontWeight='bold', color='gray').encode(
            x='x:Q', y='y:Q', text='t:N'
        )

        st.altair_chart(label_chart + rule_x + rule_y + chart + text, use_container_width=True) 

    # 🌟 柱3: トレンド分析（先月比） & 柱4: ランキング表
    if summary_data:
        df_summary = pd.DataFrame(summary_data)
        
        st.divider()
        c_left, c_right = st.columns([1, 1])
        
        with c_left:
            st.markdown(f"### 📈 トレンド分析（{selected_period}）")
            st.caption("先月との差分。数字がプラスなら成長、マイナスなら危険信号です。")
            
            # 見やすくフォーマット
            df_trend = df_summary[['生徒名', '今月自習(分)', '前月比自習(分)', '今月宿題(%)', '前月比宿題(%)']].copy()
            
            def format_diff(val):
                if val > 0: return f"🟢 +{val}"
                elif val < 0: return f"🔴 {val}"
                else: return "±0"
                
            df_trend['自習増減'] = df_trend['前月比自習(分)'].apply(format_diff)
            df_trend['宿題増減'] = df_trend['前月比宿題(%)'].apply(lambda x: format_diff(x) if isinstance(x, (int, float)) else "-")
            
            st.dataframe(df_trend[['生徒名', '今月自習(分)', '自習増減', '今月宿題(%)', '宿題増減']], hide_index=True, use_container_width=True)

        with c_right:
            st.markdown(f"### 🏆 総合ポイントランキング")
            st.caption("累計ポイントのランキングです。この表はダウンロードして掲示用に使えます！")
            
            df_ranking = df_summary[['生徒名', '今月の獲得pt', '小テスト平均']].sort_values(by="今月の獲得pt", ascending=False).reset_index(drop=True)
            df_ranking.index = df_ranking.index + 1
            df_ranking.reset_index(inplace=True)
            df_ranking.rename(columns={'index': '順位'}, inplace=True)
            
            st.dataframe(df_ranking, hide_index=True, use_container_width=True)
            
            # 🌟 Excelダウンロード機能
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                df_ranking.to_excel(writer, index=False, sheet_name='ポイントランキング')
            
            excel_data = excel_buffer.getvalue()
            st.download_button(
                label="📥 このランキングをExcelでダウンロード",
                data=excel_data,
                file_name=f"{selected_period}_{selected_grade}_{selected_subject}_ランキング.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )