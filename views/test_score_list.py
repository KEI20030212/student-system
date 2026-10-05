# views/test_scores_list.py

import streamlit as st
import pandas as pd
import io
import re
from utils.api_guard import robust_api_call

# データ取得用関数をインポート
from utils.g_sheets import load_test_scores, get_student_master

@st.cache_data(ttl=600, show_spinner=False)
def cached_get_student_master():
    return robust_api_call(get_student_master, fallback_value=pd.DataFrame())

@st.cache_data(ttl=600, show_spinner=False)
def safe_load_test_scores():
    return robust_api_call(load_test_scores, fallback_value=pd.DataFrame())

def render_test_scores_list_page():
    st.subheader("📝 定期テスト・模試・内申 成績一覧")
    st.caption("全生徒の成績データを一覧で確認・ダウンロードできます。")

    # 1. データの取得
    with st.spinner("成績データを読み込み中..."):
        df_tests = safe_load_test_scores()
        df_students = cached_get_student_master()

    if df_tests.empty or "APIエラー発生" in df_tests.columns:
        st.error("成績データが取得できませんでした。")
        return

    # 2. 基本的な列が存在するかチェック（古い形式のシートとの互換性）
    date_col = '実施日' if '実施日' in df_tests.columns else '日付' if '日付' in df_tests.columns else '日時' if '日時' in df_tests.columns else None
    name_col = '生徒名' if '生徒名' in df_tests.columns else '名前' if '名前' in df_tests.columns else None
    
    # 💡 先生にご提示いただいた最新の列名に合わせる
    type_col = 'テスト種別' if 'テスト種別' in df_tests.columns else None
    test_name_col = 'テスト名' if 'テスト名' in df_tests.columns else None # もし「テスト名」列がなくても動くように配慮

    if not date_col or not name_col or not type_col:
        st.error("成績シートに必要な列（日時・生徒名・テスト種別）が見つかりません。")
        st.write("現在の列名:", list(df_tests.columns))
        return

    # 3. 生徒マスターと結合して「学年」と「校舎」情報を付与（任意）
    if not df_students.empty and '生徒名' in df_students.columns and '学年' in df_students.columns and '生徒ID' in df_students.columns:
        # 生徒名で結合
        df_tests = pd.merge(df_tests, df_students[['生徒名', '学年', '生徒ID']], left_on=name_col, right_on='生徒名', how='left')
        
        # 生徒IDから校舎を判定
        def assign_branch(s_id):
            s_id = str(s_id).lower()
            if s_id.startswith('t'): return "田端新町校"
            elif s_id.startswith('h'): return "東十条駅前校"
            elif s_id == "trial": return "体験授業"
            else: return "その他"
            
        df_tests['所属校舎'] = df_tests['生徒ID'].apply(assign_branch)
    else:
        df_tests['学年'] = "不明"
        df_tests['所属校舎'] = "すべて"

    # ==========================================
    # 🎛️ 絞り込みフィルターUI
    # ==========================================
    with st.container(border=True):
        st.write("🔍 **絞り込み条件**")
        c1, c2, c3, c4 = st.columns(4)
        
        # 校舎フィルター
        branch_options = ["すべて"] + list(df_tests['所属校舎'].dropna().unique())
        selected_branch = c1.selectbox("🏫 校舎", branch_options)
        
        # 学年フィルター
        grade_options = ["すべて"] + list(df_tests['学年'].dropna().unique())
        selected_grade = c2.selectbox("🎯 学年", grade_options)
        
        # テスト種別フィルター
        type_options = ["すべて"] + list(df_tests[type_col].dropna().unique())
        selected_type = c3.selectbox("📝 テスト種別", type_options)
        
        # 実施時期（年）フィルター
        df_tests[date_col] = pd.to_datetime(df_tests[date_col], errors='coerce')
        year_options = ["すべて"] + sorted([str(int(y)) for y in df_tests[date_col].dt.year.dropna().unique()], reverse=True)
        selected_year = c4.selectbox("📅 実施年", year_options)

    # フィルター適用
    df_filtered = df_tests.copy()
    if selected_branch != "すべて": df_filtered = df_filtered[df_filtered['所属校舎'] == selected_branch]
    if selected_grade != "すべて": df_filtered = df_filtered[df_filtered['学年'] == selected_grade]
    if selected_type != "すべて": df_filtered = df_filtered[df_filtered[type_col] == selected_type]
    if selected_year != "すべて": df_filtered = df_filtered[df_filtered[date_col].dt.year == int(selected_year)]

    if df_filtered.empty:
        st.warning("指定された条件のデータはありません。")
        return

    # 日付降順に並び替え
    df_filtered = df_filtered.sort_values(by=date_col, ascending=False)
    
    # 日付を見やすくフォーマット
    df_filtered[date_col] = df_filtered[date_col].dt.strftime('%Y/%m/%d')

    # ==========================================
    # 📊 表示する列の整理とレイアウト
    # ==========================================
    st.write(f"📊 **検索結果: {len(df_filtered)} 件**")

    # 💡 先生にご提示いただいた列の中から、種別に応じて見やすい列だけをピックアップする
    base_cols = [date_col, '所属校舎', '学年', name_col, type_col]
    
    # もし「テスト名」列があれば追加
    if test_name_col:
        base_cols.append(test_name_col)

    # 種別によって表示する列グループを変える（ご提示いただいた列名に完全準拠）
    if selected_type == "すべて":
        # 全部入り（横に長くなるので、主要なものだけにするか、全表示するか）
        score_cols = ['英語', '数学', '国語', '理科', '社会', '総合', '9科総合', '偏差値_3科', '偏差値_5科']
    elif "模試" in selected_type or "実力" in selected_type:
        # 模試なら偏差値をメインに
        score_cols = ['英語', '数学', '国語', '理科', '社会', '総合', '偏差値_3科', '偏差値_5科', '英語 偏差値', '数学 偏差値', '国語 偏差値', '理科 偏差値', '社会 偏差値']
    elif "通知表" in selected_type or "内申" in selected_type:
        # 内申なら内申と態度をメインに
        score_cols = ['英語 内申', '数学 内申', '国語 内申', '理科 内申', '社会 内申', '保体 内申', '技家 内申', '美術 内申', '音楽 内申']
    else:
        # 定期テスト系（点数メイン）
        score_cols = ['英語', '数学', '国語', '理科', '社会', '総合', '保体', '技術', '家庭', '美術', '音楽', '9科総合']

    # 実際にデータフレームに存在する列だけを抽出
    available_score_cols = [col for col in score_cols if col in df_filtered.columns]
    
    display_cols = base_cols + available_score_cols
    
    # NaNをハイフンにして見やすくする
    df_display = df_filtered[display_cols].fillna("-")

    # 表の描画
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    # ==========================================
    # 📥 Excelダウンロード機能
    # ==========================================
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
        df_display.to_excel(writer, index=False, sheet_name='成績一覧')
    
    # ファイル名を安全に生成
    safe_branch = re.sub(r'[\\/:*?"<>|]', '_', selected_branch)
    safe_type = re.sub(r'[\\/:*?"<>|]', '_', selected_type)
    file_name = f"{safe_branch}_{safe_type}_成績一覧.xlsx"

    st.download_button(
        label="📥 この一覧をExcelでダウンロード",
        data=excel_buffer.getvalue(),
        file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )