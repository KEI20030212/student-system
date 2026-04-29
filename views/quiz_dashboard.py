import streamlit as st
import pandas as pd
import datetime

# ==========================================
# 🌟 utils/g_sheets.py から専用関数を呼び出し
# ==========================================
from utils.g_sheets import (
    get_all_student_names, 
    get_quiz_master_dict,                
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
    # 「設定_小テスト一覧」から取得
    return robust_api_call(get_quiz_master_dict, fallback_value={})

@st.cache_data(ttl=60)   
def cached_load_quiz_data(student_name):
    return robust_api_call(load_quiz_data_from_dedicated_sheet, student_name, fallback_value=pd.DataFrame())

# ==========================================

def render_quiz_list_page():
    st.header("📝 小テスト進捗＆習熟度マップ")
    st.write("実施した小テストの結果を入力・確認できるページです🎨")

    # 1. 生徒の選択
    student_names = cached_get_student_names()
    
    if not student_names:
        st.error("生徒データの取得に失敗しました。時間をおいて再読み込みしてください。")
        st.stop()

    selected_student = st.selectbox("👤 生徒を選択", ["-- 選択 --"] + student_names)
    
    if selected_student == "-- 選択 --":
        st.stop()

    # 2. 小テスト設定の取得
    quiz_details = cached_get_quiz_details()
    
    # 🌟 設定シートから「小テスト名」の重複なしリストを作成
    # 既存の get_quiz_master_dict は "テスト名_単元" をキーにしているため、_の前半を取得
    quiz_names = []
    for key in quiz_details.keys():
        if "_" in key:
            q_name = key.split("_", 1)[0]
            if q_name not in quiz_names:
                quiz_names.append(q_name)

    # ==========================================
    # 🌟 小テスト結果の入力フォーム
    # ==========================================
    with st.expander("📝 小テスト結果を登録する"):
        st.write(f"**{selected_student}** さんの結果を入力します。")
        
        with st.form("quiz_input_form"):
            col1, col2 = st.columns(2)
            
            if not quiz_names:
                st.warning("「設定_小テスト一覧」のデータが取得できません。")
                st.form_submit_button("記録不可", disabled=True)
            else:
                # 🌟 小テスト名 (設定シートから選択)
                target_quiz = col1.selectbox("📝 小テスト名", quiz_names)
                # 🌟 単元・回 (数字のみ入力)
                target_unit = col2.number_input("📖 単元・回", min_value=1, value=1, step=1)
                
                # 満点の取得 (設定シートで target_quiz に設定されている満点を探す)
                max_score = 100
                for k, v in quiz_details.items():
                    if k.startswith(f"{target_quiz}_"):
                        max_score = int(v.get("full_marks", 100))
                        break
                
                col3, col4 = st.columns(2)
                score = col3.number_input(f"💯 点数 (満点: {max_score})", min_value=0, max_value=max_score, value=max_score, step=1)
                test_date = col4.date_input("📅 実施日", datetime.date.today())
                
                submit_quiz = st.form_submit_button("この内容で記録する ✨", type="primary")
                
                if submit_quiz:
                    if target_unit < 1:
                        st.error("⚠️ 「単元・回」を入力してください。")
                    else:
                        with st.spinner("記録中..."):
                            success = robust_api_call(
                                save_quiz_to_dedicated_sheet,
                                test_date.strftime("%Y/%m/%d"), 
                                selected_student, 
                                target_quiz,  
                                target_unit,  # 🌟 ここで手入力した値が「単元」列に保存されます！
                                score,
                                "", 
                                "自習",
                                fallback_value=False
                            )
                            
                            if success:
                                st.success(f"【{target_quiz} - {target_unit}】を {score}点で記録しました！")
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
        
        if df_quiz.empty:
            st.info("小テストの記録がまだありません。結果を登録するとここに表が表示されます。")
            st.stop()

        df_quiz['点数'] = pd.to_numeric(df_quiz['点数'], errors='coerce')
        df_quiz = df_quiz.dropna(subset=['点数']).copy()
        
        if not df_quiz.empty:
            df_quiz['日時'] = pd.to_datetime(df_quiz['日時'], format='mixed', errors='coerce')
            last_date = df_quiz['日時'].max().strftime("%Y年%m月%d日")
            st.success(f"📅 前回実施日: **{last_date}**")

        # 🌟 設定シートに単元一覧がないため、記録データから「受けたテストの単元」を抽出して表を作る
        best_scores = df_quiz.groupby(['テキスト', '単元'])['点数'].max().reset_index()
        best_scores = best_scores.rename(columns={'テキスト': '小テスト名', '点数': '最高点数'})

        # タブ表示（生徒が受けたことがある小テスト名ごと）
        quiz_list = best_scores['小テスト名'].unique().tolist()
        
        if not quiz_list:
            st.stop()
            
        tabs = st.tabs(quiz_list)

        for i, q_name in enumerate(quiz_list):
            with tabs[i]: 
                df_display = best_scores[best_scores['小テスト名'] == q_name]
                
                # ピボットテーブル作成
                pivot_df = df_display.pivot_table(
                    index='小テスト名', 
                    columns='単元', 
                    values='最高点数', 
                    aggfunc='max'
                )
                
                if pivot_df.empty:
                    continue

                # 列を数字順に並び替え
                import re
                def sort_key(c):
                    nums = re.findall(r'\d+', str(c))
                    return int(nums[0]) if nums else 999
                pivot_df = pivot_df[sorted(pivot_df.columns.tolist(), key=sort_key)]

                # アイコン付与と満点判定
                def add_icon(val):
                    if pd.isna(val) or val == "": return ""
                    
                    # 満点の取得
                    full_m = 100
                    for k, v in quiz_details.items():
                        if k.startswith(f"{q_name}_"):
                            full_m = float(v.get("full_marks", 100))
                            break
                            
                    try:
                        v = float(val)
                        ratio = v / full_m if full_m > 0 else 0
                        if ratio >= 1.0: return f"👑 {int(v)}"
                        elif ratio >= 0.8: return f"🟢 {int(v)}"
                        elif ratio >= 0.6: return f"🟡 {int(v)}"
                        else: return f"🔴 {int(v)}"
                    except:
                        return str(val)

                styled_display = pivot_df.copy()
                for col in styled_display.columns:
                    styled_display[col] = styled_display[col].apply(add_icon)

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