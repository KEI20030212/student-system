import streamlit as st
import pandas as pd
import altair as alt
import time

# ==========================================
# 🛡️ APIエラー対策：堅牢なデータ読み込み関数群
# ==========================================
@st.cache_data(ttl=600, show_spinner=False)
def safe_load_test_scores():
    from utils.g_sheets import load_test_scores
    max_retries = 5
    for attempt in range(max_retries):
        try:
            return load_test_scores()
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                st.error("通信が混み合っています。少し時間をおいて画面を更新してください。")
                return pd.DataFrame()

@st.cache_data(ttl=600, show_spinner=False)
def cached_get_textbook_master():
    from utils.g_sheets import get_textbook_master
    return get_textbook_master()

@st.cache_data(ttl=600, show_spinner=False)
def cached_load_quiz_data(student_name):
    from utils.g_sheets import load_quiz_data_from_dedicated_sheet
    max_retries = 5
    for attempt in range(max_retries):
        try:
            return load_quiz_data_from_dedicated_sheet(student_name)
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return pd.DataFrame()

@st.cache_data(ttl=600, show_spinner=False)
def cached_calculate_attendance_rate(student_name):
    from utils.g_sheets import load_raw_data
    import time
    import pandas as pd
    
    max_retries = 5
    df_attendance = pd.DataFrame()
    
    # --- 🛡️ APIエラー対策: 指数バックオフ付き読み込み ---
    for attempt in range(max_retries):
        try:
            df_attendance = load_raw_data(student_name)
            break
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return "取得エラー"

    if df_attendance.empty or '出欠' not in df_attendance.columns:
        return "データなし"

    # --- 📊 出席率の計算ロジック ---
    attend_keywords = ['出席（通常）', '出席（振替授業を消化）']
    absent_keywords = ['欠席（後日振替あり）', '欠席（振替なし）']
    
    records = df_attendance['出欠'].dropna().astype(str)
    attend_count = records.isin(attend_keywords).sum()
    absent_count = records.isin(absent_keywords).sum()
    
    total_lessons = attend_count + absent_count
    
    if total_lessons == 0:
        return "0% (履歴なし)"
    
    rate = (attend_count / total_lessons) * 100
    return f"{int(rate)}%"

# ==========================================
# 🎯 面談レポート画面のメイン関数
# ==========================================
def render_conference_report(selected_student, info):
    st.header(f"🎓 {selected_student} さん 面談レポート")
    st.caption("※この画面はデータ読み込み専用です。通信エラーを防ぐため一時保存されたデータを表示しています。")

    with st.spinner("学習データを集計中..."):
        master_dict = cached_get_textbook_master()
        df_quiz = cached_load_quiz_data(selected_student)
        df_test_all = safe_load_test_scores()

    df_student_tests = pd.DataFrame()
    if not df_test_all.empty:
        df_student_tests = df_test_all[df_test_all['生徒名'] == selected_student]

    st.divider()

    # ==========================================
    # 1. 宿題・出席・努力の量
    # ==========================================
    st.subheader("🔥 学習への取り組み姿勢")
    col1, col2, col3, col4 = st.columns(4)
    
    with st.spinner("出席率を計算中..."):
        attendance_rate = cached_calculate_attendance_rate(selected_student)
    
    hw_rate_str = str(info.get('宿題履行率', '0')).replace('%', '')
    try:
        hw_rate = float(hw_rate_str)
    except ValueError:
        hw_rate = 0.0

    col1.metric("🏠 宿題履行率", f"{hw_rate}%")
    col2.metric("📅 出席率", attendance_rate)
    
    total_quiz_attempts = len(df_quiz) if not df_quiz.empty else 0
    col3.metric("📝 小テスト総回数", f"{total_quiz_attempts} 回")
    col4.metric("🎯 志望校・目標", info.get('志望校・目的', '未設定'))

    if hw_rate >= 90: st.success("素晴らしい取り組みです！この学習習慣が成績向上の最大の武器になります。")
    elif hw_rate >= 70: st.info("概ね良好に学習できています。間違えた問題の解き直しを徹底するとさらに伸びます。")
    else: st.warning("まずは宿題をやり切る習慣づけが必要です。ご家庭での学習時間の固定化をご協力お願いします。")

    st.divider()

    # ==========================================
    # 2. 学校成績の推移（切り替え機能付き）
    # ==========================================
    st.subheader("📈 成績の推移")
    if not df_student_tests.empty:
        # 日付・種別列の判定
        date_col = '実施日' if '実施日' in df_student_tests.columns else '日付' if '日付' in df_student_tests.columns else '日時' if '日時' in df_student_tests.columns else None
        type_col = 'テスト種別' if 'テスト種別' in df_student_tests.columns else 'テスト名' if 'テスト名' in df_student_tests.columns else None

        if not date_col:
            st.error("⚠️ 日付列が見つかりません。")
        else:
            # 🌟 グラフの表示切り替えスイッチ
            display_type = st.radio(
                "表示するデータを選択してください：",
                ["定期テスト", "模試", "内申"],
                horizontal=True
            )

            # データの絞り込みと設定
            plot_df = df_student_tests.copy()
            plot_df[date_col] = pd.to_datetime(plot_df[date_col], errors='coerce')
            plot_df = plot_df.sort_values(date_col)

            if display_type == "定期テスト":
                # 「テスト」という言葉が含まれるものを抽出（「模試」は除外）
                if type_col:
                    plot_df = plot_df[plot_df[type_col].astype(str).str.contains("テスト|中間|期末", na=False)]
                    plot_df = plot_df[~plot_df[type_col].astype(str).str.contains("模試", na=False)]
                subjects = ["英語", "数学", "国語", "理科", "社会"]
                y_label = "点数"
                y_domain = [0, 100]

            elif display_type == "模試":
                # 「模試」という言葉が含まれるものを抽出
                if type_col:
                    plot_df = plot_df[plot_df[type_col].astype(str).str.contains("模試", na=False)]
                subjects = ["英語", "数学", "国語", "理科", "社会"]
                y_label = "偏差値"
                y_domain = [30, 80] # 模試なので偏差値用の範囲に調整

            else: # 内申
                # 内申点がある行（どれか一つでも入っている）を抽出
                naishin_cols = ["英語 内申", "数学 内申", "国語 内申", "理科 内申", "社会 内申", "保体 内申", "技家 内申", "美術 内申", "音楽 内申"]
                available_naishin = [c for c in naishin_cols if c in plot_df.columns]
                plot_df = plot_df.dropna(subset=available_naishin, how='all')
                subjects = available_naishin
                y_label = "評定"
                y_domain = [1, 5]

            # グラフ描画
            if not plot_df.empty:
                available_subjects = [s for s in subjects if s in plot_df.columns]
                
                id_vars_list = [date_col]
                if type_col: id_vars_list.append(type_col)

                df_melted = plot_df.melt(id_vars=id_vars_list, value_vars=available_subjects, var_name='項目', value_name='数値')
                df_melted['数値'] = pd.to_numeric(df_melted['数値'], errors='coerce')
                df_melted = df_melted.dropna(subset=['数値'])

                if not df_melted.empty:
                    chart = alt.Chart(df_melted).mark_line(point=True).encode(
                        x=alt.X(f'{date_col}:T', title='実施日'),
                        y=alt.Y('数値:Q', scale=alt.Scale(domain=y_domain), title=y_label),
                        color=alt.Color('項目:N', legend=alt.Legend(title="科目・項目")),
                        tooltip=[date_col, '項目', '数値']
                    ).properties(height=350).interactive()
                    
                    st.altair_chart(chart, use_container_width=True)
                else:
                    st.info(f"{display_type}の数値データが見つかりませんでした。")
            else:
                st.info(f"{display_type}のデータがまだ登録されていません。")
    else:
        st.info("成績データが登録されていません。")

    st.divider()

    # ==========================================
    # 3. 小テスト進捗の一覧（テキスト別サマリー）
    # ==========================================
    st.subheader("📊 小テスト（基礎学力）の定着状況")
    if master_dict and not df_quiz.empty:
        df_quiz['点数'] = pd.to_numeric(df_quiz['点数'], errors='coerce')
        summary_data = []
        
        attempted_texts = df_quiz['テキスト'].dropna().unique()
        
        for text_name in attempted_texts:
            if text_name not in master_dict:
                continue
                
            chaps = master_dict[text_name]
            total_chaps = len(chaps)
            df_text = df_quiz[(df_quiz['テキスト'] == text_name) & (df_quiz['点数'] >= 80)]
            done_chaps = df_text['単元'].nunique() if '単元' in df_text.columns else 0
            
            progress = int((done_chaps / total_chaps) * 100) if total_chaps > 0 else 0
            summary_data.append({
                "テキスト名": text_name,
                "進捗率(%)": progress,
                "合格章数": f"{done_chaps} / {total_chaps} 章"
            })
            
        if summary_data:
            df_summary = pd.DataFrame(summary_data)
            bar_chart = alt.Chart(df_summary).mark_bar().encode(
                x=alt.X('進捗率(%):Q', scale=alt.Scale(domain=[0, 100])),
                y=alt.Y('テキスト名:N', sort='-x'),
                color=alt.Color('進捗率(%):Q', scale=alt.Scale(scheme='blues')),
                tooltip=['テキスト名', '進捗率(%)', '合格章数']
            ).properties(height=200)
            st.altair_chart(bar_chart, use_container_width=True)
            
            st.table(df_summary.set_index("テキスト名"))
        else:
            st.info("集計できる小テストデータがありません。")
    else:
        st.info("小テストのデータがまだありません。")

    # ==========================================
    # 4. 弱点分析（おすすめデータ：今後の対策）
    # ==========================================
    st.subheader("💡 優先して復習すべき単元（自動ピックアップ）")
    if not df_quiz.empty:
        df_weak = df_quiz[df_quiz['点数'] < 60].sort_values(by='日時', ascending=False).head(5)
        if not df_weak.empty:
            st.write("以下の単元は、直近のテストで点数が伸び悩んだため、次回の授業や講習で優先的に対策を行います。")
            display_weak = df_weak[['日時', 'テキスト', '単元', '点数', 'ミス番号']]
            
            st.table(display_weak.set_index("日時"))
        else:
            st.success("現在、極端に点数が低い（苦手な）単元は見当たりません！順調です。")