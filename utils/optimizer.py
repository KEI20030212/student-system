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
    # 🚨 【デバッグ用強制ストップ①】そもそも大元のデータが来ているか？
    if df_contracts.empty:
        raise ValueError("【原因判明！】契約データが1件も読み込まれていません！ファイルが空か、読み込みに失敗しています。")
    if not dates_in_scope:
        raise ValueError("【原因判明！】カレンダーの日付が指定されていません！")
    if df_teacher_master.empty:
        raise ValueError("【原因判明！】講師マスターデータが空です！")

    model = cp_model.CpModel()
    
    # -------------------------------------------------------------
    # 1. 必要なリスト・辞書の準備
    # -------------------------------------------------------------
    contract_remains = {}
    for _, row in df_contracts.iterrows():
        c_name = str(row.get("講習名", ""))
        
        # ⚠️ ここが怪しいポイント！is_summerと「夏」の判定
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

    # 🚨 【デバッグ用強制ストップ②】絞り込んだ結果、組むべきデータが残っているか？
    if len(students) == 0:
        raise ValueError("【原因判明！】組むべき生徒のデータが0件です！\n考えられる原因:\n・講習名に『夏』が含まれていない（サマー講習など）\n・すでに全コマ組まれていて残数が0になっている")
    if len(teachers) == 0:
        raise ValueError("【原因判明！】対応できる講師が0人です！")
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

    # 🌟 修正ポイント：スコアを入れるリストを、制約を追加する「前」に作成する
    objective_terms = []

    # -------------------------------------------------------------
    # 3. ハード制約の追加 (絶対に守るルール)
    # -------------------------------------------------------------
    
    # ① 契約残数を上限とする（※ == count から <= count に変更して緩和！）
    for st in students:
        for subj, count in contract_remains[st].items():
            model.Add(
                sum(assign[(d, s, t, st, subj)] 
                    for d in dates_in_scope for s in get_slots_for_date(d, is_summer) for t in teachers) <= count
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

    # 🌟 ⑤ 【修正版】週ごとの授業回数の平準化（ソフト制約化）
    # 週が複数ある場合のみ適用
    if num_weeks > 1:
        for st in students:
            # 生徒の全科目の合計契約残数
            total_remains = sum(contract_remains[st].values())
            
            # 週あたりの理想的な回数（下限と上限）
            min_per_week = total_remains // num_weeks
            max_per_week = math.ceil(total_remains / num_weeks)
            
            for week_idx, week_dates in enumerate(weeks):
                # この週のこの生徒の全授業数
                lessons_in_week = sum(
                    assign[(d, s, t, st, subj)]
                    for d in week_dates
                    for s in get_slots_for_date(d, is_summer)
                    for t in teachers
                    for subj in contract_remains[st].keys()
                )
                
                # --- ここからがソフト制約のロジック ---
                # 理想の回数から「はみ出した数」を格納する変数を作成（最低0）
                diff_max = model.NewIntVar(0, total_remains, f"diff_max_{st}_{week_idx}")
                diff_min = model.NewIntVar(0, total_remains, f"diff_min_{st}_{week_idx}")
                
                # 上限を超えた分を diff_max に入れる
                model.Add(diff_max >= lessons_in_week - max_per_week)
                
                # 下限を下回った分を diff_min に入れる
                model.Add(diff_min >= min_per_week - lessons_in_week)
                
                # 目的関数（スコア）でペナルティを与える（1コマ偏るごとに減点）
                # ※指名講師の加点(+40)とのバランスを見てペナルティの大きさを調整します
                PENALTY_WEIGHT = -20 
                
                objective_terms.append(diff_max * PENALTY_WEIGHT)
                objective_terms.append(diff_min * PENALTY_WEIGHT)

    # ※ここにシフト提出可否（〇、×）による変数制限も追加します。
    # （例: df_teacher_shiftsで '×' またはシフト未提出なら assign == 0 にする処理）

    # -------------------------------------------------------------
    # 4. 目的関数の設定 (ソフト制約：スコアを最大化する)
    # -------------------------------------------------------------
    for d in dates_in_scope:
        for s in get_slots_for_date(d, is_summer):
            for t in teachers:
                for st in students:
                    for subj in contract_remains[st].keys():
                        # 🌟 授業を1つ組むこと自体に「高い基本スコア」を与える（ペナルティに負けないため）
                        score = 1000 
                        
                        # - 指名講師ならさらに加点
                        if t in nomination_map.get(st, set()):
                            score += 400
                            
                        # - 講師の優先度やシフト「◎」の加点などもここに追加
                        
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