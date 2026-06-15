import streamlit as st
import pandas as pd
import datetime
import time

from utils.api_guard import robust_api_call
from utils.g_sheets import (
    get_student_master, 
    load_contract_master, 
    load_lesson_schedule, 
    load_all_shifts,
    save_lesson_schedule,
    load_teacher_master
)

def render_matching_page():
    st.header("🧩 スマート・自動予定表作成")
    st.write("ボタン一つで、生徒の契約残数と双方のシフト・指導科目を計算し、授業予定表を期間指定で自動生成します🚀")

    # ------------------------------------------
    # 1. 本番データのロード
    # ------------------------------------------
    with st.spinner("スプレッドシートから最新データを同期中..."):
        df_contracts = robust_api_call(load_contract_master, fallback_value=pd.DataFrame())
        df_lessons = robust_api_call(load_lesson_schedule, fallback_value=pd.DataFrame())
        df_teacher_shifts = robust_api_call(lambda: load_all_shifts("講師"), fallback_value=pd.DataFrame())
        df_student_shifts = robust_api_call(lambda: load_all_shifts("生徒"), fallback_value=pd.DataFrame())
        df_teacher_master = robust_api_call(load_teacher_master, fallback_value=pd.DataFrame())

    if df_contracts.empty:
        st.warning("⚠️ 講習契約マスタにデータが登録されていません。先に契約を登録してください。")
        st.stop()

    # ------------------------------------------
    # 2. スケジュール作成・確認範囲の選択（カレンダー自由指定化）
    # ------------------------------------------
    st.subheader("📅 表示・作成範囲の選択")
    st.caption("1ヶ月一括や、任意の期間をカレンダーから自由に指定して自動生成・確認ができます。")
    
    col1, col2 = st.columns(2)
    today = datetime.date.today()
    
    # 🗓️ 週指定のセレクトボックスから、自由な期間指定カレンダーに変更
    start_date = col1.date_input("🗓️ 開始日を選択", today)
    end_date = col2.date_input("🗓️ 終了日を選択", today + datetime.timedelta(days=30)) # デフォルトはたっぷり1ヶ月

    if start_date > end_date:
        st.error("⚠️ 開始日は終了日より前の日付を選択してください。")
        st.stop()

    # 指定された全日程の日付リスト（'YYYY/MM/DD'）を動的に生成
    delta = end_date - start_date
    dates_in_scope = [(start_date + datetime.timedelta(days=i)).strftime("%Y/%m/%d") for i in range(delta.days + 1)]

    # 共通定義
    days_of_week_map = ["月", "火", "水", "木", "金", "土", "日"]
    slots = ["Aコマ", "Bコマ", "0コマ", "1コマ", "2コマ", "3コマ", "4コマ"]

    st.divider()

    # ==========================================================
    # タブシステム
    # ==========================================================
    tab_create, tab_view = st.tabs(["✨ 新しい予定表を作成する", "📋 確定済みの予定表を確認する"])

    # ------------------------------------------
    # 【タブ1】 自動コマ組みの実行とプレビュー
    # ------------------------------------------
    with tab_create:
        btn_label = f"✨ {start_date.strftime('%m/%d')} 〜 {end_date.strftime('%m/%d')} の予定表を一括自動生成する"
        if st.button(btn_label, type="primary", use_container_width=True):
            with st.spinner("高度な一括マッチングアルゴリズムを実行中...（数秒かかります）"):
                
                # ① 指定期間全体のシフト抽出
                t_shifts = df_teacher_shifts[df_teacher_shifts["日付"].isin(dates_in_scope)] if not df_teacher_shifts.empty else pd.DataFrame()
                s_shifts = df_student_shifts[df_student_shifts["日付"].isin(dates_in_scope)] if not df_student_shifts.empty else pd.DataFrame()
                
                # ② 生徒ごとの残り契約コマ数（科目別）を計算
                contract_remains = {} 
                for _, row in df_contracts.iterrows():
                    s_name = row["生徒名"]
                    subj = row["科目"]
                    count = int(row["契約コマ数"])
                    
                    # すでに予定表に登録済みのコマ数を引く
                    scheduled = 0
                    if not df_lessons.empty and "生徒名" in df_lessons.columns:
                        scheduled = len(df_lessons[(df_lessons["生徒名"] == s_name) & (df_lessons["科目"] == subj)])
                    
                    remains = count - scheduled
                    if remains > 0:
                        if s_name not in contract_remains:
                            contract_remains[s_name] = {}
                        contract_remains[s_name][subj] = remains

                # ③ 講師の指導可能科目と優先度を準備
                teacher_skills = {}
                if not df_teacher_master.empty:
                    for _, row in df_teacher_master.iterrows():
                        t_name = row["講師名"]
                        priority = int(row["優先度"]) if pd.notna(row.get("優先度")) else 5
                        
                        can_teach = []
                        for subj in ["英語", "数学", "国語", "理科", "社会"]:
                            val = row.get(subj, False)
                            if str(val).upper() == "TRUE" or val is True:
                                can_teach.append(subj)
                        teacher_skills[t_name] = {"priority": priority, "subjects": can_teach}
                
                # ④ スケジュール表の枠組みを全日程分で初期化
                schedule = {d: {s: {} for s in slots} for d in dates_in_scope}
                busy_students = {d: {s: set() for s in slots} for d in dates_in_scope}
                
                # 講師の「〇」シフトを反映
                if not t_shifts.empty:
                    for _, row in t_shifts.iterrows():
                        d = row["日付"]
                        t_name = row.get("講師名")
                        if not t_name or d not in schedule: continue
                        for s in slots:
                            if row.get(s) == "〇":
                                schedule[d][s][t_name] = []
                                
                # すでに確定している既存の授業をブロックとして反映
                if not df_lessons.empty and "日付" in df_lessons.columns:
                    for _, row in df_lessons.iterrows():
                        d = row.get("日付")
                        s = row.get("コマ名")
                        t_name = row.get("講師名")
                        s_name = row.get("生徒名")
                        subj = row.get("科目", "")
                        
                        if d in dates_in_scope and d in schedule and s in schedule[d]:
                            if t_name not in schedule[d][s]:
                                schedule[d][s][t_name] = []
                            schedule[d][s][t_name].append(f"{s_name}({subj[0] if subj else '済'})")
                            busy_students[d][s].add(s_name)

                # ⑤ 自動マッチング実行！ (指定期間すべての日をループ)
                new_lessons = []
                for d in dates_in_scope:
                    for s in slots:
                        available_students = []
                        if not s_shifts.empty:
                            day_s_shifts = s_shifts[s_shifts["日付"] == d]
                            for _, row in day_s_shifts.iterrows():
                                s_name = row["生徒名"]
                                if row.get(s) == "〇" and s_name in contract_remains and s_name not in busy_students[d][s]:
                                    available_students.append(s_name)
                                    
                        unassigned_students = available_students.copy()
                        
                        for max_students in [2, 3]:
                            for s_name in unassigned_students[:]:
                                if s_name not in contract_remains: continue
                                    
                                target_subject = list(contract_remains[s_name].keys())[0]
                                available_teachers = schedule[d][s]
                                
                                best_teacher = None
                                best_score = 9999
                                
                                for t_name, assigned_students in available_teachers.items():
                                    if len(assigned_students) >= max_students:
                                        continue
                                        
                                    skills = teacher_skills.get(t_name, {"priority": 5, "subjects": []})
                                    can_teach = target_subject in skills["subjects"] if skills["subjects"] else True
                                    
                                    if can_teach:
                                        score = skills["priority"] * 10 + len(assigned_students)
                                        if score < best_score:
                                            best_score = score
                                            best_teacher = t_name
                                            
                                if best_teacher:
                                    schedule[d][s][best_teacher].append(f"{s_name}({target_subject[0]})")
                                    busy_students[d][s].add(s_name)
                                    
                                    contract_remains[s_name][target_subject] -= 1
                                    if contract_remains[s_name][target_subject] <= 0:
                                        del contract_remains[s_name][target_subject]
                                    if not contract_remains[s_name]:
                                        del contract_remains[s_name]
                                        
                                    new_lessons.append({
                                        "授業ID": f"SCH-{d.replace('/', '')}-{s}-{s_name}",
                                        "日付": d, "コマ名": s, "講師名": best_teacher,
                                        "生徒名": s_name, "科目": target_subject, "指導形態": ""
                                    })
                                    unassigned_students.remove(s_name)

                # 全てのマッチング終了後、指導形態(1:X)を確定
                for lesson in new_lessons:
                    d_val = lesson["日付"]
                    s_val = lesson["コマ名"]
                    t_val = lesson["講師名"]
                    total_students = len(schedule[d_val][s_val][t_val])
                    lesson["指導形態"] = f"1:{total_students}"

                # 状態をセッションに退避（表示は下のブロックで動的に行います）
                if new_lessons:
                    st.session_state["new_lessons"] = new_lessons
                    st.success(f"🎉 期間内の自動コマ組みが完了しました！下の一覧とボードで確認してください。")
                else:
                    st.warning("⚠️ 指定された期間内で新しく割り当てられる授業が見つかりませんでした。")

        # --- ⚡ プレビュー表示と保存処理（長期間対応版UI） ---
        if "new_lessons" in st.session_state:
            st.subheader("📋 【下書き】自動生成された授業予定表")
            st.caption("※まだ保存されていません。内容を確認して、一番下の確定ボタンを押してください。")
            
            # 👁️ 視認性向上の工夫1: 生成された全データをフラットな表でスッキリ全件見せる
            df_new_flat = pd.DataFrame(st.session_state["new_lessons"])
            st.markdown(f"**🔥 新規マッチング授業一覧（全 {len(df_new_flat)} 件）**")
            st.dataframe(
                df_new_flat[["日付", "コマ名", "講師名", "生徒名", "科目", "指導形態"]], 
                use_container_width=True, 
                hide_index=True
            )
            
            # 👁️ 視認性向上の工夫2: 選択した日ピンポイントのマトリクス板を出す（横幅スッキリ！）
            st.markdown("---")
            st.markdown("#### 🔍 日別スケジュールボードで配置を確認")
            st.caption("指定期間内の特定の日付を選んで、コマ枠の埋まり具合を縦横マトリクスで確認できます。")
            preview_date = st.selectbox("確認したい日付を選択してください", dates_in_scope, key="preview_date_select")
            
            # 既存の確定データと今回の下書きデータを合算してその日の状態を可視化
            df_combined = pd.concat([df_lessons, df_new_flat], ignore_index=True) if not df_lessons.empty else df_new_flat
            df_day = df_combined[df_combined["日付"] == preview_date]
            
            if not df_day.empty:
                day_teachers = sorted(df_day["講師名"].dropna().unique())
                matrix_data = {t: {s: "" for s in slots} for t in day_teachers}
                
                for _, row in df_day.iterrows():
                    t = row["講師名"]
                    s = row["コマ名"]
                    s_name = row["生徒名"]
                    subj = row["科目"]
                    if t in matrix_data and s in matrix_data[t]:
                        subj_char = subj[0] if subj else ""
                        existing_text = matrix_data[t][s]
                        new_text = f"{s_name}({subj_char})"
                        matrix_data[t][s] = f"{existing_text}\n{new_text}".strip() if existing_text else new_text
                        
                df_matrix = pd.DataFrame.from_dict(matrix_data, orient="index")
                df_matrix.index.name = "教師名"
                
                # 安全に曜日を取得して表示（IndexErrorの完全防御）
                dt_obj = datetime.datetime.strptime(preview_date, "%Y/%m/%d")
                st.info(f"📅 **{preview_date} ({days_of_week_map[dt_obj.weekday()]}曜日)** の配置シミュレーション")
                st.dataframe(df_matrix.reset_index(), use_container_width=True, hide_index=True)
            else:
                st.info("選択された日付の授業予定はありません。")

            st.write("")
            if st.button("💾 この予定表をすべて確定してスプレッドシートに保存", type="primary", use_container_width=True):
                with st.spinner("スプレッドシートへ授業データを保存中..."):
                    df_to_save = pd.DataFrame(st.session_state["new_lessons"])
                    if not df_to_save.empty:
                        success = robust_api_call(lambda: save_lesson_schedule(df_to_save), fallback_value=False)
                        if success:
                            st.success("✅ 授業予定表をすべて確定保存しました！")
                            st.cache_data.clear() 
                            del st.session_state["new_lessons"]
                            time.sleep(1.5)
                            st.rerun()
                        else:
                            st.error("❌ 保存に失敗しました。ネットワーク状況を確認してください。")

    # ------------------------------------------
    # 【タブ2】 確定済みデータの常時確認（長期間対応版UI）
    # ------------------------------------------
    with tab_view:
        st.subheader(f"📋 確定済みの授業予定表")
        st.caption(f"現在本番登録されている **{start_date.strftime('%Y/%m/%d')} 〜 {end_date.strftime('%m/%d')}** の確定スケジュールです。")
        
        if not df_lessons.empty and "日付" in df_lessons.columns:
            df_scope_lessons = df_lessons[df_lessons["日付"].isin(dates_in_scope)]
            
            if not df_scope_lessons.empty:
                # 1ヶ月などの長期間でも快適に見られるよう、見たい日をセレクトボックスで切り替え
                view_date = st.selectbox("確認したい日付を選択してください", dates_in_scope, key="view_date_select")
                df_view_day = df_scope_lessons[df_scope_lessons["日付"] == view_date]
                
                if not df_view_day.empty:
                    view_teachers = sorted(df_view_day["講師名"].dropna().unique())
                    view_matrix = {t: {s: "" for s in slots} for t in view_teachers}
                    
                    for _, row in df_view_day.iterrows():
                        t = row["講師名"]
                        s = row["コマ名"]
                        s_name = row["生徒名"]
                        subj = row["科目"]
                        
                        if t in view_matrix and s in view_matrix[t]:
                            subj_char = subj[0] if subj else '済'
                            existing_text = view_matrix[t][s]
                            new_text = f"{s_name}({subj_char})"
                            view_matrix[t][s] = f"{existing_text}\n{new_text}".strip() if existing_text else new_text
                            
                    df_view_matrix = pd.DataFrame.from_dict(view_matrix, orient="index")
                    df_view_matrix.index.name = "教師名"
                    
                    dt_obj = datetime.datetime.strptime(view_date, "%Y/%m/%d")
                    st.success(f"📅 **{view_date} ({days_of_week_map[dt_obj.weekday()]}曜日)** の確定スケジュール")
                    st.dataframe(df_view_matrix.reset_index(), use_container_width=True, hide_index=True)
                else:
                    st.info("選択された日付に確定済みの授業はありません。")
            else:
                st.info("ℹ️ 指定された期間内に確定登録された授業はまだありません。")
        else:
            st.info("ℹ️ 確定済みの授業スケジュールデータ自体がありません。")