import streamlit as st
import pandas as pd
from utils.g_sheets import get_all_student_names, load_all_data, get_textbook_master

# ==========================================
# 🌟 APIエラー対策：キャッシュ（一時保存）機能の追加
# ==========================================
# 頻繁に変更されないデータは、一度取得したら一定時間使い回すことで通信回数を減らします。

@st.cache_data(ttl=600)  # 600秒(10分)間は再取得せず、手元のデータを使い回す
def cached_get_student_names():
    return get_all_student_names()

@st.cache_data(ttl=600)  # マスタデータも10分間キャッシュ
def cached_get_textbook_master():
    return get_textbook_master()

@st.cache_data(ttl=60)   # 生徒の成績データは更新される可能性があるので、短め(1分)にキャッシュ
def cached_load_all_data(student_name):
    return load_all_data(student_name)

# ==========================================

def render_quiz_list_page():
    st.header("📝 小テスト進捗＆習熟度マップ")
    st.write("縦軸がテキスト、横軸が章です。タブを切り替えて各テキストの進捗を確認しましょう🎨")

    # 1. 生徒の選択（🌟キャッシュ版を使用）
    student_names = cached_get_student_names()
    selected_student = st.selectbox("👤 生徒を選択", ["-- 選択 --"] + student_names)
    
    if selected_student == "-- 選択 --":
        st.stop()

    with st.spinner("習熟度データを集計中..."):
        # 2. データの読み込み（🌟キャッシュ版を使用）
        df_history = cached_load_all_data(selected_student)
        
        # --- マスタデータの処理 ---（🌟キャッシュ版を使用）
        master_dict = cached_get_textbook_master()
        flat_data = []
        for text_name, chaps in master_dict.items():
            for chap in chaps:
                flat_data.append({'テキスト': text_name, '章': chap})
                
        df_master = pd.DataFrame(flat_data, columns=['テキスト', '章'])

        if df_master.empty:
            st.warning("⚠️ マスタデータが読み込めませんでした。")
            st.stop()

        # --- 授業記録（生徒データ）の処理 ---
        if df_history.empty:
            st.warning("授業記録がまだありません。")
            st.stop()

        df_history['点数'] = pd.to_numeric(df_history['点数'], errors='coerce')
        df_quiz = df_history.dropna(subset=['点数']).copy()

        # 3. 前回小テスト日の表示
        if not df_quiz.empty:
            df_quiz['日時'] = pd.to_datetime(df_quiz['日時'], format='mixed', errors='coerce')
            last_date = df_quiz['日時'].max().strftime("%Y年%m月%d日")
            st.success(f"📅 前回小テスト実施日: **{last_date}**")
        else:
            st.info("📅 まだ小テストの記録がありません。")
            st.stop()

        # 4. マスタと合体
        best_scores = df_quiz.groupby(['テキスト', '単元'])['点数'].max().reset_index()
        best_scores = best_scores.rename(columns={'単元': '章', '点数': '最高点数'})

        df_master['章'] = df_master['章'].astype(str).str.replace('第', '').str.replace('章', '').str.strip()
        best_scores['章'] = best_scores['章'].astype(str).str.replace('第', '').str.replace('章', '').str.strip()

        df_merged = pd.merge(df_master, best_scores, on=['テキスト', '章'], how='left')

        # ==========================================
        # 🌟 ここからが超進化版の魔法！！！
        # ==========================================

        # テキストの名前一覧を取得して、タブを作る！
        textbook_names = df_master['テキスト'].unique().tolist()
        
        if not textbook_names:
            st.warning("テキスト一覧が見つかりません。")
            st.stop()

        # タブを生成！
        tabs = st.tabs(textbook_names)

        # 各テキストごとにタブの中身を作っていく
        for i, text_name in enumerate(textbook_names):
            with tabs[i]: # それぞれのタブの中に描画する
                # このテキストのデータだけを取り出す
                df_text = df_merged[df_merged['テキスト'] == text_name]
                
                # --- 🎯 達成率の計算 ---
                total_chaps = len(df_text) # 全部の章の数
                done_chaps = df_text['最高点数'].notna().sum() # テストを受けた（点数がある）章の数
                
                if total_chaps > 0:
                    progress_rate = int((done_chaps / total_chaps) * 100)
                else:
                    progress_rate = 0
                
                # ゲージ（プログレスバー）の表示
                st.subheader(f"📊 達成率: {progress_rate}% ({done_chaps}/{total_chaps}章クリア)")
                st.progress(progress_rate / 100.0)
                st.write("") # 少し隙間を空ける

                # --- 🎨 表の作成 ---
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
                    # 文字の中から数字だけを抜き出して、数値として比較する
                    nums = re.findall(r'\d+', str(col_name))
                    if nums:
                        return int(nums[0]) # "10"なら10、"2"なら2として扱う
                    return 9999 # もし「まとめ」など数字以外の章があれば一番右端に寄せる

                # 正しい順番に並び替えた列名リストを作って、表を上書き！
                sorted_cols = sorted(pivot_df.columns.tolist(), key=sort_chapter_key)
                pivot_df = pivot_df[sorted_cols]

                # --- ✨ アイコン化＆カラーリングの魔法（絶対表示させる版） ---
                def add_icon_to_score(val):
                    """点数そのものをアイコン付きの文字に変身させる！"""
                    if pd.isna(val) or val == "":
                        return ""
                    try:
                        v = float(val)
                        if v == 100: return f"👑 100"
                        elif v >= 80: return f"🟢 {int(v)}"
                        elif v >= 60: return f"🟡 {int(v)}"
                        else: return f"🔴 {int(v)}"
                    except:
                        return str(val)

                # まず、表の中身をすべて「アイコン付きの文字」に書き換える！
                display_df = pivot_df.copy()
                for col in display_df.columns:
                    display_df[col] = display_df[col].map(add_icon_to_score)

                def color_score_bg(val):
                    """アイコンのマークを見て背景色を決定！"""
                    val_str = str(val)
                    if "👑" in val_str:
                        return 'background-color: #fffacd; color: #000000; font-weight: bold;' # ゴールド
                    elif "🟢" in val_str:
                        return 'background-color: #c6efce; color: #006100; font-weight: bold;' # 緑
                    elif "🟡" in val_str:
                        return 'background-color: #ffeb9c; color: #9c6500; font-weight: bold;' # 黄
                    elif "🔴" in val_str:
                        return 'background-color: #ffc7ce; color: #9c0006; font-weight: bold;' # 赤
                    return ''

                # 色塗り魔法をかけて表示！（※Pandasのバージョン違いにも対応）
                try:
                    styled_df = display_df.style.map(color_score_bg)
                except AttributeError:
                    styled_df = display_df.style.applymap(color_score_bg)
                
                st.dataframe(styled_df, use_container_width=True)