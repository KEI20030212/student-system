import streamlit as st
import datetime
import time
import pandas as pd
import json

from utils.g_sheets import get_student_master, get_textbook_master, save_learning_plan
from utils.api_guard import robust_api_call

@st.cache_data(ttl=600, show_spinner=False)
def cached_get_student_master():
    df = robust_api_call(get_student_master, fallback_value=pd.DataFrame())
    return df.copy() if not df.empty else df

@st.cache_data(ttl=600, show_spinner=False)
def cached_get_textbook_master():
    dct = robust_api_call(get_textbook_master, fallback_value={})
    return dict(dct)

def render_plan_management_page():
    st.header("🗺️ 生徒別 カリキュラム・学習計画管理")
    st.write("生徒ごとに年間ロードマップ、月間単元計画、週間のTo-Doをシームレスに管理します。")

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

    student_id = selected_student.split(" - ")[0]
    student_name = selected_student.split(" - ")[1]
    
    info = {}
    if not df_students.empty:
        row = df_students[df_students['生徒名'] == student_name]
        if not row.empty:
            info = row.iloc[0].to_dict()

    grade = info.get('学年', '未設定')
    course = info.get('契約コース', '未設定')
    is_exam = "🔥 受験生区分" if "受験生" in str(info.get('受験区分', '')) else "👤 非受験生"

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**🎓 対象生徒:** {student_name} さん")
        c2.markdown(f"**🎒 学年・区分:** {grade} ({is_exam})")
        c3.markdown(f"**📋 現在の契約:** {course or '未設定'}")

    st.write("")

    tab_year, tab_month, tab_week, tab_flow = st.tabs(["📅 ① 年間ロードマップ", "🗓️ ② 月間単元計画", "📋 ③ 週間To-Do", "🏫 ④ 標準授業フロー(型)"])

    # ==========================================
    # 📅 タブ1: 年間ロードマップ
    # ==========================================
    with tab_year:
        st.subheader("🎯 年間大目標・シーズンロードマップ")
        target_goal = st.text_input("🏆 今年の絶対達成目標", value=info.get('志望校・目的', '') or "定期テストでの自己ベスト更新！", key="year_goal")
        
        st.write("")
        st.markdown("#### 🌊 シーズン別ロードマップ")
        col_phase1, col_phase2, col_phase3, col_phase4 = st.columns(4)
        
        with col_phase1:
            with st.container(border=True):
                st.markdown("##### 🌸 春期 (4〜6月)\n**【基礎の徹底固め】**")
                st.caption("・前学年の苦手単元の総ざらい\n・主要教科の基礎作法習得")
                p1_check = st.checkbox("クリア！", value=True, key="p1_check")
                
        with col_phase2:
            with st.container(border=True):
                st.markdown("##### ☀️ 夏期 (7〜8月)\n**【大容量インプット】**")
                st.caption("・夏期講習による総復習\n・苦手教科の標準問題完成")
                p2_check = st.checkbox("クリア！", value=False, key="p2_check")
                
        with col_phase3:
            with st.container(border=True):
                st.markdown("##### 🍁 秋期 (9〜11月)\n**【実戦応用・対策】**")
                st.caption("・定期テスト対策の最大化\n・入試過去問のスタート")
                p3_check = st.checkbox("クリア！", value=False, key="p3_check")
                
        with col_phase4:
            with st.container(border=True):
                st.markdown("##### ❄️ 冬期 (12〜3月)\n**【総仕上げ・直前】**")
                st.caption("・志望校別過去問演習\n・学年末テスト対策と総仕上げ")
                p4_check = st.checkbox("クリア！", value=False, key="p4_check")

        st.write("")
        if st.button("💾 年間計画を保存", key="save_year_plan", type="primary"):
            plan_data = f"【目標】{target_goal}\n春:{'済' if p1_check else '未'} / 夏:{'済' if p2_check else '未'} / 秋:{'済' if p3_check else '未'} / 冬:{'済' if p4_check else '未'}"
            with st.spinner("保存中..."):
                success = robust_api_call(save_learning_plan, student_id, student_name, "年間ロードマップ", plan_data, fallback_value=False)
                if success:
                    st.success("✅ 年間計画を保存しました！")

    # ==========================================
    # 🗓️ タブ2: 月間単元計画
    # ==========================================
    with tab_month:
        current_month = datetime.date.today().month
        st.subheader(f"🗓️ {current_month}月の月間進捗目標")
        st.caption(f"※ {course or '登録コース'} の月間授業回数に基づき、消化すべき単元を定義します。")

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
        if st.button("💾 月間進捗目標を保存", key="save_month_plan", type="primary"):
            plan_data = f"[英語] 単元1:{prog1}% / 単元2:{prog2}% / 単元3:{prog3}%\n[数学] 単元1:{prog4}% / 単元2:{prog5}% / 単元3:{prog6}%"
            with st.spinner("保存中..."):
                success = robust_api_call(save_learning_plan, student_id, student_name, "月間単元計画", plan_data, fallback_value=False)
                if success:
                    st.success("✅ 月間進捗を保存しました！")

    # ==========================================
    # 📋 タブ3: 週間To-Do・宿題指示
    # ==========================================
    with tab_week:
        st.subheader("🚀 今週のTo-Do ＆ 自習タスク指示")
        st.caption("日々の自習室利用時や、自宅学習で生徒が迷わないための明確なタスク表です。")

        days = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]
        week_tasks = []
        
        for idx, day in enumerate(days):
            with st.expander(f"📅 {day} の学習タスク", expanded=(idx==0)):
                c_task1, c_task2 = st.columns([3, 1])
                default_task = "宿題のテキスト P.12〜15 を解き直す" if idx % 2 == 0 else "単元テストのミス直し ＆ 自習室で30分暗記"
                if idx == 2: default_task = "🏫 通塾日：小テスト合格に向けて20分前に入室すること！"
                
                t_val = c_task1.text_input("タスク内容", value=default_task, key=f"task_val_{idx}")
                t_stat = c_task2.selectbox("進捗", ["未着手", "進行中", "完了！"], index=2 if idx==0 else 0, key=f"task_status_{idx}")
                week_tasks.append(f"【{day}】 {t_val} ({t_stat})")
                
        st.write("")
        if st.button("💾 週間To-Doを確定・保存", key="save_week_plan", type="primary"):
            plan_data = "\n".join(week_tasks)
            with st.spinner("保存中..."):
                success = robust_api_call(save_learning_plan, student_id, student_name, "週間To-Do", plan_data, fallback_value=False)
                if success:
                    st.success("✅ 週間To-Doを保存しました！")

    # ==========================================
    # 🏫 タブ4: 標準授業フロー(型)の設計
    # ==========================================
    with tab_flow:
        st.subheader("🏫 1回の授業の「型」をデザインする")
        st.write("この生徒の普段の授業（1コマ）の流れを**科目ごと**に設定します。**将来的に、この設定が授業記録画面に自動入力されるようになります！**")
        
        # 🌟 科目を選ぶUIを追加！
        target_subject = st.selectbox("📚 フローを設定する科目", ["英語", "数学", "国語", "理科", "社会"], key="flow_subject")
        
        st.divider()
        st.markdown(f"##### 🔄 【{target_subject}】の授業フローステップ")
        
        text_options = list(cached_get_textbook_master().keys())
        
        flow_data_list = []
        for step in range(1, 4):
            with st.container(border=True):
                st.markdown(f"**🟢 Step {step}**")
                c_f1, c_f2, c_f3 = st.columns([2, 2, 1])
                
                # 🌟 各入力エリアのKeyに {target_subject} を組み込むことで、英語と数学で入力データが混ざらない安全設計に！
                selected_text = c_f1.selectbox(
                    f"使用テキスト (Step {step})", 
                    ["設定なし", "🔥 小テスト実施"] + text_options, 
                    key=f"flow_txt_{target_subject}_{step}"
                )
                
                target_range = c_f2.text_input(
                    "実施範囲の目安", 
                    placeholder="例: 1章分, P.10〜15 など", 
                    key=f"flow_range_{target_subject}_{step}"
                )
                
                time_est = c_f3.number_input(
                    "目安時間(分)", 
                    min_value=5, max_value=90, value=30 if step==1 else 20, step=5, 
                    key=f"flow_time_{target_subject}_{step}"
                )
                
                hw_flag = False
                if selected_text not in ["設定なし", "🔥 小テスト実施"]:
                    hw_flag = st.checkbox(
                        f"⚠️ {selected_text} が時間内に終わらなかった場合は、そのまま「次回の宿題」に回す", 
                        value=True, 
                        key=f"flow_hw_flag_{target_subject}_{step}"
                    )
                
                if selected_text != "設定なし":
                    hw_str = "宿題に回す" if hw_flag else "宿題にしない"
                    flow_data_list.append(f"[Step {step}] {selected_text} (範囲: {target_range or '指定なし'} / {time_est}分) - {hw_str}")

        st.write("")
        if st.button(f"💾 {target_subject} の授業フローを保存", key=f"save_flow_plan_{target_subject}", type="primary"):
            if not flow_data_list:
                st.warning("⚠️ Stepが1つも設定されていません。")
            else:
                # 🌟 JSON形式（辞書）に変換して保存
                flow_dict = {
                    "subject": target_subject,
                    "step1": {
                        "text": st.session_state.get(f"flow_txt_{target_subject}_1"), 
                        "range": st.session_state.get(f"flow_range_{target_subject}_1"), 
                        "time": st.session_state.get(f"flow_time_{target_subject}_1"), 
                        "hw": st.session_state.get(f"flow_hw_flag_{target_subject}_1", False)
                    },
                    "step2": {
                        "text": st.session_state.get(f"flow_txt_{target_subject}_2"), 
                        "range": st.session_state.get(f"flow_range_{target_subject}_2"), 
                        "time": st.session_state.get(f"flow_time_{target_subject}_2"), 
                        "hw": st.session_state.get(f"flow_hw_flag_{target_subject}_2", False)
                    },
                    "step3": {
                        "text": st.session_state.get(f"flow_txt_{target_subject}_3"), 
                        "range": st.session_state.get(f"flow_range_{target_subject}_3"), 
                        "time": st.session_state.get(f"flow_time_{target_subject}_3"), 
                        "hw": st.session_state.get(f"flow_hw_flag_{target_subject}_3", False)
                    }
                }
                
                plan_data_str = json.dumps(flow_dict, ensure_ascii=False)
                
                with st.spinner(f"{target_subject} の授業フローを保存中..."):
                    # 🌟 保存時の名前を "授業フロー_英語" のように科目名入りで保存！
                    plan_type_str = f"授業フロー_{target_subject}"
                    success = robust_api_call(save_learning_plan, student_id, student_name, plan_type_str, plan_data_str, fallback_value=False)
                    if success:
                        st.success(f"✅ {target_subject} の授業フロー（型）をスプレッドシートに保存しました！")
                        
        st.info("💡 **【今後の連携イメージ】**\nこれを保存しておくと、将来 `multi_input.py` でこの生徒の「英語」や「数学」を選んだ瞬間に、ここで設定した通りのテキストや宿題指示が自動で画面にセットされるようになります！")