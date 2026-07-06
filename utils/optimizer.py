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
    # 2. 変数の定義
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

    # ② 生徒の重複禁止
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
    # 4. ソルバーの実行（制限時間を15秒に設定）
    # -------------------------------------------------------------
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 15.0 
    
    status = solver.Solve(model)

    # -------------------------------------------------------------
    # 5. 結果の判定と【強制エラーによる画面出力】
    # -------------------------------------------------------------
    status_dict = {
        cp_model.OPTIMAL: "OPTIMAL（最適な組み合わせが完成しました！）",
        cp_model.FEASIBLE: "FEASIBLE（条件を満たす組み合わせが完成しました！）",
        cp_model.INFEASIBLE: "INFEASIBLE（物理的に不可能な矛盾した条件があります！）",
        cp_model.UNKNOWN: "UNKNOWN（組み合わせが複雑すぎて時間切れ、または解がありません）"
    }
    
    status_text = status_dict.get(status, f"未知のステータス ({status})")
    
    # 計算された総コマ数をカウント
    total_scheduled_units = 0
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        for d in dates_in_scope:
            for s in get_slots_for_date(d, is_summer):
                for t in teachers:
                    for st_name in students:
                        for subj in contract_remains[st_name].keys():
                            if solver.Value(assign[(d, s, t, st_name, subj)]) == 1:
                                total_scheduled_units += 1

    # 総契約コマ数と最大キャパの計算
    total_contracts = sum(sum(contract_remains[st_name].values()) for st_name in students)
    total_slots_count = sum(len(get_slots_for_date(d, is_summer)) for d in dates_in_scope)
    max_capacity = total_slots_count * len(teachers) * 3

    # 画面に強制表示するためのエラー文
    debug_result = (
        f"📊 【AI計算結果のデバッグ情報】\n\n"
        f"▼ AIの計算ステータス:\n"
        f"  ⇒ {status_text}\n\n"
        f"▼ 現在のデータ状況:\n"
        f"  ・選択された総コマ枠数: {total_slots_count}枠 (35日分)\n"
        f"  ・登録された講師の人数: {len(teachers)}人\n"
        f"  ・生徒全員の総契約コマ数: {total_contracts}コマ\n"
        f"  ・この講師数で配置できる最大キャパ (1:3計算): {max_capacity}コマ分\n\n"
        f"▼ 原因の解説:\n"
    )
    
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        debug_result += f"  🎉 AIはスケジュールを正常に組み立てられました！（合計 {total_scheduled_units} コマ）\n  アルゴリズムは正常です。このデバッグコードを外せば画面に結果が反映されます。"
    elif status == cp_model.INFEASIBLE:
        debug_result += (
            f"  🚨 条件のどこかに「絶対に不可能な要求」が混ざっています。\n"
            f"  【チェックポイント】\n"
            f"  1. 1人の生徒の契約コマ数（例: 英語10コマ＋数学15コマ＋国語10コマ＝計35コマ）が、選択した日数（35日）と同じ、あるいはそれ以上になっていませんか？\n"
            f"     （生徒は1日1コマしか受けられない制約があるため、35日で35コマ以上を消化しようとすると、他の予定や講師の都合で1日でもズレた瞬間に破綻します）\n"
            f"  2. 特定の教科を教えられる講師が、NG講師リスト等によって0人になっていませんか？"
        )
    elif status == cp_model.UNKNOWN:
        debug_result += f"  ⏳ 15秒の制限時間内に解が見つかりませんでした。制約が複雑すぎるか、解が存在しない可能性があります。"
        
    raise ValueError(debug_result)