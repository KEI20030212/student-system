import streamlit as st
import time
from utils.g_sheets import get_all_student_names

# 完成している2つのファイルを部品として読み込む
from views.student_details import render_student_details_page
from views.analysis import render_analysis_page

def render_student_portal_page():
    st.header("🏫 生徒個別ポータル")
    
    # 🌟 変更: 生徒一覧の取得にも Exponential Backoff を適用
    student_names = []
    max_retries = 5
    with st.spinner("生徒データを読み込み中..."):
        for attempt in range(max_retries):
            try:
                student_names = get_all_student_names()
                # 取得できたらループを抜ける（空っぽのリストが返ってきた場合もエラーではないので抜ける）
                if student_names is not None: 
                    break
            except Exception:
                pass # エラーが起きても下に進んで待機する
            
            # 取得に失敗したら、待機時間を倍にして再チャレンジ (1秒, 2秒, 4秒, 8秒...)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                
    if not student_names: 
        st.warning("まだ生徒が登録されていません。")
        return

    # 🌟 全機能共通の生徒選択バー
    selected_student = st.selectbox("👤 対象の生徒を選択してください", ["-- 選択 --"] + student_names)

    # 🌟 生徒が選ばれていない時の「機能紹介画面」！
    if selected_student == "-- 選択 --":
        st.info("👆 上のメニューから生徒を選択すると、以下の個別メニューが利用できます！")
        
        c1, c2 = st.columns(2)
        with c1:
            with st.container(border=True):
                st.markdown("### 👤 生徒詳細・成績入力")
                st.write("生徒の基本データや、テスト結果を管理します。")
                st.markdown("""
                - **🩺 カルテ**: 能力・やる気マトリクスの確認
                - **✍️ 成績入力**: 定期テスト・内申点・模試の入力
                - **📈 成績推移**: 過去の点数グラフの確認
                """)
        with c2:
            with st.container(border=True):
                st.markdown("### 📊 個別分析・履歴・振替")
                st.write("日々の授業履歴や、未消化の振替授業を管理します。")
                st.markdown("""
                - **⚠️ 振替管理**: 未消化の授業コマ数を自動カウント
                - **📊 学習グラフ**: ページ数や単元ごとの点数を可視化
                - **📚 履歴編集**: 過去の授業記録をスプレッドシートに直接上書き修正
                """)
        return

    # 🌟 生徒が選ばれたら、機能切り替えボタンを表示
    app_mode = st.radio(
        "📂 表示するメニューを選んでください", 
        ["👤 生徒詳細・成績入力", "📊 個別分析・履歴・振替管理"], 
        horizontal=True
    )
    
    st.divider()
    
    # 選ばれた機能に応じて、生徒名を渡しながら画面を呼び出す
    if app_mode == "👤 生徒詳細・成績入力":
        render_student_details_page(selected_student)
    else:
        render_analysis_page(selected_student)