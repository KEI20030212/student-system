import pandas as pd
import datetime
import math
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
    # 契約残数の算出 (メイン側のロジックを踏襲)
    contract_remains = {}
    for _, row in df_contracts.iterrows():
        c_name = str(row.get("講習名", ""))
        if is_summer != ("夏" in c_name): continue
        
        s_name = str(row["生徒名"]).strip()
        subj = str(row["科目"]).strip()
        count = int(row["契約コマ数"])
        
        # 既にdf_lessonsに入っている分の差し引きはここで行う想定
        scheduled = len(df_lessons[(df_lessons["生徒名"] == s_name) & (df_lessons["科目"] == subj)]) if not df_lessons.empty else 0
        remains = count - scheduled
        
        if remains > 0:
            if s_name not in contract_remains:
                contract_remains[s_name] = {}
            contract_remains[s_name][subj] = contract_remains.get(s_name, {}).get(subj, 0) + remains

    students = list(contract_remains.keys())
    teachers = df_teacher_master["講師名"].dropna().unique().tolist() if not df_teacher_master.empty else []
    
    # 🌟 日付を「週ごと」にグルーピング（平準化制約用）
    # datetimeのisocalendar().weekを利用して同じ週の日付をまとめる
    week_groups = {}
    for d in dates_in_scope:
        dt_obj = datetime.datetime.strptime(d, "%Y/%m/%d")
        week_num = dt_obj.isocalendar().week
        if week_num not in week_groups:
            week_groups[week_num] = []
        week_groups[week_num].append(d)
    weeks = list(week_groups.values())
    num_weeks = len(weeks)

    # -------------------------------------------------------------
    # 2. 変数の定義
    # -------------------------------------------------------------
    # assign[d, s, t, st, subj] = 1 なら、日付d, コマs に 講師t が 生徒st に 科目subj を教える
    assign = {}
    for d in dates_in_scope:
        slots = get_slots_for_date(d, is_summer)
        for s in slots:
            for t in teachers:
                for st in students:
                    for subj in contract_remains[st].keys():
                        assign[(d, s, t, st, subj)] = model.NewBoolVar(f"x_{d}_{s}_{t}_{st}_{subj}")

    # -------------------------------------------------------------
    # 3. ハード制約の追加 (絶対に守るルール)
    # -------------------------------------------------------------
    
    # ① 契約残数をぴったり満たす
    for st in students:
        for subj, count in contract_remains[st].items():
            model.Add(
                sum(assign[(d, s, t, st, subj)] 
                    for d in dates_in_scope for s in get_slots_for_date(d, is_summer) for t in teachers) == count
            )

    # ② 生徒の重複禁止（同じコマに2つの授業を受けられない）
    for d in dates_in_scope:
        slots = get_slots_for_date(d, is_summer)
        for s in slots:
            for st in students:
                model.Add(sum(assign[(d, s, t, st, subj)] for t in teachers for subj in contract_remains[st].keys()) <= 1)

    # ③ 講師の定員（1:2 や 1:3の制限）
    MAX_STUDENTS_PER_TEACHER = 3  # 運用に合わせて変更
    for d in dates_in_scope:
        slots = get_slots_for_date(d, is_summer)
        for s in slots:
            for t in teachers:
                model.Add(sum(assign[(d, s, t, st, subj)] for st in students for subj in contract_remains[st].keys()) <= MAX_STUDENTS_PER_TEACHER)

    # ④ NG講師の回避
    for st in students:
        ng_teachers = ng_map.get(st, set())
        for t in ng_teachers:
            if t in teachers:
                for d in dates_in_scope:
                    for s in get_slots_for_date(d, is_summer):
                        for subj in contract_remains[st].keys():
                            model.Add(assign[(d, s, t, st, subj)] == 0)

    # 🌟 ⑤ 【新規追加】週ごとの授業回数の平準化制約
    # 週が複数ある場合のみ適用
    if num_weeks > 1:
        for st in students:
            # 生徒の全科目の合計契約残数
            total_remains = sum(contract_remains[st].values())
            
            # 週あたりの目標回数（下限と上限）
            min_per_week = total_remains // num_weeks
            max_per_week = math.ceil(total_remains / num_weeks)
            
            for week_dates in weeks:
                # この週のこの生徒の全授業数
                lessons_in_week = sum(
                    assign[(d, s, t, st, subj)]
                    for d in week_dates
                    for s in get_slots_for_date(d, is_summer)
                    for t in teachers
                    for subj in contract_remains[st].keys()
                )
                # 週に割り当てられる授業数を平準化（はみ出しを許さない）
                model.Add(lessons_in_week >= min_per_week)
                model.Add(lessons_in_week <= max_per_week)

    # ※ここにシフト提出可否（〇、×）による変数制限も追加します。
    # （例: df_teacher_shiftsで '×' またはシフト未提出なら assign == 0 にする処理）

    # -------------------------------------------------------------
    # 4. 目的関数の設定 (ソフト制約：スコアを最大化する)
    # -------------------------------------------------------------
    objective_terms = []
    for d in dates_in_scope:
        for s in get_slots_for_date(d, is_summer):
            for t in teachers:
                for st in students:
                    for subj in contract_remains[st].keys():
                        score = 0
                        # スコアの例:
                        # - 指名講師なら +40
                        if t in nomination_map.get(st, set()):
                            score += 40
                            
                        # - 講師の優先度やシフト「◎」の加点（データフレームから取得する）等
                        
                        if score > 0:
                            objective_terms.append(assign[(d, s, t, st, subj)] * score)

    if objective_terms:
        model.Maximize(sum(objective_terms))

    # -------------------------------------------------------------
    # 5. ソルバーの実行
    # -------------------------------------------------------------
    solver = cp_model.CpSolver()
    # 探索の制限時間（秒）。複雑なパズルになるため10〜30秒程度設けるのが推奨
    solver.parameters.max_time_in_seconds = 15.0 
    
    status = solver.Solve(model)

    # -------------------------------------------------------------
    # 6. 結果のパース
    # -------------------------------------------------------------
    new_lessons = []
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        for d in dates_in_scope:
            slots = get_slots_for_date(d, is_summer)
            for s in slots:
                for t in teachers:
                    assigned_students = []
                    for st in students:
                        for subj in contract_remains[st].keys():
                            if solver.Value(assign[(d, s, t, st, subj)]) == 1:
                                assigned_students.append((st, subj))
                    
                    # 割り当てがあった場合、形式を整えてnew_lessonsへ
                    if assigned_students:
                        guidance_mode = f"1:{len(assigned_students)}"
                        for (st, subj) in assigned_students:
                            new_lessons.append({
                                "授業ID": f"SCH-{d.replace('/', '')}-{s}-{st}",
                                "日付": d,
                                "コマ名": s,
                                "講師名": t,
                                "生徒名": st,
                                "科目": subj,
                                "指導形態": guidance_mode
                            })
    else:
        # 解が見つからなかった場合（制約が厳しすぎる）
        print("最適解、および許容解が見つかりませんでした。条件を緩和してください。")

    return new_lessons