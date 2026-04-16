import streamlit as st
import pandas as pd
import altair as alt
import time

# ==========================================
# 🛡️ APIエラー対策：堅牢なデータ読み込み関数群
# ==========================================
@st.cache_data(ttl=600, show_spinner=False)
def cached_calculate_attendance_rate(student_name):
    from utils.g_sheets import load_raw_data # 生徒個別シートを読み込む既存の関数（※）
    import time
    
    max_retries = 5
    df_attendance = pd.DataFrame()
    
    # --- 🛡️ APIエラー対策: 指数バックオフ付き読み込み ---
    for attempt in range(max_retries):
        try:
            # 生徒名と同じ名前のシートを読み込む想定
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
    # 1. 判定用のキーワード
    attend_keywords = ['出席（通常）', '出席（振替授業を消化）']
    absent_keywords = ['欠席（後日振替あり）', '欠席（振替なし）']
    
    # 2. それぞれの数をカウント
    # ※ 列名が「出欠」であることを前提にしています
    records = df_attendance['出欠'].dropna().astype(str)
    attend_count = records.isin(attend_keywords).sum()
    absent_count = records.isin(absent_keywords).sum()
    
    total_lessons = attend_count + absent_count
    
    if total_lessons == 0:
        return "0% (履歴なし)"
    
    rate = (attend_count / total_lessons) * 100
    return f"{int(rate)}%"

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

    # --- 1. 宿題履行状況 ＆ 努力の量 ---
    st.subheader("🔥 学習への取り組み姿勢")
    col1, col2, col3, col4 = st.columns(4)
    with st.spinner("出席率を計算中..."):
        # 🌟 ここで先ほど作った計算関数を呼び出す
        attendance_rate = cached_calculate_attendance_rate(selected_student)
    
    hw_rate_str = str(info.get('宿題履行率', '0')).replace('%', '')
    try:
        hw_rate = float(hw_rate_str)
    except ValueError:
        hw_rate = 0.0

    attendance_rate = info.get('出席率', 'データなし')

    col1.metric("🏠 宿題履行率", f"{hw_rate}%")
    col2.metric("📅 出席率", attendance_rate) # 🌟 自動計算された値が表示される
    
    total_quiz_attempts = len(df_quiz) if not df_quiz.empty else 0
    col3.metric("📝 小テスト総回数", f"{total_quiz_attempts} 回")
    col4.metric("🎯 志望校・目標", info.get('志望校・目的', '未設定'))
    if hw_rate >= 90: st.success("素晴らしい取り組みです！この学習習慣が成績向上の最大の武器になります。")
    elif hw_rate >= 70: st.info("概ね良好に学習できています。間違えた問題の解き直しを徹底するとさらに伸びます。")
    else: st.warning("まずは宿題をやり切る習慣づけが必要です。ご家庭での学習時間の固定化をご協力お願いします。")

    st.divider()

    # ==========================================
    # 2. 学校成績の推移（5科目マルチライン）
    # ==========================================
    st.subheader("📈 成績の推移 (5科目)")
    if not df_student_tests.empty:
        # 💡 列名の違い（実施日か、日付か）を自動で判別して吸収する安全設計
        date_col = '実施日' if '実施日' in df_student_tests.columns else '日付' if '日付' in df_student_tests.columns else None
        type_col = 'テスト種別' if 'テスト種別' in df_student_tests.columns else 'テスト名' if 'テスト名' in df_student_tests.columns else None

        if not date_col:
            # 万が一どちらの列名もない場合は、クラッシュさせずに現在の列名を画面に表示して教える
            st.error(f"⚠️ 成績データの中に「実施日」または「日付」という名前の列が見つかりません。スプレッドシートを確認してください。\n（現在の列名: {', '.join(df_student_tests.columns)}）")
        else:
            # テスト種別の絞り込み（列が存在する場合のみ）
            if type_col:
                df_plot = df_student_tests[df_student_tests[type_col].astype(str).str.contains("テスト|模試", na=False)].copy()
            else:
                df_plot = df_student_tests.copy()

            if not df_plot.empty:
                # 日付順に並び替え
                df_plot[date_col] = pd.to_datetime(df_plot[date_col], errors='coerce')
                df_plot = df_plot.sort_values(date_col)
                
                subjects = ["英語", "数学", "国語", "理科", "社会"]
                # シートに実際に存在する科目列だけを抽出（国語と算数しかない場合などのエラー防止）
                available_subjects = [s for s in subjects if s in df_plot.columns]
                
                # グラフ描画用にデータを変形
                id_vars_list = [date_col]
                if type_col: id_vars_list.append(type_col)

                df_melted = df_plot.melt(id_vars=id_vars_list, value_vars=available_subjects, var_name='科目', value_name='点数')
                df_melted['点数'] = pd.to_numeric(df_melted['点数'], errors='coerce')
                df_melted = df_melted.dropna(subset=['点数'])

                # ツールチップ（マウスオーバー時の表示）の設定
                tooltip_list = [date_col, '科目', '点数']
                if type_col: tooltip_list.insert(1, type_col)

                # グラフの描画
                chart = alt.Chart(df_melted).mark_line(point=True).encode(
                    x=alt.X(f'{date_col}:T', title='実施日'),
                    y=alt.Y('点数:Q', scale=alt.Scale(domain=[0, 100]), title='点数'),
                    color=alt.Color('科目:N', scale=alt.Scale(domain=available_subjects, range=['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00'])),
                    tooltip=tooltip_list
                ).properties(height=350)
                
                st.altair_chart(chart, use_container_width=True)
            else:
                st.info("グラフ化できる定期テスト・模試のデータがまだありません。")
    else:
        st.info("成績データが登録されていません。")

    st.divider()
    # --- 3. 小テスト進捗 ---
    st.subheader("📊 小テスト（基礎学力）の定着状況")
    if master_dict and not df_quiz.empty:
        df_quiz['点数'] = pd.to_numeric(df_quiz['点数'], errors='coerce')
        summary_data = []

        attempted_texts = df_quiz['テキスト'].dropna().unique()

        for text_name in attempted_texts:
            if text_name not in master_dict:
                continue # マスターにない場合はスキップ
                
            chaps = master_dict[text_name]
            total_chaps = len(chaps)
            df_text = df_quiz[(df_quiz['テキスト'] == text_name) & (df_quiz['点数'] >= 80)]
            done_chaps = df_text['単元'].nunique() if '単元' in df_text.columns else 0
            
            progress = int((done_chaps / total_chaps) * 100) if total_chaps > 0 else 0
            summary_data.append({
                "テキスト名": text_name,
                "進捗率(%)": progress,
                "合格章数": f"{done_chaps} / {total_chaps} 章"
            }
        if summary_data:
            df_summary = pd.DataFrame(summary_data)
            bar_chart = alt.Chart(df_summary).mark_bar().encode(
                x=alt.X('進捗率(%):Q', scale=alt.Scale(domain=[0, 100])),
                y=alt.Y('テキスト名:N', sort='-x'),
                color=alt.Color('進捗率(%):Q', scale=alt.Scale(scheme='blues')),
                tooltip=['テキスト名', '進捗率(%)', '合格章数']
            ).properties(height=200)
            st.altair_chart(bar_chart, use_container_width=True)
            
            # 🌟 印刷対策：インデックスをテキスト名にして、st.tableで静的に表示
            st.table(df_summary.set_index("テキスト名"))
        else:
            st.info("集計できる小テストデータがありません。")
    else:
        st.info("小テストのデータがまだありません。")

    # --- 4. 弱点分析 ---
    st.subheader("💡 優先して復習すべき単元（自動ピックアップ）")
    if not df_quiz.empty:
        df_weak = df_quiz[df_quiz['点数'] < 60].sort_values(by='日時', ascending=False).head(5)
        if not df_weak.empty:
            st.write("以下の単元は、直近のテストで点数が伸び悩んだため、次回の授業や講習で優先的に対策を行います。")
            display_weak = df_weak[['日時', 'テキスト', '単元', '点数', 'ミス番号']]
            
            # 🌟 印刷対策：インデックスを「日時」にして、st.tableで表示
            st.table(display_weak.set_index("日時"))
        else:
            st.success("現在、極端に点数が低い（苦手な）単元は見当たりません！順調です。")