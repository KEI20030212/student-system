import streamlit as st
import datetime

# さっき作った裏方部隊から、必要な関数を呼び出します（自習用も追加！）
from utils.g_sheets import (
    get_all_student_names, 
    save_to_spreadsheet, 
    get_last_page_from_sheet, 
    update_student_homework_rate,
    save_self_study_record  # 👈 これを追加！
)

def render_multi_input_page(textbook_master):
    st.header("📝 授業・自習記録の入力")

    # 👇 ここが新しい魔法のスイッチ！ 👇
    record_type = st.radio("✍️ 記録の種類を選択してください", ["📖 授業", "📝 自習"], horizontal=True)
    st.divider()

    # ==========================================
    # 📖 「授業」が選ばれた時の画面（元の機能そのまま）
    # ==========================================
    if record_type == "📖 授業":
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            date = c1.date_input("授業日", datetime.date.today())
            teacher_name = c2.text_input("👨‍🏫 担当講師名", placeholder="例：山田先生")
            class_type = c3.radio("👥 授業形態", ["1:1", "1:2", "1:3"], horizontal=True)

        num_students = int(class_type.split(":")[1])
        student_names = get_all_student_names()
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
                                "name": name, "subject": "-", "text_name": "-", "advanced_p": 0, 
                                "quiz_records": [], "hw_status": "-", "attendance": attendance
                            })
                        else:
                            subject = st.selectbox("科目", ["英語", "数学", "国語", "理科", "社会"], key=f"sub_{i}")
                            text_name = st.selectbox("テキスト", list(textbook_master.keys()), key=f"text_{i}")
                            st.divider()
                            hw_status = st.radio("🏠 宿題", ["やってきた", "やってない", "なし"], horizontal=True, key=f"hw_{i}")
                            last_page = get_last_page_from_sheet(name)
                            advanced_p = st.number_input("📖 何ページまで進んだ？", min_value=last_page, value=last_page, key=f"adv_{i}")
                            quiz_done = st.checkbox("💯 小テストを実施した", key=f"q_done_{i}")
                            quiz_records = []
                            if quiz_done:
                                target_chap = st.number_input("実施した章", min_value=1, value=1, step=1, key=f"q_chap_{i}")
                                w_nums = st.text_input("ミス問題番号", key=f"w_{i}")
                                score = 100 if not w_nums else max(0, 100 - (len(w_nums.split(",")) * 10))
                                quiz_records.append({"unit": target_chap, "score": score})

                            input_data_list.append({
                                "name": name, "subject": subject, "text_name": text_name,
                                "advanced_p": advanced_p, "quiz_records": quiz_records, 
                                "hw_status": hw_status, "attendance": attendance
                            })

        st.divider()
        if len(input_data_list) == num_students:
            if st.button("🚀 全員の記録をまとめて保存する", type="primary", use_container_width=True):
                for data in input_data_list:
                    save_to_spreadsheet(
                        data["name"], data["subject"], data["text_name"], 
                        data["advanced_p"], data["quiz_records"], 
                        date, data["hw_status"], teacher_name, class_type, data["attendance"]
                    )
                    update_student_homework_rate(data["name"])
                    
                st.success(f"✅ {num_students}名全員の記録を保存し、カルテの「やる気」データを自動更新しました！")

    # ==========================================
    # 📝 「自習」が選ばれた時の新しい画面！
    # ==========================================
    elif record_type == "📝 自習":
        st.subheader("📝 自習記録の入力")
        student_names = get_all_student_names()
        options = ["-- 選択 --"] + student_names

        # 自習用の入力フォーム
        name = st.selectbox("👤 生徒名", options)

        c1, c2, c3, c4 = st.columns(4)
        date = c1.date_input("📅 自習日", datetime.date.today())
        start_time = c2.time_input("⏰ 開始時間", datetime.time(17, 0))  # 初期値 17:00
        end_time = c3.time_input("⏰ 終了時間", datetime.time(19, 0))    # 初期値 19:00
        break_time = c4.number_input("☕ 休憩時間（分）", min_value=0, value=0, step=5)

        if name != "-- 選択 --":
            # 自動で自習時間を計算する魔法（日またぎも計算できます！）
            start_dt = datetime.datetime.combine(date, start_time)
            end_dt = datetime.datetime.combine(date, end_time)
            if end_dt <= start_dt:
                end_dt += datetime.timedelta(days=1) # 終了が開始より前なら次の日として計算

            total_minutes = int((end_dt - start_dt).total_seconds() / 60)
            actual_minutes = total_minutes - break_time

            # 計算結果を画面に出す
            st.info(f"⏱️ 実質自習時間: **{actual_minutes} 分** （合計 {total_minutes}分 - 休憩 {break_time}分）")

            if st.button("🚀 自習記録を保存する", type="primary"):
                if actual_minutes <= 0:
                    st.error("🚨 時間が正しくありません（自習時間が0分以下になっています）")
                else:
                    # 時間を「17:00」のような文字にして保存関数に渡す
                    # 👇👇👇 ここから変更 👇👇👇
                    success, error_msg = save_self_study_record(
                        date, 
                        name, 
                        start_time.strftime("%H:%M"), 
                        end_time.strftime("%H:%M"), 
                        break_time, 
                        actual_minutes
                    )
                    
                    if success:
                        st.success(f"✅ {name}さんの自習記録（{actual_minutes}分）をスプレッドシートに保存しました！")
                    else:
                        # 失敗した場合は、赤い画面でエラーの正体を暴く！
                        st.error(f"🚨 保存に失敗しました！原因: {error_msg}")
                    # 👆👆👆 ここまで変更 👆👆👆