import streamlit as st
import pandas as pd
import datetime

# ==========================================
# 🌟 utils/g_sheets.py から専用関数を呼び出し
# ==========================================
from utils.g_sheets import (
    get_all_student_names, 
    get_quiz_master_dict,                # 🌟 今回はこれだけで全てまかないます！
    save_quiz_to_dedicated_sheet,        
    load_quiz_data_from_dedicated_sheet  
)

from utils.api_guard import robust_api_call

# ==========================================
# 🌟 APIエラー対策：キャッシュ機能 + 強化版APIコール
# ==========================================
@st.cache_data(ttl=600)  
def cached_get_student_names():
    return robust_api_call(get_all_student_names, fallback_value=[])

@st.cache_data(ttl=600)  
def cached_get_quiz_details():
    # 「設定_小テスト一覧」から取得 (例: {"確認テスト_第1回": {"full_marks": 50, "サイズ": "A4"}})
    return robust_api_call(get_quiz_master_dict, fallback_value={})

@st.cache_data(ttl=60)   
def cached_load_quiz_data(student_name):
    return robust_api_call(load_quiz_data_from_dedicated_sheet, student_name, fallback_value=pd.DataFrame())

# ==========================================

def render_quiz_list_page():
    st.header("📝 小テスト進捗＆習熟度マップ")
    st.write("自習などで実施した小テストの結果を入力・確認できるページです🎨")

    # 1. 生徒の選択
    student_names = cached_get_student_names()
    
    if not student_names:
        st.error("生徒データの取得に失敗しました。時間をおいて再読み込みしてください。")
        st.stop()

    selected_student = st.selectbox("👤 生徒を選択", ["-- 選択 --"] + student_names)
    
    if selected_student == "-- 選択 --":
        st.stop()

    # 2. 小テスト設定の取得と階層化
    quiz_details = cached_get_quiz_details()
    
    # 🌟 A列(小テスト名) と B列(単元・回) の階層辞書を自動生成
    quiz_hierarchy = {}
    for key in quiz_details.keys():
        if "_" in key:
            q_name, q_unit = key.split("_", 1)
            if q_name not in quiz_hierarchy:
                quiz_hierarchy[q_name] = []
            quiz_hierarchy[q_name].append(q_unit)

    # ==========================================
    # 🌟 小テスト結果の入力フォーム
    # ==========================================
    with st.expander("📝 小テスト結果を登録する"):
        st.write(f"**{selected_student}** さんの結果を入力します。")
        
        with st.form("quiz_input_form"):
            col1, col2 = st.columns(2)
            
            # 小テスト名のリスト（A列の重複なしリスト）
            quiz_names = list(quiz_hierarchy.keys())
            
            if not quiz_names:
                st.warning("「設定_小テスト一覧」のデータが取得できません。")
                st.form_submit_button("記録不可", disabled=True)
            else:
                # 🌟 小テスト名 (A列)
                target_quiz = col1.selectbox("📝 小テスト名", quiz_names)
                
                # 🌟 単元・回 (B列)
                valid_units = quiz_hierarchy.get(target_quiz, [])
                target_unit = col2.selectbox("📖 単元・回", valid_units)
                
                # 満点の取得
                quiz_key = f"{target_quiz}_{target_unit}"
                max_score = int(quiz_details.get(quiz_key, {}).get("full_marks", 100))
                
                col3, col4 = st.columns(2)
                score = col3.number_input(f"💯 点数 (満点: {max_score})", min_value=0, max_value=max_score, value=max_score, step=1)
                test_date = col4.date_input("📅 実施日", datetime.date.today())
                
                submit_quiz = st.form_submit_button("この内容で記録する ✨", type="primary")
                
                if submit_quiz:
                    with st.spinner("記録中..."):
                        success = robust_api_call(
                            save_quiz_to_dedicated_sheet,
                            test_date.strftime("%Y/%m/%d"), 
                            selected_student, 
                            target_quiz,  # 保存先シートでは「テキスト/テスト名」列に保存されます
                            target_unit,  # 保存先シートでは「単元」列に保存されます
                            score,
                            "", 
                            "自習",
                            fallback_value=False
                        )
                        
                        if success:
                            st.success(f"【{target_quiz} {target_unit}】を {score}点で記録しました！")
                            cached_load_quiz_data.clear()
                            st.rerun()
                        else:
                            st.error("記録に失敗しました。")

    st.divider()

    # ==========================================
    # 🌟 習熟度マップの表示ロジック
    # ==========================================
    with st.spinner("習熟度データを集計中..."):
        df_quiz = cached_load_quiz_data(selected_student)
        
        if "APIエラー発生" in df_quiz.columns:
            st.error("データの取得中にエラーが発生しました。")
            st.stop()
        
        # 🌟 マスタデータ（下部の表の枠組み）も「設定_小テスト一覧」から直接作成
        flat_data = []
        for q_name, units in quiz_hierarchy.items():
            for unit in units:
                flat_data.append({'小テスト名': q_name, '単元': unit})
                
        df_master = pd.DataFrame(flat_data, columns=['小テスト名', '単元'])

        if df_master.empty:
            st.warning("⚠️ 小テスト設定データがありません。")
            st.stop()

        if df_quiz.empty:
            st.warning("小テストの記録がまだありません。")
            st.stop()

        df_quiz['点数'] = pd.to_numeric(df_quiz['点数'], errors='coerce')
        df_quiz = df_quiz.dropna(subset=['点数']).copy()
        
        if not df_quiz.empty:
            df_quiz['日時'] = pd.to_datetime(df_quiz['日時'], format='mixed', errors='coerce')
            last_date = df_quiz['日時'].max().strftime("%Y年%m月%d日")
            st.success(f"📅 前回実施日: **{last_date}**")

        # 既存シートの「テキスト」列を「小テスト名」として扱う
        best_scores = df_quiz.groupby(['テキスト', '単元'])['点数'].max().reset_index()
        best_scores = best_scores.rename(columns={'テキスト': '小テスト名', '点数': '最高点数'})

        df_master['単元_clean'] = df_master['単元'].astype(str).str.replace('第', '').str.replace('章', '').str.strip()
        best_scores['単元_clean'] = best_scores['単元'].astype(str).str.replace('第', '').str.replace('章', '').str.strip()

        df_merged = pd.merge(df_master, best_scores, left_on=['小テスト名', '単元_clean'], right_on=['小テスト名', '単元_clean'], how='left', suffixes=('', '_score'))

        # タブ表示（小テスト名ごと）
        quiz_list = df_master['小テスト名'].unique().tolist()
        tabs = st.tabs(quiz_list)

        for i, q_name in enumerate(quiz_list):
            with tabs[i]: 
                df_display = df_merged[df_merged['小テスト名'] == q_name]
                
                total = len(df_display)
                done = df_display['最高点数'].notna().sum()
                rate = int((done / total) * 100) if total > 0 else 0
                
                st.subheader(f"📊 達成率: {rate}% ({done}/{total} 単元クリア)")
                st.progress(rate / 100.0)

                pivot_df = df_display.pivot_table(
                    index='小テスト名', 
                    columns='単元', 
                    values='最高点数', 
                    aggfunc='max'
                )
                
                if pivot_df.empty:
                    st.info("記録がありません。")
                    continue

                import re
                def sort_key(c):
                    nums = re.findall(r'\d+', str(c))
                    return int(nums[0]) if nums else 999
                pivot_df = pivot_df[sorted(pivot_df.columns.tolist(), key=sort_key)]

                def add_icon(val, unit_name=None):
                    if pd.isna(val): return ""
                    q_key = f"{q_name}_{unit_name}"
                    full_m = float(quiz_details.get(q_key, {}).get("full_marks", 100))
                    ratio = val / full_m if full_m > 0 else 0
                    if ratio >= 1.0: return f"👑 {int(val)}"
                    elif ratio >= 0.8: return f"🟢 {int(val)}"
                    elif ratio >= 0.6: return f"🟡 {int(val)}"
                    else: return f"🔴 {int(val)}"

                styled_display = pivot_df.copy()
                for col in styled_display.columns:
                    styled_display[col] = styled_display[col].apply(lambda x: add_icon(x, col))

                def color_bg(v):
                    if "👑" in str(v): return 'background-color: #fffacd; color: #000; font-weight: bold;'
                    if "🟢" in str(v): return 'background-color: #c6efce; color: #006100;'
                    if "🟡" in str(v): return 'background-color: #ffeb9c; color: #9c6500;'
                    if "🔴" in str(v): return 'background-color: #ffc7ce; color: #9c0006;'
                    return ''

                try:
                    st.dataframe(styled_display.style.applymap(color_bg), use_container_width=True)
                except AttributeError:
                    st.dataframe(styled_display.style.map(color_bg), use_container_width=True)