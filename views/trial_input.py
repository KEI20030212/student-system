import streamlit as st
import datetime
import time
import os
import pickle
import pandas as pd

from utils.g_sheets import (
    get_student_master,
    get_all_teacher_names,
    add_new_textbook,        
    get_textbook_master,
    get_quiz_master_dict,
    get_type_advice_dict,
    save_trial_lesson_to_spreadsheet # 🌟 先ほど作った専用の保存関数
)
from utils.calc_logic import calculate_quiz_points
from utils.api_guard import robust_api_call

# --- 🚀 キャッシュ関数 ---
@st.cache_data(ttl=600, show_spinner=False)
def cached_get_student_master():
    return robust_api_call(get_student_master, fallback_value=pd.DataFrame())

@st.cache_data(ttl=600, show_spinner=False)
def cached_get_teacher_names():
    return robust_api_call(get_all_teacher_names, fallback_value=[])

@st.cache_data(ttl=600, show_spinner=False)
def cached_get_textbook_master():
    return robust_api_call(get_textbook_master, fallback_value={})

@st.cache_data(ttl=600, show_spinner=False)
def cached_get_quiz_master():
    return robust_api_call(get_quiz_master_dict, fallback_value={})

@st.cache_data(ttl=600, show_spinner=False)
def cached_get_type_advice():
    return robust_api_call(get_type_advice_dict, fallback_value={})

# 🌟 一時保存対象のキー（通常授業と混ざらないように "t_" を付けています）
DRAFT_PREFIXES_TRIAL = (
    "t_num_blocks", "t_class_date", "t_class_type", 
    "t_sb_", "t_sel_student", "t_new_name", "t_att", "t_late", "t_sub", "t_texts", "t_new_usage_text", 
    "t_adv_start", "t_adv_end", "t_num_q", "t_q_name", "t_q_chap", "t_q_score", "t_w",
    "t_conc", "t_reac", "t_advc", "t_p_msg", "t_next_h"
)

# ==========================================
# 🌟 タブ増減のコールバック関数
# ==========================================
def add_trial_tab():
    st.session_state['t_num_blocks'] = st.session_state.get('t_num_blocks', 1) + 1

def remove_trial_tab():
    num_blocks = st.session_state.get('t_num_blocks', 1)
    if num_blocks > 1:
        b_to_delete = num_blocks - 1
        for key in list(st.session_state.keys()):
            if f"t_{b_to_delete}" in key:
                del st.session_state[key]
        st.session_state['t_num_blocks'] = num_blocks - 1

def render_trial_input_page():
    user_id = st.session_state.get('user_id', st.session_state.get('username', 'default_user'))
    draft_file = f"trial_draft_{user_id}.pkl"

    with st.sidebar:
        st.header("💾 一時保存（体験用）")
        c1, c2 = st.columns(2)
        if c1.button("💾 保存", key="t_save_draft", use_container_width=True):
            draft = {k: v for k, v in st.session_state.items() if any(k.startswith(p) for p in DRAFT_PREFIXES_TRIAL)}
            with open(draft_file, "wb") as f:
                pickle.dump(draft, f)
            st.success("保存しました！")
            
        if c2.button("📂 復元", key="t_load_draft", use_container_width=True):
            if os.path.exists(draft_file):
                with open(draft_file, "rb") as f:
                    draft = pickle.load(f)
                for k, v in draft.items():
                    st.session_state[k] = v
                st.success("復元しました！")
                time.sleep(1)
                st.rerun() 
            else:
                st.warning("データがありません")

    student_df = cached_get_student_master()
    student_options = (student_df['生徒ID'].astype(str) + " - " + student_df['生徒名']).tolist() if not student_df.empty else []

    teacher_names = cached_get_teacher_names()
    text_options = list(cached_get_textbook_master().keys())
    
    quiz_details = cached_get_quiz_master()
    quiz_names = []
    for key in quiz_details.keys():
        if "_" in key:
            q_name = key.split("_", 1)[0]
            if q_name not in quiz_names:
                quiz_names.append(q_name)
    if not quiz_names:
        quiz_names = ["設定なし"]

    st.write("### 🔰 体験授業 報告書入力")
    num_blocks = st.session_state.get('t_num_blocks', 1)

    col_add, col_del, _ = st.columns([2, 2, 6])
    with col_add:
        st.button("➕ 新しいコマを追加", key="t_add", use_container_width=True, on_click=add_trial_tab)
    with col_del:
        if num_blocks > 1:
            st.button("➖ 最後のタブを削除", key="t_del", use_container_width=True, on_click=remove_trial_tab)

    tabs = st.tabs([f"📝 コマ {b+1}" for b in range(num_blocks)])
    
    single_save_triggered = None
    all_save_triggered = None

    for b in range(num_blocks):
        with tabs[b]:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([1.5, 1.5, 1.5, 2])
                
                date = c1.date_input("授業日", datetime.date.today(), key=f"t_class_date_{b}")
                teacher_name = c2.selectbox("👨‍🏫 担当講師", teacher_names, index=None, placeholder="講師を選択", key=f"t_sb_teacher_{b}")
                class_type = c3.radio("👥 授業形態", ["1:1", "1:2", "1:3"], horizontal=True, key=f"t_class_type_{b}")
                time_slots = [
                    "Aコマ目 (9:30~11:00)", "Bコマ目 (11:10~12:40)",
                    "0コマ目 (13:10~14:40)", "1コマ目 (14:50~16:20)",
                    "2コマ目 (16:40~18:10)", "3コマ目 (18:20~19:50)", "4コマ目 (20:00~21:30)"
                ]
                class_slot = c4.selectbox("⏰ 授業コマ", time_slots, index=None, placeholder="コマを選択", key=f"t_sb_class_slot_{b}")

            if not teacher_name or not class_slot:
                st.info(f"👆 コマ {b+1} の「担当講師」と「授業コマ」を選択してください。")
                continue 

            num_students = int(class_type.split(":")[1])
            st.divider()
            cols = st.columns(num_students)
            input_data_list = []

            for i in range(num_students):
                with cols[i]:
                    with st.container(border=True):
                        is_saved = st.session_state.get(f"t_saved_flag_{b}_{i}", False)
                        saved_name = st.session_state.get(f"t_saved_name_{b}_{i}", "生徒")

                        if is_saved:
                            st.success(f"✅ {saved_name} さんの体験記録は保存済みです。")
                        else:
                            # 🌟 体験なので「新規登録」をデフォルトに設定
                            selected_student = st.selectbox("生徒名", ["🆕 新規登録（体験生）"] + student_options, index=0, key=f"t_sel_student_{b}_{i}")
                            
                            name = None
                            if selected_student == "🆕 新規登録（体験生）":
                                name = st.text_input("体験生徒の名前", key=f"t_new_name_{b}_{i}")
                            elif selected_student:
                                name = selected_student.split(" - ")[1]

                            if name:
                                # 🌟 【神アドバイス機能】
                                type_advice_dict = cached_get_type_advice()
                                student_type_str = ""
                                if not student_df.empty and 'タイプ' in student_df.columns:
                                    row = student_df[student_df['生徒名'] == name]
                                    if not row.empty:
                                        student_type_str = str(row.iloc[0].get('タイプ', ''))
                                
                                if student_type_str and student_type_str.lower() != "nan":
                                    advices = [f"・{t_adv}" for t_key, t_adv in type_advice_dict.items() if t_key in student_type_str]
                                    if advices:
                                        st.info("💡 **指導アドバイス（生徒タイプ別）**\n\n" + "\n".join(advices))

                                attendance = st.selectbox("📅 出欠状況", ["出席", "欠席（振替あり）", "欠席（振替なし）"], key=f"t_att_{b}_{i}")
                                late_time = st.number_input("⏰ 遅刻時間 (分)", min_value=0, value=0, step=5, key=f"t_late_{b}_{i}")

                                if "欠席" in attendance:
                                    st.warning("欠席のため入力はスキップされます。")
                                    input_data_list.append({"name": name, "attendance": attendance, "late_time": late_time})
                                else:
                                    subject = st.selectbox("科目", ["英語", "数学", "国語", "理科", "社会"], index=None, placeholder="科目を選択", key=f"t_sub_{b}_{i}")
                                    
                                    if subject:
                                        st.write("📚 **使用テキストと進捗**")
                                        usage_text_options = ["🆕 新規テキスト入力"] + text_options
                                        selected_texts = st.multiselect("使用テキスト (複数可)", usage_text_options, key=f"t_texts_{b}_{i}")
                                        
                                        if "🆕 新規テキスト入力" in selected_texts:
                                            new_usage_text = st.text_input("📝 新しいテキスト名を入力", key=f"t_new_usage_text_{b}_{i}")
                                            if new_usage_text:
                                                robust_api_call(add_new_textbook, new_usage_text)
                                                selected_texts.remove("🆕 新規テキスト入力")
                                                if new_usage_text not in selected_texts:
                                                    selected_texts.append(new_usage_text)
                                                cached_get_textbook_master.clear()

                                        advanced_p_list = []
                                        if selected_texts:
                                            text_name_str = "、".join(selected_texts)
                                            for t_idx, text_name in enumerate(selected_texts):
                                                st.caption(f"📘 {text_name} の進捗")
                                                col_adv1, col_adv2 = st.columns(2)
                                                with col_adv1:
                                                    adv_start = st.number_input(f"開始P", min_value=0, value=0, key=f"t_adv_start_{b}_{i}_{t_idx}")
                                                with col_adv2:
                                                    adv_end = st.number_input(f"終了P", min_value=0, value=0, key=f"t_adv_end_{b}_{i}_{t_idx}")
                                                
                                                if adv_end >= adv_start and adv_end > 0:
                                                    advanced_p_list.append(f"{text_name}: P.{adv_start}〜{adv_end}")
                                                else:
                                                    advanced_p_list.append(f"{text_name}: -")
                                            advanced_p_str = "\n".join(advanced_p_list)
                                        else:
                                            text_name_str = "-"
                                            advanced_p_str = "-"
                                        
                                        st.divider()
                                        num_quizzes = st.number_input("💯 小テスト実施 (あれば)", min_value=0, max_value=2, value=0, step=1, key=f"t_num_q_{b}_{i}")
                                        quiz_records = []
                                        if num_quizzes > 0:
                                            for q_idx in range(num_quizzes):
                                                with st.container(border=True):
                                                    q_name = st.selectbox(f"テスト名", quiz_names, index=None, key=f"t_q_name_{b}_{i}_{q_idx}")
                                                    current_max = 100 
                                                    if q_name:
                                                        matched_marks = [v["full_marks"] for k, v in quiz_details.items() if k.startswith(f"{q_name}_")]
                                                        if matched_marks:
                                                            current_max = int(pd.Series(matched_marks).mode()[0])

                                                    cq1, cq2 = st.columns(2)
                                                    with cq1:
                                                        target_chap = st.number_input("単元/回", min_value=1, value=1, step=1, key=f"t_q_chap_{b}_{i}_{q_idx}")
                                                    with cq2:
                                                        score = st.number_input(f"点数 (/{current_max})", min_value=0, max_value=current_max, value=current_max, step=1, key=f"t_q_score_{b}_{i}_{q_idx}")
                                                    quiz_records.append({"quiz_name": q_name or "不明", "unit": target_chap, "score": score})

                                        st.divider()
                                        st.write("🧠 **授業中の様子・評価**")
                                        col_eval1, col_eval2 = st.columns(2)
                                        with col_eval1:
                                            concentration = st.selectbox("集中力", ["超集中", "前向き", "緊張気味", "ムラあり", "集中できない"], index=1, key=f"t_conc_{b}_{i}")
                                        with col_eval2:
                                            reaction = st.selectbox("ミスへの反応", ["原因を分析した", "悔しがった", "教えを素直に聞いた", "放置しようとした"], index=0, key=f"t_reac_{b}_{i}")

                                        st.divider()
                                        st.write("💬 **体験授業コメント**")
                                        advice = st.text_area("🌟 生徒の長所・褒めた点", height=80, key=f"t_advc_{b}_{i}")
                                        parent_msg = st.text_area("👪 保護者へお伝えしたいこと", height=80, key=f"t_p_msg_{b}_{i}")
                                        next_handover = st.text_area("🔄 入塾に向けた課題・特記事項", height=80, key=f"t_next_h_{b}_{i}")

                                        input_data_list.append({
                                            "name": name, "subject": subject, "text_name": text_name_str,
                                            "advanced_p": advanced_p_str, "quiz_records": quiz_records, 
                                            "attendance": attendance, "late_time": late_time, 
                                            "concentration": concentration, "reaction": reaction,
                                            "advice": advice, "parent_msg": parent_msg, "next_handover": next_handover
                                        })

                                        st.divider()
                                        if st.button(f"👤 {name} の体験記録を保存", key=f"t_save_single_{b}_{i}", use_container_width=True):
                                            with st.status("保存中...", expanded=True) as status:
                                                robust_api_call(
                                                    save_trial_lesson_to_spreadsheet,
                                                    date=date, student_name=name, subject=subject, text_name=text_name_str,
                                                    advanced_p=advanced_p_str, quiz_records=quiz_records, 
                                                    teacher_name=teacher_name, class_type=class_type, attendance=attendance,
                                                    class_slot=class_slot, advice=advice, parent_msg=parent_msg,
                                                    next_handover=next_handover, late_time=late_time,        
                                                    concentration=concentration, reaction=reaction            
                                                )
                                                status.update(label="保存完了！", state="complete", expanded=False)
                                            st.success(f"✅ 保存しました！")
                                            st.session_state[f"t_saved_flag_{b}_{i}"] = True
                                            st.session_state[f"t_saved_name_{b}_{i}"] = name
                                            single_save_triggered = (b, i, name)

            st.divider()
            if len(input_data_list) == num_students:
                actual_attendees = sum(1 for data in input_data_list if "欠席" not in data.get("attendance", ""))
                actual_class_type = f"1:{actual_attendees}" if actual_attendees > 0 else class_type

                if st.button(f"🚀 コマ {b+1} の全員の記録をまとめて保存する", type="primary", key=f"t_save_all_{b}", use_container_width=True):
                    with st.status("データを保存中...", expanded=True) as status:
                        for data in input_data_list:
                            if "欠席" in data.get("attendance", ""):
                                continue
                            robust_api_call(
                                save_trial_lesson_to_spreadsheet,
                                date=date, student_name=data["name"], subject=data["subject"], text_name=data["text_name"],
                                advanced_p=data["advanced_p"], quiz_records=data.get("quiz_records", []), 
                                teacher_name=teacher_name, class_type=actual_class_type, attendance=data["attendance"],
                                class_slot=class_slot, advice=data["advice"], parent_msg=data["parent_msg"],
                                next_handover=data["next_handover"], late_time=data["late_time"],        
                                concentration=data["concentration"], reaction=data["reaction"]            
                            )
                        status.update(label="保存完了！", state="complete", expanded=False)
                    st.success(f"✅ 全員の記録を保存しました！")
                    all_save_triggered = (b, num_students)

            # 🌟 全員個別保存時のリセット発動
            saved_count = sum(1 for idx in range(num_students) if st.session_state.get(f"t_saved_flag_{b}_{idx}", False))
            if saved_count == num_students and num_students > 0 and not all_save_triggered:
                st.success("🎉 全員の入力が完了しました！画面をリセットします...")
                all_save_triggered = (b, num_students)


    # ==========================================
    # 🧹 お掃除処理
    # ==========================================
    if all_save_triggered:
        b_idx, students_count = all_save_triggered
        for k in ["t_class_date", "t_sb_teacher", "t_class_type", "t_sb_class_slot"]:
            if f"{k}_{b_idx}" in st.session_state:
                del st.session_state[f"{k}_{b_idx}"]
        for i_idx in range(students_count):
            for key in list(st.session_state.keys()):
                if key.startswith(f"t_") and f"_{b_idx}_{i_idx}" in key:
                    del st.session_state[key]
        st.cache_data.clear()
        time.sleep(1.5)
        st.rerun()

    elif single_save_triggered:
        b_idx, i_idx, saved_name = single_save_triggered
        for key in list(st.session_state.keys()):
            if key.startswith(f"t_") and f"_{b_idx}_{i_idx}" in key and not key.startswith("t_saved_"):
                del st.session_state[key]
        st.cache_data.clear()
        time.sleep(1.5)
        st.rerun()