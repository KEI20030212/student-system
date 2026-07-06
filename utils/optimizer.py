import pandas as pd
import datetime
import math
import streamlit as st_ui  # 🌟 名前被りを避けるため st_ui に変更しました！
from ortools.sat.python import cp_model

def get_slots_for_date(date_str, is_summer_mode):
    """メイン側と同じコマ判定ロジック"""
    if is_summer_mode:
        return ["Aコマ", "Bコマ", "0コマ", "1コマ", "2コマ", "3コマ", "4コマ"]
    else:
        dt_obj = datetime.datetime.strptime(date_str, "%Y/%m/%d")
        if dt_obj.weekday() < 5:  # 月〜金
            return ["2コマ", "3コマ", "4コマ"]
        else:  # 土日
            return ["0コマ", "1コマ", "2コマ", "3コマ", "4コマ"]

def run_optimization_engine(
    dates_in_scope, 
    is_summer, 
    df_contracts, 
    df_teacher_shifts, 
    df_student_shifts, 
    df_lessons, 
    df_teacher_master,
    student_branch_map, 
    teacher_branch_map, 
    nomination_map, 
    ng_map
):
    model = cp_model.CpModel()
    
    # -------------------------------------------------------------
    # 1. 必要なリスト・辞書の準備
    # -------------------------------------------------------------
    contract_remains = {}
    for _, row in df_contracts.iterrows():
        c_name = str(row.get("講習名", ""))
        if is_summer != ("夏" in c_name): continue
        
        s_name = str(row["生徒名"]).strip()
        subj = str(row["科目"]).strip()
        count = int(row["契約コマ数"])
        
        scheduled = len(df_lessons[(df_lessons["生徒名"] == s_name) & (df_lessons["科目"] == subj)]) if not df_lessons.empty else 0
        remains = count - scheduled
        
        if remains > 0:
            if s_name not in contract_remains:
                contract_remains[s_name] = {}
            contract_remains[s_name][subj] = contract_remains.get(s_name, {}).get(subj, 0) + remains

    students = list(contract_remains.keys())
    teachers = df_teacher_master["講師名"].dropna().unique().tolist() if not df_teacher_master.empty else []

    # -------------------------------------------------------------
    # 2. 変数の定義（※ st を st_name に修正）
    # -------------------------------------------------------------
    assign = {}
    for d in dates_in_scope:
        slots = get_slots_for_date(d, is_summer)
        for s in slots:
            for t in teachers:
                for st_name in students:
                    for subj in contract_remains[st_name].keys():
                        assign[(d, s, t, st_name, subj)] = model.NewBoolVar(f"x_{d}_{s}_{t}_{st_name}_{subj}")

    # -------------------------------------------------------------
    # 3. ハード制約の追加 (絶対に守るルール)
    # -------------------------------------------------------------
    # ① 契約残数をぴったり満たす
    for st_name in students:
        for subj, count in contract_remains[st_name].items():
            model.Add(
                sum(assign[(d, s, t, st_name, subj)] 
                    for d in dates_in_scope for s in get_slots_for_date(d, is_summer) for t in teachers) == count
            )

    # ② 生徒の重複禁止（同じコマに2つの授業を受けられない）
    for d in dates_in_scope:
        slots = get_slots_for_date(d, is_summer)
        for s in slots:
            for st_name in students:
                model.Add(sum(assign[(d, s, t, st_name, subj)] for t in teachers for subj in contract_remains[st_name].keys()) <= 1)

    # ③ 講師の定員（1:3の制限）
    MAX_STUDENTS_PER_TEACHER = 3
    for d in dates_in_scope:
        slots = get_slots_for_date(d, is_summer)
        for s in slots:
            for t in teachers:
                model.Add(sum(assign[(d, s, t, st_name, subj)] for st_name in students for subj in contract_remains[st_name].keys()) <= MAX_STUDENTS_PER_TEACHER)

    # ④ NG講師の回避
    for st_name in students:
        ng_teachers = ng_map.get(st_name, set())
        for t in ng_teachers:
            if t in teachers:
                for d in dates_in_scope:
                    for s in get_slots_for_date(d, is_summer):
                        for subj in contract_remains[st_name].keys():
                            model.Add(assign[(d, s, t, st_name, subj)] == 0)

    # -------------------------------------------------------------
    # 4. ソルバーの実行（制限時間を30秒に延長）
    # -------------------------------------------------------------
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0 
    
    # 🌟 実行前に画面でお知らせ (st_ui に修正)
    st_ui.info("🤖 AIがスケジュール計算を開始しました...最大30秒かかります。")
    
    status = solver.Solve(model)

    # -------------------------------------------------------------
    # 5. 結果のパースと画面への結果表示
    # -------------------------------------------------------------
    new_lessons = []
    
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        st_ui.success("✨ スケジュールの作成に成功しました！（AIが条件を満たす組み合わせを発見しました）")
        for d in dates_in_scope:
            slots = get_slots_for_date(d, is_summer)
            for s in slots:
                for t in teachers:
                    assigned_students = []
                    for st_name in students:
                        for subj in contract_remains[st_name].keys():
                            if solver.Value(assign[(d, s, t, st_name, subj)]) == 1:
                                assigned_students.append((st_name, subj))
                    
                    if assigned_students:
                        guidance_mode = f"1:{len(assigned_students)}"
                        for (st_name, subj) in assigned_students:
                            new_lessons.append({
                                "授業ID": f"SCH-{d.replace('/', '')}-{s}-{st_name}",
                                "日付": d,
                                "コマ名": s,
                                "講師名": t,
                                "生徒名": st_name,
                                "科目": subj,
                                "指導形態": guidance_mode
                            })
    elif status == cp_model.INFEASIBLE:
        st_ui.error("🚨 【INFEASIBLE】物理的に不可能な条件が含まれています（例: 講師の枠より契約コマ数が多い等）")
    elif status == cp_model.UNKNOWN:
        st_ui.warning("⚠️ 【UNKNOWN】組み合わせが多すぎて、30秒以内に計算が終わりませんでした（タイムアウト）")
    else:
        st_ui.error(f"❌ 予期せぬエラーステータス: {status}")

    return new_lessons