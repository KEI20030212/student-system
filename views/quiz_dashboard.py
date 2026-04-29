import streamlit as st
import pandas as pd
import datetime

# ==========================================
# 🌟 utils/g_sheets.py から専用関数を呼び出し
# ==========================================
from utils.g_sheets import (
    get_all_student_names, 
    get_textbook_master,
    get_quiz_master_dict,                # 🌟 ご提示いただいた関数をインポート
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
def cached_get_textbook_master():
    return robust_api_call(get_textbook_master, fallback_value={})

@st.cache_data(ttl=600)  # 🌟 get_quiz_master_dict 用のキャッシュを追加
def cached_get_quiz_master_dict():
    return robust_api_call(get_quiz_master_dict, fallback_value={})

@st.cache_data(ttl=60)   
def cached_load_quiz_data(student_name):
    return robust_api_call(load_quiz_data_from_dedicated_sheet, student_name, fallback_value=pd.DataFrame())

# ==========================================

def render_quiz_list_page():
    st.header("📝 小テスト進捗＆習熟度マップ")
    st.write("縦軸がテキスト、横軸が小テストです。授業以外で実施したテスト結果もここから入力できます🎨")

    # 1. 生徒の選択
    student_names = cached_get_student_names()
    
    if not student_names:
        st.error("生徒データの取得に失敗しました。時間をおいて再読み込みしてください。")
        st.stop()

    selected_student = st.selectbox("👤 生徒を選択", ["-- 選択 --"] + student_names)
    
    if selected_student == "-- 選択 --":
        st.stop()

    # マスタデータとテスト詳細データの読み込み
    master_dict = cached_get_textbook_master()
    quiz_master = cached_get_quiz_master_dict()

    # ==========================================
    # 🌟 小テスト結果の入力フォーム
    # ==========================================
    with st.expander("📝 小テスト結果を登録する（授業以外・自習など）"):
        st.write(f"**{selected_student}** さんのテスト結果を入力します。")
        
        with st.form("quiz_input_form"):
            col1, col2 = st.columns(2)
            
            # テキスト選択
            textbooks = list(master_dict.keys())
            if not textbooks:
                st.warning("マスタデータが取得できないため、入力できません。")
                st.form_submit_button("記録不可", disabled=True)
            else:
                target_text = col1.selectbox("📚 テキスト", textbooks)
                
                # 🌟 get_quiz_master_dict から、選択したテキストに紐づくテスト名を抽出
                prefix = f"{target_text}_"
                # "テキスト名_テスト名" のキーからテスト名の部分だけを切り出す
                valid_quizzes = [k.replace(prefix, "", 1) for k in quiz_master.keys() if k.startswith(prefix)]
                
                if not valid_quizzes:
                    target_chap = col2.text_input("📝 小テスト名 (マスタ未登録のため手入力)")
                    max_score = 100 # 手入力の場合は一旦100点満点とする
                else:
                    target_chap = col2.selectbox("📝 小テスト名", valid_quizzes)
                    # 🌟 選択したテストの満点データを取得（なければ100とする）
                    quiz_key = f"{target_text}_{target_chap}"
                    max_score = int(quiz_master.get(quiz_key, {}).get("full_marks", 100))
                
                col3, col4 = st.columns(2)
                
                # 🌟 点数の直接入力 (max_valueとvalueを満点に合わせて自動可変に！)
                score = col3.number_input(f"💯 点数 (満点: {max_score})", min_value=0, max_value=max_score, value=max_score, step=1)
                
                # 実施日
                test_date = col4.date_input("📅 実施日", datetime.date.today())
                
                submit_quiz = st.form_submit_button("この内容で記録する ✨", type="primary")
                
                if submit_quiz:
                    with st.spinner("記録中..."):
                        success = robust_api_call(
                            save_quiz_to_dedicated_sheet,
                            test_date.strftime("%Y/%m/%d"), 
                            selected_student, 
                            target_text, 
                            target_chap, 
                            score,
                            "", 
                            "自習",
                            fallback_value=False
                        )
                        
                        if success:
                            st.success(f"【{target_text} - {target_chap}】を {score}点で記録しました！")
                            cached_load_quiz_data.clear()
                            st.rerun()
                        else:
                            st.error("記録に失敗しました。通信状況を確認してください。")

    st.divider()

    # ==========================================
    # 🌟 以降、習熟度マップの表示ロジック
    # ==========================================
    with st.spinner("習熟度データを集計中..."):
        df_quiz = cached_load_quiz_data(selected_student)
        
        if "APIエラー発生" in df_quiz.columns:
            st.error("小テスト記録の取得中にエラーが発生したため、処理を中断しました。時間をおいて再試行してください。")
            st.stop()
        
        flat_data = []
        for text_name, chaps in master_dict.items():
            for chap in chaps:
                flat_data.append({'テキスト': text_name, '章': chap})
                
        df_master = pd.DataFrame(flat_data, columns=['テキスト', '章'])

        if df_master.empty:
            st.warning("⚠️ マスタデータが読み込めませんでした。")
            st.stop()

        if df_quiz.empty:
            st.warning("小テストの記録がまだありません。")
            st.stop()

        df_quiz['点数'] = pd.to_numeric(df_quiz['点数'], errors='coerce')
        df_quiz = df_quiz.dropna(subset=['点数']).copy()

        if not df_quiz.empty:
            df_quiz['日時'] = pd.to_datetime(df_quiz['日時'], format='mixed', errors='coerce')
            last_date = df_quiz['日時'].max().strftime("%Y年%m月%d日")
            st.success(f"📅 前回小テスト実施日: **{last_date}**")
        else:
            st.info("📅 まだ小テストの記録がありません。")

        best_scores = df_quiz.groupby(['テキスト', '単元'])['点数'].max().reset_index()
        best_scores = best_scores.rename(columns={'単元': '章', '点数': '最高点数'})

        df_master['章_clean'] = df_master['章'].astype(str).str.replace('第', '').str.replace('章', '').str.strip()
        best_scores['章_clean'] = best_scores['章'].astype(str).str.replace('第', '').str.replace('章', '').str.strip()

        df_merged = pd.merge(df_master, best_scores, left_on=['テキスト', '章_clean'], right_on=['テキスト', '章_clean'], how='left', suffixes=('', '_score'))

        textbook_names = df_master['テキスト'].unique().tolist()
        
        if not textbook_names:
            st.warning("テキスト一覧が見つかりません。")
            st.stop()

        tabs = st.tabs(textbook_names)

        for i, text_name in enumerate(textbook_names):
            with tabs[i]: 
                df_text = df_merged[df_merged['テキスト'] == text_name]
                
                total_chaps = len(df_text)
                done_chaps = df_text['最高点数'].notna().sum()
                
                if total_chaps > 0:
                    progress_rate = int((done_chaps / total_chaps) * 100)
                else:
                    progress_rate = 0
                
                st.subheader(f"📊 達成率: {progress_rate}% ({done_chaps}/{total_chaps}テストクリア)")
                st.progress(progress_rate / 100.0)
                st.write("") 

                pivot_df = df_text.pivot_table(
                    index='テキスト', 
                    columns='章', 
                    values='最高点数', 
                    aggfunc='max'
                )
                
                if pivot_df.empty:
                    st.info("このテキストのテスト記録はまだありません。")
                    continue
                
                import re
                def sort_chapter_key(col_name):
                    nums = re.findall(r'\d+', str(col_name))
                    if nums:
                        return int(nums[0])
                    return 9999

                sorted_cols = sorted(pivot_df.columns.tolist(), key=sort_chapter_key)
                pivot_df = pivot_df[sorted_cols]

                # --- ✨ アイコン化＆カラーリング ---
                def add_icon_to_score(val, chap_name=None):
                    if pd.isna(val) or val == "":
                        return ""
                    try:
                        v = float(val)
                        # 各テストの満点を取得して、達成度を判定！
                        q_key = f"{text_name}_{chap_name}" if chap_name else ""
                        full_m = float(quiz_master.get(q_key, {}).get("full_marks", 100))
                        
                        # 満点に対する割合で色分け (100%, 80%以上, 60%以上, それ未満)
                        ratio = v / full_m if full_m > 0 else 0
                        
                        if ratio >= 1.0: return f"👑 {int(v)}"
                        elif ratio >= 0.8: return f"🟢 {int(v)}"
                        elif ratio >= 0.6: return f"🟡 {int(v)}"
                        else: return f"🔴 {int(v)}"
                    except:
                        return str(val)

                display_df = pivot_df.copy()
                for col in display_df.columns:
                    display_df[col] = display_df[col].apply(lambda x: add_icon_to_score(x, col))

                def color_score_bg(val):
                    val_str = str(val)
                    if "👑" in val_str:
                        return 'background-color: #fffacd; color: #000000; font-weight: bold;'
                    elif "🟢" in val_str:
                        return 'background-color: #c6efce; color: #006100; font-weight: bold;'
                    elif "🟡" in val_str:
                        return 'background-color: #ffeb9c; color: #9c6500; font-weight: bold;'
                    elif "🔴" in val_str:
                        return 'background-color: #ffc7ce; color: #9c0006; font-weight: bold;'
                    return ''

                try:
                    styled_df = display_df.style.map(color_score_bg)
                except AttributeError:
                    styled_df = display_df.style.applymap(color_score_bg)
                
                st.dataframe(styled_df, use_container_width=True)