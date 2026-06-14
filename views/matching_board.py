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
    # 2. 自動作成する週の選択
    # ------------------------------------------
    st.subheader("📅 スケジュール作成範囲の選択")
    today = datetime.date.today()
    start_of_week = today - datetime.timedelta(days=today.weekday()) 
    
    week_options = []
    for i in range(-2, 9): 
        w_start = start_of_week + datetime.timedelta(weeks=i)
        w_end = w_start + datetime.timedelta(days=6)
        label = f"{w_start.strftime('%Y/%m/%d')} (月) 〜 {w_end.strftime('%m/%d')} (日)"
        week_options.append((w_start, label))
        
    selected_week_idx = st.selectbox(
        "自動コマ組みを実行する週を選んでください", 
        range(len(week_options)), 
        index=2, # デフォルトは「今週」
        format_func=lambda x: week_options[x][1]
    )
    target_start_date = week_options[selected_week_idx][0]

    st.divider()

    # ------------------------------------------
    # 3. 自動コマ組みアルゴリズム実行
    # ------------------------------------------
    if st.button("✨ この週の授業予定表を自動生成する", type="primary", use_container_width=True):
        with st.spinner("高度なマッチングアルゴリズムを実行中...（数秒かかります）"):
            days_of_week = ["月", "火", "水", "木", "金", "土", "日"]
            slots = ["Aコマ", "Bコマ", "0コマ", "1コマ", "2コマ", "3コマ", "4コマ"]
            
            dates_in_week = [(target_start_date + datetime.timedelta(days=i)).strftime("%Y/%m/%d") for i in range(7)]
            
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

            # ⑤ 自動マッチング実行！
            new_lessons = []
            for d in dates_in_week:
                for s in slots:
                    # その時間に「〇」を出している生徒を探す
                    available_students = []
                    if not s_shifts.empty:
                        day_s_shifts = s_shifts[s_shifts["日付"] == d]
                        for _, row in day_s_shifts.iterrows():
                            s_name = row["生徒名"]
                            if row.get(s) == "〇" and s_name in contract_remains and s_name not in busy_students[d][s]:
                                available_students.append(s_name)
                                
                    # 空いている生徒に対して、条件に合う講師をアサイン
                    for s_name in available_students:
                        if s_name not in contract_remains: continue
                            
                        target_subject = list(contract_remains[s_name].keys())[0] # 残っている科目を1つ選ぶ
                        available_teachers = schedule[d][s]
                        
                        best_teacher = None
                        best_priority = 999
                        
                        for t_name, assigned_students in available_teachers.items():
                            if len(assigned_students) >= 2:
                                continue # 1:2 指導のため、すでに2人いる場合はスキップ
                                
                            skills = teacher_skills.get(t_name, {"priority": 5, "subjects": []})
                            # マスタ未設定の講師はとりあえず全科目OKとみなす
                            can_teach = target_subject in skills["subjects"] if skills["subjects"] else True
                            
                            if can_teach:
                                if skills["priority"] < best_priority:
                                    best_priority = skills["priority"]
                                    best_teacher = t_name
                                    
                        # ぴったり合う講師が見つかったらアサイン！
                        if best_teacher:
                            schedule[d][s][best_teacher].append(f"{s_name}({target_subject[0]})")
                            busy_students[d][s].add(s_name)
                            
                            # 契約残数を減らす
                            contract_remains[s_name][target_subject] -= 1
                            if contract_remains[s_name][target_subject] <= 0:
                                del contract_remains[s_name][target_subject]
                            if not contract_remains[s_name]:
                                del contract_remains[s_name]
                                
                            new_lessons.append({
                                "授業ID": f"SCH-{d.replace('/', '')}-{s}-{s_name}",
                                "日付": d, "コマ名": s, "講師名": best_teacher,
                                "生徒名": s_name, "科目": target_subject, "指導形態": "1:2"
                            })

            # ⑥ PDF形式のマトリクス表（MultiIndex DataFrame）を作成！
            all_teachers = set()
            for d in dates_in_week:
                for s in slots:
                    all_teachers.update(schedule[d][s].keys())
            all_teachers = sorted(list(all_teachers))
            
            display_data = {}
            for t_name in all_teachers:
                display_data[t_name] = {}
                for i, d in enumerate(dates_in_week):
                    day_label = f"{d[5:]}({days_of_week[i]})" # 例: 06/08(月)
                    for s in slots:
                        students = schedule[d][s].get(t_name, [])
                        s_label = s.replace("コマ", "") # 表をスッキリさせるため「コマ」を除外
                        display_data[t_name][(day_label, s_label)] = "\n".join(students) if students else ""

            if display_data:
                df_display = pd.DataFrame.from_dict(display_data, orient='index')
                df_display.index.name = "教師名"
                df_display.reset_index(inplace=True)
                
                # StreamlitでExcelのような階層ヘッダー（MultiIndex）を作る魔法
                multi_cols = [("教師名", "")] + list(df_display.columns)[1:]
                df_display.columns = pd.MultiIndex.from_tuples(multi_cols)
                
                st.session_state["generated_schedule"] = df_display
                st.session_state["new_lessons"] = new_lessons
                st.success("🎉 自動コマ組みが完了しました！下の予定表を確認してください。")
            else:
                st.warning("⚠️ この週に出勤している講師が見つかりませんでした。")

    # ------------------------------------------
    # 4. 生成された予定表の表示と保存
    # ------------------------------------------
    if "generated_schedule" in st.session_state:
        st.subheader("📋 自動生成された授業予定表")
        st.caption("PDFのフォーマットに合わせて、日付とコマごとの担当生徒（科目）を表示しています。")
        
        # 階層型データフレームの表示
        st.dataframe(st.session_state["generated_schedule"], use_container_width=True, hide_index=True)
        
        st.info(f"💡 今回新たに {len(st.session_state['new_lessons'])} 件の授業がマッチングされました。（※空白のセルは生徒が入っていない空き枠です）")
        
        if st.button("💾 この予定表を確定してスプレッドシートに保存", type="primary", use_container_width=True):
            with st.spinner("スプレッドシートへ授業データを保存中..."):
                df_to_save = pd.DataFrame(st.session_state["new_lessons"])
                if not df_to_save.empty:
                    success = robust_api_call(lambda: save_lesson_schedule(df_to_save), fallback_value=False)
                    if success:
                        st.success("✅ 授業予定表を確定保存しました！")
                        st.cache_data.clear()
                        del st.session_state["generated_schedule"]
                        del st.session_state["new_lessons"]
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("❌ 保存に失敗しました。ネットワーク状況を確認してください。")
                else:
                    st.warning("新たに割り当てられた授業がないため、保存をスキップしました。")