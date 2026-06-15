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
    st.write("ボタン一つで、生徒の契約残数と双方のシフト・指導科目を計算し、PDF形式の授業予定表を自動生成します🚀")

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
    # 2. スケジュール作成・確認範囲の選択（共通設定）
    # ------------------------------------------
    st.subheader("📅 表示・作成範囲の選択")
    today = datetime.date.today()
    start_of_week = today - datetime.timedelta(days=today.weekday()) 
    
    week_options = []
    for i in range(-2, 9): 
        w_start = start_of_week + datetime.timedelta(weeks=i)
        w_end = w_start + datetime.timedelta(days=6)
        label = f"{w_start.strftime('%Y/%m/%d')} (月) 〜 {w_end.strftime('%m/%d')} (日)"
        week_options.append((w_start, label))
        
    selected_week_idx = st.selectbox(
        "対象となる週を選んでください（作成も確認もこの週が連動します）", 
        range(len(week_options)), 
        index=2, # デフォルトは「今週」
        format_func=lambda x: week_options[x][1]
    )
    target_start_date = week_options[selected_week_idx][0]

    # タブ共通で使う週の日程・コマ枠の定義
    days_of_week = ["月", "火", "水", "木", "金", "土", "日"]
    slots = ["Aコマ", "Bコマ", "0コマ", "1コマ", "2コマ", "3コマ", "4コマ"]
    dates_in_week = [(target_start_date + datetime.timedelta(days=i)).strftime("%Y/%m/%d") for i in range(7)]

    st.divider()

    # ==========================================================
    # 常時確認タブの導入
    # ==========================================================
    tab_create, tab_view = st.tabs(["✨ 新しい予定表を作成する", "📋 確定済みの予定表を確認する"])

    # ------------------------------------------
    # 【タブ1】 自動コマ組みの実行とプレビュー
    # ------------------------------------------
    with tab_create:
        if st.button("✨ この週の授業予定表を自動生成する", type="primary", use_container_width=True):
            with st.spinner("高度なマッチングアルゴリズムを実行中...（数秒かかります）"):
                
                # ① 対象週のシフト抽出
                t_shifts = df_teacher_shifts[df_teacher_shifts["日付"].isin(dates_in_week)] if not df_teacher_shifts.empty else pd.DataFrame()
                s_shifts = df_student_shifts[df_student_shifts["日付"].isin(dates_in_week)] if not df_student_shifts.empty else pd.DataFrame()
                
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
                
                # ④ スケジュール表の枠組み作成 schedule[日付][コマ][講師] = [生徒1, 生徒2]
                schedule = {d: {s: {} for s in slots} for d in dates_in_week}
                busy_students = {d: {s: set() for s in slots} for d in dates_in_week}
                
                # 講師が「〇」を出している枠を初期化
                if not t_shifts.empty:
                    for _, row in t_shifts.iterrows():
                        d = row["日付"]
                        t_name = row.get("講師名")
                        if not t_name: continue
                        for s in slots:
                            if row.get(s) == "〇":
                                schedule[d][s][t_name] = []
                                
                # すでに確定している既存の授業をブロックとして予定表に反映
                if not df_lessons.empty and "日付" in df_lessons.columns:
                    for _, row in df_lessons.iterrows():
                        d = row.get("日付")
                        s = row.get("コマ名")
                        t_name = row.get("講師名")
                        s_name = row.get("生徒名")
                        subj = row.get("科目", "")
                        
                        if d in dates_in_week and d in schedule and s in schedule[d]:
                            if t_name not in schedule[d][s]:
                                schedule[d][s][t_name] = []
                            schedule[d][s][t_name].append(f"{s_name}({subj[0] if subj else '済'})")
                            busy_students[d][s].add(s_name)

                # ⑤ 自動マッチング実行！ (1:2 優先、やむを得ない場合は 1:3 許容)
                new_lessons = []
                for d in dates_in_week:
                    for s in slots:
                        available_students = []
                        if not s_shifts.empty:
                            day_s_shifts = s_shifts[s_shifts["日付"] == d]
                            for _, row in day_s_shifts.iterrows():
                                s_name = row["生徒名"]
                                if row.get(s) == "〇" and s_name in contract_remains and s_name not in busy_students[d][s]:
                                    available_students.append(s_name)
                                    
                        unassigned_students = available_students.copy()
                        
                        # 🌟 フェーズ1(上限2人) -> フェーズ2(上限3人) の順でアサインを試みる
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
                                        # 💡 平準化ロジック：受け持ち人数が少ない講師を優先し、人数バランスを均等に保つ
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
                                        "生徒名": s_name, "科目": target_subject, "指導形態": "" # 後で計算
                                    })
                                    unassigned_students.remove(s_name)

                # 🌟 全てのマッチングが終わった後、各レッスンの「指導形態(1:X)」を確定させる
                for lesson in new_lessons:
                    d_val = lesson["日付"]
                    s_val = lesson["コマ名"]
                    t_val = lesson["講師名"]
                    # 既存の生徒と新規の生徒を合わせた最終的な人数をカウント
                    total_students = len(schedule[d_val][s_val][t_val])
                    lesson["指導形態"] = f"1:{total_students}"

                # ⑥ プレビュー用マトリクス表の作成
                all_teachers = set()
                for d in dates_in_week:
                    for s in slots:
                        all_teachers.update(schedule[d][s].keys())
                all_teachers = sorted(list(all_teachers))
                
                display_data = {}
                for t_name in all_teachers:
                    display_data[t_name] = {}
                    for i, d in enumerate(dates_in_week):
                        day_label = f"{d[5:]}({days_of_week[i]})"
                        for s in slots:
                            students = schedule[d][s].get(t_name, [])
                            s_label = s.replace("コマ", "")
                            display_data[t_name][(day_label, s_label)] = "\n".join(students) if students else ""

                if display_data:
                    df_display = pd.DataFrame.from_dict(display_data, orient='index')
                    df_display.index.name = "教師名"
                    df_display.reset_index(inplace=True)
                    
                    multi_cols = [("教師名", "")] + list(df_display.columns)[1:]
                    df_display.columns = pd.MultiIndex.from_tuples(multi_cols)
                    
                    st.session_state["generated_schedule"] = df_display
                    st.session_state["new_lessons"] = new_lessons
                    st.success("🎉 自動コマ組みが完了しました！下の予定表を確認してください。")
                else:
                    st.warning("⚠️ この週に出勤している講師が見つかりませんでした。")

        # --- プレビュー表示と保存処理 ---
        if "generated_schedule" in st.session_state:
            st.subheader("📋 【下書き】自動生成された授業予定表")
            st.caption("※まだ保存されていません。内容を確認して、下の確定ボタンを押してください。")
            st.dataframe(st.session_state["generated_schedule"], use_container_width=True, hide_index=True)
            st.info(f"💡 今回新たに {len(st.session_state['new_lessons'])} 件の授業がマッチングされました。")
            
            if st.button("💾 この予定表を確定してスプレッドシートに保存", type="primary", use_container_width=True):
                with st.spinner("スプレッドシートへ授業データを保存中..."):
                    df_to_save = pd.DataFrame(st.session_state["new_lessons"])
                    if not df_to_save.empty:
                        success = robust_api_call(lambda: save_lesson_schedule(df_to_save), fallback_value=False)
                        if success:
                            st.success("✅ 授業予定表を確定保存しました！「確定済みの予定表を確認する」タブでいつでも見られます。")
                            st.cache_data.clear() # キャッシュをクリアして最新データを強制再読込
                            del st.session_state["generated_schedule"]
                            del st.session_state["new_lessons"]
                            time.sleep(1.5)
                            st.rerun()
                        else:
                            st.error("❌ 保存に失敗しました。ネットワーク状況を確認してください。")
                    else:
                        st.warning("新たに割り当てられた授業がないため、保存をスキップしました。")

    # ------------------------------------------
    # 【タブ2】 確定済みデータの常時確認
    # ------------------------------------------
    with tab_view:
        st.subheader(f"📋 確定済みの授業予定表")
        st.caption(f"現在スプレッドシートに本番登録されている **{week_options[selected_week_idx][1]}** の確定スケジュールです。")
        
        if not df_lessons.empty and "日付" in df_lessons.columns:
            # 選択された週のデータだけにフィルタリング
            df_week_lessons = df_lessons[df_lessons["日付"].isin(dates_in_week)]
            
            if not df_week_lessons.empty:
                # 登場する講師を抽出
                view_teachers = sorted(df_week_lessons["講師名"].dropna().unique())
                
                # マトリクス空枠の初期化
                view_matrix = {}
                for t_name in view_teachers:
                    view_matrix[t_name] = {}
                    for i, d in enumerate(dates_in_week):
                        day_label = f"{d[5:]}({days_of_week[i]})"
                        for s in slots:
                            s_label = s.replace("コマ", "")
                            view_matrix[t_name][(day_label, s_label)] = []
                
                # データをマトリクスに詰め込む
                for _, row in df_week_lessons.iterrows():
                    d = row.get("日付")
                    s = row.get("コマ名")
                    t_name = row.get("講師名")
                    s_name = row.get("生徒名")
                    subj = row.get("科目", "")
                    
                    if d in dates_in_week and t_name in view_matrix:
                        i = dates_in_week.index(d)
                        day_label = f"{d[5:]}({days_of_week[i]})"
                        s_label = s.replace("コマ", "")
                        
                        if (day_label, s_label) in view_matrix[t_name]:
                            subj_char = subj[0] if subj else '済'
                            view_matrix[t_name][(day_label, s_label)].append(f"{s_name}({subj_char})")
                
                # 各セルの配列を改行テキストに変換
                display_view_data = {}
                for t_name in view_teachers:
                    display_view_data[t_name] = {}
                    for i, d in enumerate(dates_in_week):
                        day_label = f"{d[5:]}({days_of_week[i]})"
                        for s in slots:
                            s_label = s.replace("コマ", "")
                            students_list = view_matrix[t_name][(day_label, s_label)]
                            display_view_data[t_name][(day_label, s_label)] = "\n".join(students_list) if students_list else ""
                
                # DataFrame化して階層ヘッダーを設定
                df_view_display = pd.DataFrame.from_dict(display_view_data, orient='index')
                df_view_display.index.name = "教師名"
                df_view_display.reset_index(inplace=True)
                
                multi_cols_view = [("教師名", "")] + list(df_view_display.columns)[1:]
                df_view_display.columns = pd.MultiIndex.from_tuples(multi_cols_view)
                
                # 画面に常時表示！
                st.dataframe(df_view_display, use_container_width=True, hide_index=True)
            else:
                st.info("ℹ️ この週に確定登録された授業はまだありません。「予定表を作成する」タブから自動生成して保存してください。")
        else:
            st.info("ℹ️ 確定済みの授業スケジュールデータ自体がありません。")