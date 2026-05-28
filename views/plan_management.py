import streamlit as st
import datetime
import time
import pandas as pd

from utils.g_sheets import get_student_master
from utils.api_guard import robust_api_call

@st.cache_data(ttl=600, show_spinner=False)
def cached_get_student_master():
    return robust_api_call(get_student_master, fallback_value=pd.DataFrame())

def render_plan_management_page():
    st.header("🗺️ 生徒別 カリキュラム・学習計画管理")
    st.write("生徒ごとに年間ロードマップ、月間単元計画、週間のTo-Doをシームレスに管理します。")

    # 生徒マスターの読み込み
    df_students = cached_get_student_master()
    student_options = []
    if not df_students.empty and '生徒ID' in df_students.columns and '生徒名' in df_students.columns:
        student_options = (df_students['生徒ID'].astype(str) + " - " + df_students['生徒名']).tolist()

    if not student_options:
        st.warning("生徒データがありません。先に生徒個別ポータルから新入生を登録してください。")
        return

    selected_student = st.selectbox("👤 計画を確認・編集する生徒を選択してください", student_options, index=None, placeholder="--生徒を選択--")

    if selected_student is None:
        st.info("👆 生徒を選択すると、その子の学年やコースに合わせた計画表が作成・表示されます。")
        return

    # 生徒情報の抽出
    student_name = selected_student.split(" - ")[1]
    info = {}
    if not df_students.empty:
        row = df_students[df_students['生徒名'] == student_name]
        if not row.empty:
            info = row.iloc[0].to_dict()

    grade = info.get('学年', '未設定')
    course = info.get('契約コース', '未設定')
    is_exam = "🔥 受験生区分" if "受験生" in str(info.get('受験区分', '')) else "👤 非受験生"

    # 生徒のステータスカード
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**🎓 対象生徒:** {student_name} さん")
        c2.markdown(f"**🎒 学年・区分:** {grade} ({is_exam})")
        c3.markdown(f"**📋 現在の契約:** {course or '未設定'}")

    st.write("")

    # 🌟 本機能の核：年間・月間・週間をタブで綺麗に切り替える
    tab_year, tab_month, tab_week = st.tabs(["📅 ① 年間ロードマップ", "🗓️ ② 月間単元計画", "📋 ③ 週間To-Do・宿題指示"])

    # ==========================================
    # 📅 タブ1: 年間ロードマップ
    # ==========================================
    with tab_year:
        st.subheader("🎯 年間大目標・シーズンロードマップ")
        
        # 将来的にスプレッドシートに保存する用の入力欄
        target_goal = st.text_input("🏆 今年の絶対達成目標", value=info.get('志望校・目的', '') or "定期テストでの自己ベスト更新！", key="year_goal")
        
        st.write("")
        st.markdown("#### 🌊 シーズン別ロードマップ")
        
        # 塾の標準的なスケジュールを学年に応じて可視化
        col_phase1, col_phase2, col_phase3, col_phase4 = st.columns(4)
        
        with col_phase1:
            with st.container(border=True):
                st.markdown("##### 🌸 春期 (4〜6月)\n**【基礎の徹底固め】**")
                st.caption("・前学年の苦手単元の総ざらい\n・主要教科の基礎作法習得")
                st.checkbox("クリア！", value=True, key="p1_check")
                
        with col_phase2:
            with st.container(border=True):
                st.markdown("##### ☀️ 夏期 (7〜8月)\n**【大容量インプット】**")
                st.caption("・夏期講習による総復習\n・苦手教科の標準問題完成")
                st.checkbox("クリア！", value=False, key="p2_check")
                
        with col_phase3:
            with st.container(border=True):
                st.markdown("##### 🍁 秋期 (9〜11月)\n**【実戦応用・対策】**")
                st.caption("・定期テスト対策の最大化\n・入試過去問のスタート")
                st.checkbox("クリア！", value=False, key="p3_check")
                
        with col_phase4:
            with st.container(border=True):
                st.markdown("##### ❄️ 冬期 (12〜3月)\n**【総仕上げ・直前】**")
                st.caption("・志望校別過去問演習\n・学年末テスト対策と総仕上げ")
                st.checkbox("クリア！", value=False, key="p4_check")

        st.write("")
        st.button("💾 年間計画を保存", key="save_year_plan", type="primary")

    # ==========================================
    # 🗓️ タブ2: 月間単元計画
    # ==========================================
    with tab_month:
        current_month = datetime.date.today().month
        st.subheader(f"🗓️ {current_month}月の月間進捗目標")
        st.caption(f"※ {course or '登録コース'} の月間授業回数に基づき、消化すべき単元を定義します。")

        # 科目ごとの進捗計画（モックデータですが、セレクトボックス等で変更可能にします）
        with st.container(border=True):
            st.markdown("#### 📘 英語の月間計画")
            st.markdown("**使用教材:** フォレスタ英語")
            
            prog1 = st.slider("単元1: 不定詞の復習", 0, 100, 100, key="m_eng_1")
            prog2 = st.slider("単元2: 動名詞の基本概念", 0, 100, 60, key="m_eng_2")
            prog3 = st.slider("単元3: 現在完了の導入", 0, 100, 0, key="m_eng_3")
            
        with st.container(border=True):
            st.markdown("#### 📐 数学の月間計画")
            st.markdown("**使用教材:** 塾専用一次関数ワーク")
            
            prog4 = st.slider("単元1: 連立方程式の応用", 0, 100, 100, key="m_math_1")
            prog5 = st.slider("単元2: 一次関数のグラフと変域", 0, 100, 20, key="m_math_2")
            prog6 = st.slider("単元3: 一次関数と方程式の交点", 0, 100, 0, key="m_math_3")

        st.write("")
        st.button("💾 月間進捗目標を保存", key="save_month_plan", type="primary")

    # ==========================================
    # 📋 タブ3: 週間To-Do・宿題指示
    # ==========================================
    with tab_week:
        st.subheader("🚀 今週のTo-Do ＆ 自習タスク指示")
        st.caption("日々の自習室利用時や、自宅学習で生徒が迷わないための明確なタスク表です。")

        # 1週間の曜日ごとのTo-Doリスト
        days = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]
        
        for idx, day in enumerate(days):
            with st.expander(f"📅 {day} の学習タスク", expanded=(idx==0)):
                c_task1, c_task2 = st.columns([3, 1])
                
                # タスク内容の入力欄
                default_task = "宿題のテキスト P.12〜15 を解き直す" if idx % 2 == 0 else "単元テストのミス直し ＆ 自習室で30分暗記"
                if idx == 2: default_task = "🏫 通塾日：小テスト合格に向けて20分前に入室すること！"
                
                # 🌟 修正ポイント： key の {b} を削除しました！
                task_content = c_task1.text_input("タスク内容", value=default_task, key=f"task_val_{idx}")
                status = c_task2.selectbox("進捗", ["未着手", "進行中", "完了！"], index=2 if idx==0 else 0, key=f"task_status_{idx}")
                
        st.write("")
        st.button("💾 週間To-Doを確定・保存", key="save_week_plan", type="primary")