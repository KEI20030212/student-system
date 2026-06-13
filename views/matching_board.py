import streamlit as st
import pandas as pd
import datetime
import time
from utils.g_sheets import (
    get_student_master, 
    load_contract_master, 
    load_lesson_schedule, 
    load_all_shifts,
    save_lesson_schedule
)

def render_matching_page():
    st.header("🧩 スマート・コマ組みマッチング")
    st.write("生徒の残り契約コマ数と、講師・生徒の提出シフトをリアルタイムに突き合わせてコマを組みます。")

    # ------------------------------------------
    # 1. 本番データのロード（最強の盾発動🛡️）
    # ------------------------------------------
    with st.spinner("スプレッドシートから最新データを同期中..."):
        df_students = get_student_master()
        df_contracts = load_contract_master()
        df_lessons = load_lesson_schedule()
        df_teacher_shifts = load_all_shifts("講師")
        df_student_shifts = load_all_shifts("生徒")

    if df_students.empty or df_contracts.empty:
        st.warning("⚠️ 生徒情報、または講習契約マスタにデータが登録されていません。先に登録を完了させてください。")
        st.stop()

    # ------------------------------------------
    # 2. 条件選択エリア
    # ------------------------------------------
    col_target, col_week = st.columns(2)
    
    # 生徒マスタからプルダウンの選択肢を動的に生成
    student_options = (df_students['生徒ID'].astype(str) + " - " + df_students['生徒名']).tolist()
    selected_student_raw = col_target.selectbox("👤 対象の生徒を選択", ["-- 選択してください --"] + student_options)
    
    # 対象週の選択（運用に合わせて動的化可能、ここでは夏期の基準週を例示）
    selected_week_start = datetime.date(2026, 8, 3) 
    col_week.selectbox("📅 コマ組みする週を選択", [f"{selected_week_start.strftime('%Y/%m/%d')} (月) 〜 2026/08/09 (日)"])

    if selected_student_raw == "-- 選択してください --":
        st.info("💡 生徒を選択すると、その生徒の契約状況とマッチングボードが起動します。")
        st.stop()

    # 選択された生徒情報の分解
    student_id = selected_student_raw.split(" - ")[0]
    student_name = selected_student_raw.split(" - ")[1]

    # ------------------------------------------
    # 3. 契約コマ数のリアルタイム残数計算ダッシュボード
    # ------------------------------------------
    st.divider()
    st.subheader(f"📊 {student_name} さんの受講・契約進捗")

    # 講習契約マスタからこの生徒の総契約数を計算
    student_contracts = df_contracts[df_contracts["生徒ID"].astype(str) == student_id]
    
    if student_contracts.empty:
        st.error(f"❌ {student_name} さんの講習契約データが見つかりません。「講習契約マスタ登録」画面で契約を追加してください。")
        st.stop()
        
    total_contract_units = int(student_contracts["契約コマ数"].sum())
    
    # 授業予定表シートから、この生徒がすでにスケジュール確定しているコマ数を集計
    if not df_lessons.empty and "生徒名" in df_lessons.columns:
        already_scheduled_units = len(df_lessons[df_lessons["生徒名"] == student_name])
    else:
        already_scheduled_units = 0

    remaining_units = total_contract_units - already_scheduled_units
    progress_pct = min(100, int((already_scheduled_units / total_contract_units) * 100)) if total_contract_units > 0 else 0

    met1, met2, met3 = st.columns(3)
    met1.metric("総契約コマ数", f"{total_contract_units} コマ")
    met2.metric("スケジュール確定済", f"{already_scheduled_units} コマ")
    met3.metric("未手配（残り）", f"{remaining_units} コマ", delta=f"-{remaining_units}" if remaining_units > 0 else "完了！", delta_color="inverse")
    st.progress(progress_pct / 100, text=f"スケジュール消化率: {progress_pct}%")

    # ------------------------------------------
    # 4. マッチング・ボード（生徒シフトに基づく自動ブロックUI）
    # ------------------------------------------
    st.divider()
    st.subheader("🗓️ マッチング・ボード")
    st.caption("生徒が「〇」を出しているコマのみ編集可能です。「×」のコマは自動でブロックされます。")
    
    # 該当生徒の提出シフトを抽出
    this_student_shift = df_student_shifts[df_student_shifts["生徒名"] == student_name]
    
    if this_student_shift.empty:
        st.warning(f"⚠️ {student_name} さんのシフトデータがスプレッドシートに見つかりません。シフトを入力してください。")
        st.stop()

    slots = ["Aコマ", "Bコマ", "0コマ", "1コマ", "2コマ", "3コマ", "4コマ"]
    days_of_week = ["月", "火", "水", "木", "金", "土", "日"]
    
    # 1週間分（7日間）のマトリクス行を動的に生成
    init_data = []
    for i in range(7):
        current_date = selected_week_start + datetime.timedelta(days=i)
        date_str = current_date.strftime("%Y/%m/%d")
        
        # スプレッドシートのシフト行から該当日のデータを取得
        day_shift = this_student_shift[this_student_shift["日付"] == date_str]
        
        row_dict = {"日付": date_str, "曜日": days_of_week[i]}
        for slot in slots:
            if not day_shift.empty and day_shift.iloc[0][slot] == "〇":
                row_dict[slot] = ""  # 生徒が〇なら空欄（講師を選択できる状態にする）
            else:
                row_dict[slot] = "⛔ 生徒NG"  # 生徒が×、または未提出なら強制ブロック
                
        init_data.append(row_dict)
        
    df_matching_board = pd.DataFrame(init_data)

    # プルダウンに表示する全講師のリストをシフトデータから動的に抽出
    all_teachers = [""] + df_teacher_shifts["講師名"].unique().tolist() if not df_teacher_shifts.empty else [""]

    # カラム設定
    column_config = {
        "日付": st.column_config.TextColumn("📅 日付", disabled=True),
        "曜日": st.column_config.TextColumn("📆 曜日", disabled=True),
    }
    for slot in slots:
        column_config[slot] = st.column_config.SelectboxColumn(slot, options=all_teachers, width="medium")

    # エクセルライクなデータエディタの描画
    edited_df = st.data_editor(
        df_matching_board,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        key="matching_editor"
    )

    # ------------------------------------------
    # 5. 保存処理 ＆ 講師の出勤バリデーション（安全装置）
    # ------------------------------------------
    if st.button("💾 このスケジュールで確定して授業予定表に書き込む", type="primary", use_container_width=True):
        new_lessons_list = []
        errors = []
        
        # 画面上の変更内容を1セルずつ走査
        for index, row in edited_df.iterrows():
            date_str = row["日付"]
            for slot in slots:
                val = row[slot]
                
                # 講師が選択されており、かつ生徒NG枠でない場合
                if val and val != "⛔ 生徒NG":
                    teacher_name = val
                    
                    # 🛡️ 【バリデーション】選択された講師が本当にその日そのコマに「〇」を出しているか検証
                    t_match = df_teacher_shifts[
                        (df_teacher_shifts["講師名"] == teacher_name) & 
                        (df_teacher_shifts["日付"] == date_str)
                    ]
                    if t_match.empty or t_match.iloc[0][slot] != "〇":
                        errors.append(f"❌ {date_str} {slot}: {teacher_name} 先生はこの時間シフト（出勤希望）を出していません！")
                        continue
                    
                    # 授業IDの自動ユニーク生成
                    class_id = f"SCH-{date_str.replace('/', '')}-{slot}-{student_id}"
                    
                    # 科目は契約マスタの最初の科目を仮アサイン（運用に応じて選択化可能）
                    subj = student_contracts.iloc[0]["科目"] if not student_contracts.empty else "未定"
                    
                    new_lessons_list.append({
                        "授業ID": class_id,
                        "日付": date_str,
                        "コマ名": slot,
                        "講師名": teacher_name,
                        "生徒名": student_name,
                        "科目": subj,
                        "指導形態": "1:2"  # 初期デフォルト値
                    })

        # 1つでもシフト不一致の講師がいれば処理を中断して警告
        if errors:
            for err in errors:
                st.error(err)
            st.stop()
            
        if not new_lessons_list:
            st.warning("⚠️ アサインされた授業がありません。講師を選択してから保存してください。")
            st.stop()

        # スプレッドシートの「データ_授業予定表」シートへ一括追記
        df_new_lessons = pd.DataFrame(new_lessons_list)
        with st.spinner("スプレッドシートへ授業データを保存中..."):
            success = save_lesson_schedule(df_new_lessons)
            if success:
                st.success(f"🎉 正常に {len(df_new_lessons)} コマ分の授業を確定し、予定表に追記しました！")
                st.balloons()
                time.sleep(1.5)
                st.rerun()