import streamlit as st
import datetime
import time
import re

# 🌟 追加：get_all_teacher_names を呼び出す！
from utils.g_sheets import (
    get_all_student_names, 
    get_all_teacher_names,   # 👈 これを追加
    save_to_spreadsheet, 
    get_last_page_from_sheet, 
    update_student_homework_rate,
    save_self_study_record,
    get_last_handover,
    get_last_homework_info,  
    add_new_textbook,        
    get_textbook_master
)
from utils.calc_logic import (
    calculate_hw_rate, 
    calculate_quiz_points, 
    calculate_motivation_rank
)

def render_multi_input_page(textbook_master):
    st.header("📝 授業・自習記録の入力")

    record_type = st.radio("✍️ 記録の種類を選択してください", ["📖 授業", "📝 自習"], horizontal=True)
    st.divider()

    if "cached_student_names" not in st.session_state:
        st.session_state["cached_student_names"] = get_all_student_names()
    student_names = st.session_state["cached_student_names"]

    # 🌟 講師名のリストを取得して記憶しておく
    if "cached_teacher_names" not in st.session_state:
        st.session_state["cached_teacher_names"] = get_all_teacher_names()
    teacher_names = st.session_state["cached_teacher_names"]

    # ==========================================
    # 📖 「授業」が選ばれた時の画面
    # ==========================================
    if record_type == "📖 授業":
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([1.5, 1.5, 1.5, 2])
            date = c1.date_input("授業日", datetime.date.today())
            
            # 🌟 変更①：担当講師をプルダウン（五十音順・絞り込み可能）に変更
            teacher_options = ["-- 選択 --"] + teacher_names
            teacher_name = c2.selectbox("👨‍🏫 担当講師", teacher_options)
            
            class_type = c3.radio("👥 授業形態", ["1:1", "1:2", "1:3"], horizontal=True)
            
            # 🌟 変更①：コマ選択にも「-- 選択 --」を追加
            time_slots = [
                "-- 選択 --",
                "Aコマ目 (9:30~11:00)", "Bコマ目 (11:10~12:40)",
                "0コマ目 (13:10~14:40)", "1コマ目 (15:00~16:30)",
                "2コマ目 (16:40~18:10)", "3コマ目 (18:20~19:50)",
                "4コマ目 (20:00~21:30)"
            ]
            class_slot = c4.selectbox("⏰ 授業コマ", time_slots)

        # 🌟 変更②：講師とコマが両方選ばれていないと、下に進めないようにする！
        if teacher_name == "-- 選択 --" or class_slot == "-- 選択 --":
            st.info("👆 まずは「担当講師」と「授業コマ」を選択してください。選択すると生徒の入力欄が表示されます。")
        else:
            # ▼▼▼ ここから下は、講師とコマが選ばれた時だけ表示される ▼▼▼
            num_students = int(class_type.split(":")[1])
            options = ["-- 選択 --", "🆕 新規登録"] + student_names

            st.divider()
            cols = st.columns(num_students)
            input_data_list = []

            for i in range(num_students):
                with cols[i]:
                    with st.container(border=True):
                        st.markdown(f"### 👤 生徒 {i+1}")
                        name = st.selectbox("生徒名", options, key=f"name_{i}")
                        if name == "🆕 新規登録": name = st.text_input("新しい生徒の名前", key=f"new_name_{i}")

                        if name and name != "-- 選択 --":
                            attendance = st.selectbox("📅 出欠状況", ["出席（通常）", "出席（振替授業を消化）", "欠席（後日振替あり）", "欠席（振替なし）"], key=f"att_{i}")
                            if "欠席" in attendance:
                                st.warning("欠席のため、進捗・テスト入力はスキップされます。")
                                input_data_list.append({
                                    "name": name, "subject": "-", "text_name": "-", "advanced_p": "-", 
                                    "quiz_records": [], "attendance": attendance,
                                    "advice": "-", "parent_msg": "-", "next_handover": "-",
                                    "assigned_p": 0, "completed_p": 0, "motivation_rank": 0, 
                                    "next_hw_text": "-", "next_hw_pages": "-"
                                })
                            else:
                                subject = st.selectbox("科目", ["英語", "数学", "国語", "理科", "社会"], key=f"sub_{i}")
                                
                                cache_key = f"prev_data_{name}_{subject}"
                                if cache_key not in st.session_state:
                                    with st.spinner("☁️ 過去のデータを読み込み中..."):
                                        st.session_state[cache_key] = {
                                            "note": get_last_handover(name, subject),
                                            "hw_info": get_last_homework_info(name, subject),
                                            "page": get_last_page_from_sheet(name)
                                        }
                                
                                cached_data = st.session_state[cache_key]
                                last_note = cached_data["note"]
                                last_hw_text, last_hw_pages = cached_data["hw_info"]
                                last_page = cached_data["page"]

                                st.info(f"💡 **【前回 ({subject}) の引継ぎ事項】**\n\n{last_note}")

                                text_name = st.selectbox("テキスト", list(textbook_master.keys()), key=f"text_{i}")
                                st.divider()

                                assigned_p = 0
                                hw_str = str(last_hw_pages)
                                if "〜" in hw_str or "~" in hw_str: 
                                    nums = [int(n) for n in re.findall(r'\d+', hw_str)]
                                    if len(nums) >= 2:
                                        assigned_p = nums[1] - nums[0] + 1
                                elif hw_str.isdigit():
                                    assigned_p = int(hw_str)

                                st.markdown(f"🚩 **前回の宿題:** {last_hw_text} (範囲: {last_hw_pages} / 計 {assigned_p} P分)")

                                st.write("✅ **実施状況（やってきた範囲）**")
                                col_hw1, col_hw2 = st.columns(2)
                                with col_hw1:
                                    done_start = st.number_input("やってきた 開始P", min_value=0, value=0, key=f"done_start_{i}")
                                with col_hw2:
                                    done_end = st.number_input("やってきた 終了P", min_value=0, value=0, key=f"done_end_{i}")
                                
                                if done_end >= done_start and done_end > 0:
                                    completed_p = done_end - done_start + 1
                                else:
                                    completed_p = 0
                                    
                                st.caption(f"やってきたページ数: 計 {completed_p} P分")

                                current_hw_rate = calculate_hw_rate(assigned_p, completed_p) if assigned_p > 0 else 0.0
                                if current_hw_rate > 100.0:
                                    current_hw_rate = 100.0
                                    
                                if assigned_p > 0:
                                    st.caption(f"📊 宿題履行率: {current_hw_rate:.1f}%")
                                else:
                                    st.caption("📊 宿題履行率: - % (宿題なし)")
                                
                                st.divider()

                                advanced_p = st.text_input("📖 授業でどこまで進んだか", value=f"P.{last_page} 〜 ", placeholder="例：P.45〜47、関係代名詞", key=f"adv_{i}")
                                
                                quiz_done = st.checkbox("💯 小テストを実施した", key=f"q_done_{i}")
                                quiz_records = []
                                current_quiz_pts = 0 
                                
                                if quiz_done:
                                    target_chap = st.number_input("実施した章", min_value=1, value=1, step=1, key=f"q_chap_{i}")
                                    w_nums = st.text_input("ミス問題番号", key=f"w_{i}")
                                    score = 100 if not w_nums else max(0, 100 - (len(w_nums.split(",")) * 10))
                                    quiz_records.append({"unit": target_chap, "score": score})
                                    current_quiz_pts += calculate_quiz_points(score)

                                motivation_rank = calculate_motivation_rank(current_hw_rate, current_quiz_pts)

                                st.divider()
                                st.write("🚀 **次回の宿題指示**")
                                hw_text_options = ["-- 選択 --", "🆕 新規テキスト入力"] + list(get_textbook_master().keys())
                                selected_hw_text = st.selectbox("次回の宿題テキスト", hw_text_options, key=f"hw_text_{i}")

                                if selected_hw_text == "🆕 新規テキスト入力":
                                    new_text_name = st.text_input("新規テキスト名を入力", key=f"new_hw_text_{i}")
                                    if new_text_name:
                                        add_new_textbook(new_text_name)
                                        selected_hw_text = new_text_name

                                st.write("宿題の範囲")
                                n_s_col, n_e_col = st.columns(2)
                                next_start = n_s_col.number_input("次 開始P", min_value=0, value=0, key=f"n_start_{i}")
                                next_end = n_e_col.number_input("次 終了P", min_value=0, value=0, key=f"n_end_{i}")
                                
                                if next_end >= next_start and next_end > 0:
                                    next_hw_pages_str = f"P.{next_start}〜{next_end}"
                                else:
                                    next_hw_pages_str = "-"
                                    
                                st.caption(f"スプレッドシートに保存される範囲: {next_hw_pages_str}")

                                st.divider()
                                advice = st.text_area("🗣️ 授業でのアドバイス（褒めた点など）", height=80, key=f"advc_{i}")
                                parent_msg = st.text_area("👪 保護者への連絡事項", height=80, key=f"p_msg_{i}")
                                next_handover = st.text_area("🔄 次回への引継ぎ事項", height=80, key=f"next_h_{i}")

                                input_data_list.append({
                                    "name": name, "subject": subject, "text_name": text_name,
                                    "advanced_p": advanced_p, "quiz_records": quiz_records, 
                                    "attendance": attendance,
                                    "advice": advice, "parent_msg": parent_msg, "next_handover": next_handover,
                                    "assigned_p": assigned_p, "completed_p": completed_p,
                                    "motivation_rank": motivation_rank, 
                                    "next_hw_text": selected_hw_text, 
                                    "next_hw_pages": next_hw_pages_str
                                })

            st.divider()
            if len(input_data_list) == num_students:
                if st.button("🚀 全員の記録をまとめて保存する", type="primary", use_container_width=True):
                    for data in input_data_list:
                        save_to_spreadsheet(
                            name=data["name"], 
                            subject=data["subject"], 
                            text_name=data["text_name"], 
                            advanced_p=data["advanced_p"], 
                            quiz_records=data["quiz_records"], 
                            date=date, 
                            teacher_name=teacher_name, 
                            class_type=class_type, 
                            attendance=data["attendance"],
                            class_slot=class_slot, 
                            advice=data["advice"], 
                            parent_msg=data["parent_msg"], 
                            next_handover=data["next_handover"],
                            assigned_p=data["assigned_p"],
                            completed_p=data["completed_p"],
                            motivation_rank=data["motivation_rank"],
                            next_hw_text=data["next_hw_text"],
                            next_hw_pages=data["next_hw_pages"]
                        )
                        
                        update_student_homework_rate(data["name"])
                        time.sleep(1) # サーバー負荷軽減

                    # 🌟 変更③：保存完了メッセージの後、2秒待ってから画面をリセットする！
                    st.success(f"✅ {num_students}名全員の記録を保存し、カルテの「やる気」データを自動更新しました！")
                    
                    for key in list(st.session_state.keys()):
                        if key.startswith("prev_data_"):
                            del st.session_state[key]
                            
                    time.sleep(2) # 2秒待機
                    st.rerun()    # 🔄 画面をリロードして初期状態（選択前に戻る）にする！

    # ==========================================
    # 📝 「自習」が選ばれた時の画面
    # ==========================================
    elif record_type == "📝 自習":
        st.subheader("📝 自習記録の入力")
        options = ["-- 選択 --"] + student_names 

        name = st.selectbox("👤 生徒名", options)

        c1, c2, c3, c4 = st.columns(4)
        date = c1.date_input("📅 自習日", datetime.date.today())
        start_time = c2.time_input("⏰ 開始時間", datetime.time(17, 0))
        end_time = c3.time_input("⏰ 終了時間", datetime.time(19, 0))
        break_time = c4.number_input("☕ 休憩時間（分）", min_value=0, value=0, step=5)

        if name != "-- 選択 --":
            start_dt = datetime.datetime.combine(date, start_time)
            end_dt = datetime.datetime.combine(date, end_time)
            if end_dt <= start_dt:
                end_dt += datetime.timedelta(days=1)

            total_minutes = int((end_dt - start_dt).total_seconds() / 60)
            actual_minutes = total_minutes - break_time

            st.info(f"⏱️ 実質自習時間: **{actual_minutes} 分** （合計 {total_minutes}分 - 休憩 {break_time}分）")

            if st.button("🚀 自習記録を保存する", type="primary"):
                if actual_minutes <= 0:
                    st.error("🚨 時間が正しくありません")
                else:
                    success, error_msg = save_self_study_record(
                        date, name, start_time.strftime("%H:%M"), 
                        end_time.strftime("%H:%M"), break_time, actual_minutes
                    )
                    if success:
                        st.success(f"✅ {name}さんの自習記録（{actual_minutes}分）をスプレッドシートに保存しました！")
                        # 自習画面も保存後にリセットさせたい場合は追加
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(f"🚨 保存に失敗しました！原因: {error_msg}")