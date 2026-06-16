import streamlit as st
import streamlit.components.v1 as components
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
    load_teacher_master,
    load_nominated_teacher_master,
    load_compatibility_ng_master   
)

def generate_weekly_matrix_html(df_source, dates_for_week, slots, days_of_week_map, teacher_branch_map=None, is_print_mode=False):
    """
    1週間分のデータを『縦軸：講師名』『横軸：日付 × コマ名』の横長マトリクスHTMLとして生成する関数。
    ※Streamlitの暴走を防ぐため、改行を一切使わずにHTMLを組み立てます。
    """
    if teacher_branch_map is None:
        teacher_branch_map = {}
        
    if df_source.empty or not dates_for_week:
        return "<p style='color: gray; font-style: italic; padding: 10px;'>この期間の授業予定はありません。</p>"
        
    teachers = sorted(df_source["講師名"].dropna().unique())
    if not teachers:
        return "<p style='color: gray; font-style: italic; padding: 10px;'>配置された講師がいません。</p>"
        
    last_names_count = {}
    for full_name in df_source["生徒名"].dropna().unique():
        parts = str(full_name).strip().split()
        if parts:
            last_name = parts[0]
            last_names_count[last_name] = last_names_count.get(last_name, 0) + 1

    def get_display_name(full_name):
        parts = str(full_name).strip().split()
        if not parts: return ""
        last_name = parts[0]
        if last_names_count.get(last_name, 0) > 1 and len(parts) > 1:
            first_name_initial = parts[1][0]
            return f"{last_name}({first_name_initial})"
        return last_name

    color_map = {
        "国語": "background-color: #C5A059; color: white;",
        "数学": "background-color: #B3E5FC; color: #1A237E;",
        "英語": "background-color: #F8BBD0; color: #880E4F;",
        "理科": "background-color: #C8E6C9; color: #1B5E20;",
        "社会": "background-color: #FFF9C4; color: #F57F17;"
    }
    
    container_class = "print-container" if is_print_mode else "scroll-container"
    
    # 🌟 HTMLをリストで組み立てて最後に1行に結合（マークダウンの誤作動を完全に防ぐ）
    h = []
    h.append(f"<div class='{container_class}'><table class='print-optimized-table'>")
    h.append("<tr>")
    h.append("<th rowspan='2' class='sticky-col header-col'>講師名</th>")
    
    for d in dates_for_week:
        dt_obj = datetime.datetime.strptime(d, "%Y/%m/%d")
        day_str = days_of_week_map[dt_obj.weekday()]
        day_color = "#1565C0" if day_str == "土" else "#C62828" if day_str == "日" else "#333333"
        date_short = d.split('/', 1)[1]
        h.append(f"<th colspan='{len(slots)}' class='date-header' style='color: {day_color};'><span class='date-text'>{date_short}</span> ({day_str})</th>")
    h.append("</tr><tr>")
    
    for d in dates_for_week:
        for s in slots:
            h.append(f"<th class='slot-header'>{s.replace('コマ', '')}</th>")
    h.append("</tr>")
    
    for t in teachers:
        t_branch = teacher_branch_map.get(t, "")
        branch_html = f"<br><span class='branch-badge'>{t_branch}</span>" if t_branch else ""
        h.append(f"<tr><td class='sticky-col name-col'>{t}{branch_html}</td>")
        
        for d in dates_for_week:
            df_date = df_source[(df_source["講師名"] == t) & (df_source["日付"] == d)]
            for s in slots:
                h.append("<td class='data-cell'>")
                df_cell = df_date[df_date["コマ名"] == s]
                if not df_cell.empty:
                    for _, row in df_cell.iterrows():
                        disp_name = get_display_name(row["生徒名"])
                        subj = row["科目"]
                        style = color_map.get(subj, "background-color: #e0e0e0; color: #333;")
                        h.append(f"<div class='student-badge' style='{style}' title='{row['生徒名']} ({subj})'>{disp_name}</div>")
                h.append("</td>")
        h.append("</tr>")
    
    h.append("</table></div>")
    return "".join(h)

def render_matching_page():
    # 🌟 印刷用・スクロール用のCSS設定
    st.markdown("""
    <style>
        .scroll-container { overflow-x: auto; max-width: 100%; border: 1px solid #ddd; border-radius: 8px; margin-bottom: 20px; }
        
        /* 🌟 修正：通常画面では印刷用のコンテナを隠す！ */
        .print-container { display: none; } 
        
        .print-optimized-table { width:100%; border-collapse: collapse; min-width: 1800px; background-color: #ffffff; color: #333333; font-family: sans-serif; font-size: 12px; }
        .print-optimized-table th, .print-optimized-table td { border: 1px solid #444; padding: 4px; text-align: center; }
        .header-col { width: 90px; background-color: #f7f9fa; font-weight: bold; }
        .date-header { background-color: #f7f9fa; font-weight: bold; font-size: 13px; }
        .date-text { font-size: 11px; color: #666; }
        .slot-header { background-color: #fcfcfc; font-size: 11px; font-weight: bold; color: #555; width: 55px; }
        .name-col { font-weight: bold; background-color: #fafafa; font-size: 12px; text-align: left; padding-left: 8px; }
        .branch-badge { font-size: 9px; color: #777; font-weight: normal; background-color:#eee; padding:1px 3px; border-radius:3px; display: inline-block; margin-top: 2px; }
        .data-cell { vertical-align: top; min-width: 55px; background-color: #ffffff; }
        .student-badge { padding: 2px; border-radius: 3px; margin: 1px 0; display: block; font-size: 11px; font-weight: bold; width: 100%; box-sizing: border-box; }
        .scroll-container .sticky-col { position: sticky; left: 0; z-index: 2; box-shadow: 2px 0 5px rgba(0,0,0,0.05); }
        .scroll-container .name-col { z-index: 1; }
        
        @media print {
            @page { size: A4 landscape; margin: 10mm; }
            header, .stSidebar, .stButton, .stTabs > div:first-child, .stSelectbox, .stDateInput, footer { display: none !important; }
            .main .block-container { max-width: 100% !important; padding: 0 !important; margin: 0 !important; }
            
            /* 🌟 印刷のときだけ、印刷用コンテナを表示し、スクロール用を隠す */
            .print-container { display: block !important; width: 100% !important; page-break-after: always; }
            .scroll-container { display: none !important; }
            
            .print-optimized-table { min-width: 100% !important; width: 100% !important; font-size: 10px !important; }
            .print-optimized-table th, .print-optimized-table td { border: 1px solid #000 !important; padding: 2px !important; }
            .sticky-col { position: static !important; box-shadow: none !important; }
            .student-badge, .header-col, .date-header, .slot-header, .name-col { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
            .student-badge { font-size: 9px !important; padding: 1px !important; border: 1px solid rgba(0,0,0,0.2) !important; }
            .header-col { width: 60px !important; }
            .slot-header { width: auto !important; font-size: 9px !important; }
        }
    </style>
    """, unsafe_allow_html=True)

    st.header("🧩 スマート・自動予定表作成")
    st.write("生徒と講師のシフト・指導科目・**所属校舎・指名/NG講師・過去の固定履歴**を考慮して、最適な授業予定表を自動生成します🚀")

    with st.spinner("スプレッドシートから最新データを同期中..."):
        df_student_master = robust_api_call(get_student_master, fallback_value=pd.DataFrame())
        df_contracts = robust_api_call(load_contract_master, fallback_value=pd.DataFrame())
        df_lessons = robust_api_call(load_lesson_schedule, fallback_value=pd.DataFrame())
        df_teacher_shifts = robust_api_call(lambda: load_all_shifts("講師"), fallback_value=pd.DataFrame())
        df_student_shifts = robust_api_call(lambda: load_all_shifts("生徒"), fallback_value=pd.DataFrame())
        df_teacher_master = robust_api_call(load_teacher_master, fallback_value=pd.DataFrame())
        df_nominate = robust_api_call(load_nominated_teacher_master, fallback_value=pd.DataFrame())
        df_ng = robust_api_call(load_compatibility_ng_master, fallback_value=pd.DataFrame())

    if df_contracts.empty:
        st.warning("⚠️ 講習契約マスタにデータが登録されていません。先に契約を登録してください。")
        st.stop()

    student_branch_map = {}
    teacher_branch_map = {}

    if not df_student_master.empty and "生徒名" in df_student_master.columns and "生徒ID" in df_student_master.columns:
        for _, row in df_student_master.iterrows():
            s_name = str(row["生徒名"]).replace(" ", "").replace(" ", "").strip()
            sid = str(row.get("生徒ID", "")).strip().lower()
            if s_name:
                if sid.startswith("t"): student_branch_map[s_name] = "田端"
                elif sid.startswith("h"): student_branch_map[s_name] = "東十条"

    for df_temp in [df_contracts, df_student_shifts]:
        if not df_temp.empty and "生徒ID" in df_temp.columns and "生徒名" in df_temp.columns:
            for _, row in df_temp.iterrows():
                s_name = str(row["生徒名"]).replace(" ", "").replace(" ", "").strip()
                if s_name and s_name not in student_branch_map:
                    sid = str(row.get("生徒ID", "")).strip().lower()
                    if sid.startswith("t"): student_branch_map[s_name] = "田端"
                    elif sid.startswith("h"): student_branch_map[s_name] = "東十条"

    if not df_teacher_master.empty and "講師名" in df_teacher_master.columns:
        for _, row in df_teacher_master.iterrows():
            t_name = str(row["講師名"]).replace(" ", "").replace(" ", "").strip()
            if not t_name: continue
            t_branch = row.get("校舎", "")
            if not t_branch or pd.isna(t_branch):
                t_id = str(row.get("講師ID", "")).strip().lower()
                if t_id.startswith("t"): t_branch = "田端"
                elif t_id.startswith("h"): t_branch = "東十条"
                elif t_id.startswith("b"): t_branch = "両校"
            if pd.notna(t_branch) and t_branch:
                teacher_branch_map[t_name] = t_branch
            
    if not df_teacher_shifts.empty and "講師名" in df_teacher_shifts.columns:
        for _, row in df_teacher_shifts.iterrows():
            t_name_raw = row.get("講師名")
            if pd.isna(t_name_raw): continue
            t_name = str(t_name_raw).replace(" ", "").replace(" ", "").strip()
            e_branch = row.get("抽出校舎")
            t_id = str(row.get("講師ID", "")).strip().lower()
            
            if t_name and t_name not in teacher_branch_map:
                if pd.notna(e_branch) and e_branch: teacher_branch_map[t_name] = e_branch
                elif t_id.startswith("t"): teacher_branch_map[t_name] = "田端"
                elif t_id.startswith("h"): teacher_branch_map[t_name] = "東十条"
                elif t_id.startswith("b"): teacher_branch_map[t_name] = "両校"

    nomination_map = {}
    if not df_nominate.empty and "指名生徒名" in df_nominate.columns and "講師名" in df_nominate.columns:
        for _, row in df_nominate.iterrows():
            sn = str(row["指名生徒名"]).replace(" ", "").replace(" ", "").strip()
            tn = str(row["講師名"]).replace(" ", "").replace(" ", "").strip()
            if sn not in nomination_map: nomination_map[sn] = set()
            nomination_map[sn].add(tn)

    ng_map = {}
    if not df_ng.empty and "NG生徒名" in df_ng.columns and "講師名" in df_ng.columns:
        for _, row in df_ng.iterrows():
            sn = str(row["NG生徒名"]).replace(" ", "").replace(" ", "").strip()
            tn = str(row["講師名"]).replace(" ", "").replace(" ", "").strip()
            if sn not in ng_map: ng_map[sn] = set()
            ng_map[sn].add(tn)

    st.subheader("📅 表示・作成範囲の選択")
    col1, col2 = st.columns(2)
    today = datetime.date.today()
    start_date = col1.date_input("🗓️ 開始日を選択", today)
    end_date = col2.date_input("🗓️ 終了日を選択", today + datetime.timedelta(days=30)) 

    if start_date > end_date:
        st.error("⚠️ 開始日は終了日より前の日付を選択してください。")
        st.stop()

    delta = end_date - start_date
    dates_in_scope = [(start_date + datetime.timedelta(days=i)).strftime("%Y/%m/%d") for i in range(delta.days + 1)]
    days_of_week_map = ["月", "火", "水", "木", "金", "土", "日"]
    slots = ["Aコマ", "Bコマ", "0コマ", "1コマ", "2コマ", "3コマ", "4コマ"]

    st.divider()
    tab_create, tab_view = st.tabs(["✨ 新しい予定表を作成する", "📋 確定済みの予定表を確認する"])

    with tab_create:
        btn_label = f"✨ {start_date.strftime('%m/%d')} 〜 {end_date.strftime('%m/%d')} の予定表を一括自動生成する"
        if st.button(btn_label, type="primary", use_container_width=True):
            with st.spinner("アルゴリズムを実行中...（数秒かかります）"):
                
                t_shifts = df_teacher_shifts[df_teacher_shifts["日付"].isin(dates_in_scope)] if not df_teacher_shifts.empty else pd.DataFrame()
                s_shifts = df_student_shifts[df_student_shifts["日付"].isin(dates_in_scope)] if not df_student_shifts.empty else pd.DataFrame()
                
                # 過去の固定履歴
                history_map = {}
                if not df_lessons.empty and "日付" in df_lessons.columns:
                    df_lessons['DateObj'] = pd.to_datetime(df_lessons['日付'], errors='coerce')
                    df_past = df_lessons[df_lessons['DateObj'].dt.date < start_date]
                    
                    for _, row in df_past.iterrows():
                        d_obj = row['DateObj']
                        if pd.isna(d_obj): continue
                        weekday = d_obj.weekday()
                        s_name = str(row.get("生徒名", "")).replace(" ", "").replace(" ", "").strip()
                        t_name = str(row.get("講師名", "")).replace(" ", "").replace(" ", "").strip()
                        slot = str(row.get("コマ名", ""))
                        subj = str(row.get("科目", ""))
                        
                        if s_name and t_name and slot and subj:
                            if s_name not in history_map: history_map[s_name] = {}
                            if weekday not in history_map[s_name]: history_map[s_name][weekday] = {}
                            if slot not in history_map[s_name][weekday]: history_map[s_name][weekday][slot] = {}
                            if subj not in history_map[s_name][weekday][slot]: history_map[s_name][weekday][slot][subj] = {}
                            history_map[s_name][weekday][slot][subj][t_name] = history_map[s_name][weekday][slot][subj].get(t_name, 0) + 1

                contract_remains = {} 
                for _, row in df_contracts.iterrows():
                    s_name = row["生徒名"]
                    subj = row["科目"]
                    count = int(row["契約コマ数"])
                    scheduled = len(df_lessons[(df_lessons["生徒名"] == s_name) & (df_lessons["科目"] == subj)]) if not df_lessons.empty and "生徒名" in df_lessons.columns else 0
                    remains = count - scheduled
                    if remains > 0:
                        if s_name not in contract_remains: contract_remains[s_name] = {}
                        contract_remains[s_name][subj] = remains

                teacher_skills = {}
                if not df_teacher_master.empty:
                    for _, row in df_teacher_master.iterrows():
                        t_name = row["講師名"]
                        priority = int(row["優先度"]) if pd.notna(row.get("優先度")) else 5
                        can_teach = [subj for subj in ["英語", "数学", "国語", "理科", "社会"] if str(row.get(subj, False)).upper() == "TRUE" or row.get(subj, False) is True]
                        teacher_skills[t_name] = {"priority": priority, "subjects": can_teach}
                
                schedule = {d: {s: {} for s in slots} for d in dates_in_scope}
                busy_students = {d: {s: set() for s in slots} for d in dates_in_scope}
                teacher_slot_branches = {d: {} for d in dates_in_scope}
                student_daily_subjects = {d: {} for d in dates_in_scope} 
                teacher_slot_symbols = {d: {s: {} for s in slots} for d in dates_in_scope}
                
                if not t_shifts.empty:
                    for _, row in t_shifts.iterrows():
                        d = row["日付"]
                        t_name = row.get("講師名")
                        if not t_name or d not in schedule: continue
                        for s in slots:
                            val = row.get(s)
                            if val in ["◎", "〇", "△"]:
                                schedule[d][s][t_name] = []
                                teacher_slot_symbols[d][s][t_name] = val 
                                
                if not df_lessons.empty and "日付" in df_lessons.columns:
                    for _, row in df_lessons.iterrows():
                        d = row.get("日付")
                        s = row.get("コマ名")
                        t_name = row.get("講師名")
                        s_name = row.get("生徒名")
                        subj = row.get("科目", "")
                        
                        if d in dates_in_scope and d in schedule and s in schedule[d]:
                            if t_name not in schedule[d][s]: schedule[d][s][t_name] = []
                            schedule[d][s][t_name].append(f"{s_name}({subj[0] if subj else '済'})")
                            busy_students[d][s].add(s_name)
                            
                            s_name_clean = str(s_name).replace(" ", "").replace(" ", "").strip()
                            existing_s_branch = student_branch_map.get(s_name_clean)
                            if existing_s_branch in ["田端", "東十条"]:
                                if t_name not in teacher_slot_branches[d]: teacher_slot_branches[d][t_name] = {}
                                teacher_slot_branches[d][t_name][s] = existing_s_branch
                            if subj:
                                if s_name not in student_daily_subjects[d]: student_daily_subjects[d][s_name] = {}
                                student_daily_subjects[d][s_name][s] = subj

                new_lessons = []
                for d in dates_in_scope:
                    current_weekday = datetime.datetime.strptime(d, "%Y/%m/%d").weekday() 
                    
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
                                s_name_clean = str(s_name).replace(" ", "").replace(" ", "").strip()
                                
                                valid_subject = None
                                s_idx = slots.index(s)
                                available_subjects = list(contract_remains[s_name].keys())
                                available_subjects.sort(key=lambda x: contract_remains[s_name][x], reverse=True)
                                
                                for subj in available_subjects:
                                    if s_idx >= 2:
                                        prev1, prev2 = slots[s_idx - 1], slots[s_idx - 2]
                                        s_record = student_daily_subjects[d].get(s_name, {})
                                        if s_record.get(prev1) == subj and s_record.get(prev2) == subj: continue 
                                    valid_subject = subj
                                    break
                                
                                if not valid_subject: continue 
                                target_subject = valid_subject
                                
                                past_fixed_teacher = None
                                if s_name_clean in history_map and current_weekday in history_map[s_name_clean] and s in history_map[s_name_clean][current_weekday] and target_subject in history_map[s_name_clean][current_weekday][s]:
                                    teacher_counts = history_map[s_name_clean][current_weekday][s][target_subject]
                                    if teacher_counts:
                                        past_fixed_teacher = max(teacher_counts, key=teacher_counts.get)
                                
                                available_teachers = schedule[d][s]
                                s_branch = student_branch_map.get(s_name_clean, "不明")
                                best_teacher, best_score = None, 9999
                                
                                for t_name, assigned_students in available_teachers.items():
                                    if len(assigned_students) >= max_students: continue
                                        
                                    t_name_clean = str(t_name).replace(" ", "").replace(" ", "").strip()
                                    if t_name_clean in ng_map.get(s_name_clean, set()): continue
                                        
                                    t_branch = teacher_branch_map.get(t_name, "両校")
                                    if s_branch in ["田端", "東十条"] and t_branch in ["田端", "東十条"] and t_branch != s_branch: continue 

                                    branch_conflict = False
                                    for assigned_s in assigned_students:
                                        a_name = assigned_s.split('(')[0].replace(" ", "").replace(" ", "").strip()
                                        a_branch = student_branch_map.get(a_name, "不明")
                                        if s_branch in ["田端", "東十条"] and a_branch in ["田端", "東十条"] and s_branch != a_branch:
                                            branch_conflict = True
                                            break
                                    if branch_conflict: continue 

                                    if s_branch in ["田端", "東十条"]:
                                        t_slots_dict = teacher_slot_branches[d].get(t_name, {})
                                        am_slots, pm_slots = ["Aコマ", "Bコマ"], ["0コマ", "1コマ", "2コマ", "3コマ", "4コマ"]
                                        conflict_rule = False
                                        
                                        if s in am_slots:
                                            if any(t_slots_dict.get(am_s) and t_slots_dict.get(am_s) != s_branch for am_s in am_slots): conflict_rule = True
                                            if s == "Bコマ" and t_slots_dict.get("0コマ") and t_slots_dict.get("0コマ") != s_branch: conflict_rule = True
                                        elif s in pm_slots:
                                            if any(t_slots_dict.get(pm_s) and t_slots_dict.get(pm_s) != s_branch for pm_s in pm_slots): conflict_rule = True
                                            if s == "0コマ" and t_slots_dict.get("Bコマ") and t_slots_dict.get("Bコマ") != s_branch: conflict_rule = True
                                                
                                        if conflict_rule: continue 

                                    skills = teacher_skills.get(t_name, {"priority": 5, "subjects": []})
                                    if target_subject in skills["subjects"] if skills["subjects"] else True:
                                        score = skills["priority"] * 10
                                        slot_symbol = teacher_slot_symbols[d][s].get(t_name, "〇")
                                        
                                        if slot_symbol == "◎": score -= 200  
                                        elif slot_symbol == "△": score += 500  
                                            
                                        if t_name_clean in nomination_map.get(s_name_clean, set()):
                                            score -= 400  
                                            
                                        if t_name_clean == past_fixed_teacher:
                                            score -= 300
                                        
                                        same_subj_count = sum(1 for a in assigned_students if f"({target_subject[0]})" in a)
                                        mixed_subj_count = len(assigned_students) - same_subj_count
                                        
                                        if mixed_subj_count > 0: score += 100 
                                        if same_subj_count > 0: score -= 50  
                                        score += len(assigned_students) * 5 
                                        
                                        if score < best_score:
                                            best_score, best_teacher = score, t_name
                                            
                                if best_teacher:
                                    schedule[d][s][best_teacher].append(f"{s_name}({target_subject[0]})")
                                    busy_students[d][s].add(s_name)
                                    if s_branch in ["田端", "東十条"]:
                                        if best_teacher not in teacher_slot_branches[d]: teacher_slot_branches[d][best_teacher] = {}
                                        teacher_slot_branches[d][best_teacher][s] = s_branch
                                    if s_name not in student_daily_subjects[d]: student_daily_subjects[d][s_name] = {}
                                    student_daily_subjects[d][s_name][s] = target_subject
                                        
                                    contract_remains[s_name][target_subject] -= 1
                                    if contract_remains[s_name][target_subject] <= 0: del contract_remains[s_name][target_subject]
                                    if not contract_remains[s_name]: del contract_remains[s_name]
                                        
                                    new_lessons.append({
                                        "授業ID": f"SCH-{d.replace('/', '')}-{s}-{s_name}",
                                        "日付": d, "コマ名": s, "講師名": best_teacher,
                                        "生徒名": s_name, "科目": target_subject, "指導形態": ""
                                    })
                                    unassigned_students.remove(s_name)

                for lesson in new_lessons:
                    d_val, s_val, t_val = lesson["日付"], lesson["コマ名"], lesson["講師名"]
                    lesson["指導形態"] = f"1:{len(schedule[d_val][s_val][t_val])}"

                if new_lessons:
                    st.session_state["new_lessons"] = new_lessons
                    st.success(f"🎉 期間内の自動コマ組みが完了しました！下の一覧とボードで確認してください。")
                else:
                    st.warning("⚠️ 指定された期間内で新しく割り当てられる授業が見つかりませんでした。")

        if "new_lessons" in st.session_state:
            st.subheader("📋 【下書き】自動生成された授業予定表")
            df_new_flat = pd.DataFrame(st.session_state["new_lessons"])
            st.dataframe(df_new_flat[["日付", "コマ名", "講師名", "生徒名", "科目", "指導形態"]], use_container_width=True, hide_index=True)
            
            weeks = [dates_in_scope[i:i+7] for i in range(0, len(dates_in_scope), 7)]
            tab_labels = [f"📅 {w[0].split('/', 1)[1]} 〜 ({idx+1}週目)" for idx, w in enumerate(weeks[:4])]
            
            if tab_labels:
                preview_tabs = st.tabs(tab_labels)
                df_combined = pd.concat([df_lessons, df_new_flat], ignore_index=True) if not df_lessons.empty else df_new_flat
                for idx, w_dates in enumerate(weeks[:4]):
                    with preview_tabs[idx]:
                        html_code = generate_weekly_matrix_html(df_combined[df_combined["日付"].isin(w_dates)], w_dates, slots, days_of_week_map, teacher_branch_map, is_print_mode=False)
                        st.markdown(html_code, unsafe_allow_html=True)

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
                        else: st.error("❌ 保存に失敗しました。ネットワーク状況を確認してください。")

    # ------------------------------------------
    # 【タブ2】 確定済みデータの常時確認（校舎ごとに表を分離）
    # ------------------------------------------
    with tab_view:
        c_title, c_print = st.columns([0.8, 0.2])
        c_title.subheader(f"📋 確定済みの授業予定表")
        
        # 🌟 Streamlitのセキュリティを突破する魔法のボタン！
        # （隔離エリアから大元の画面に印刷命令を出すため、window.parent.print() にしています）
        with c_print:
            components.html("""
                <button onclick="window.parent.print()" style="padding: 8px 15px; background: #333; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; width: 100%; font-family: sans-serif; font-size: 14px; box-sizing: border-box;">
                    🖨️ A4横で印刷・PDF化
                </button>
            """, height=50)
        
        st.caption(f"現在本番登録されている **{start_date.strftime('%Y/%m/%d')} 〜 {end_date.strftime('%m/%d')}** の確定スケジュールです。")
        st.info("💡 **【印刷時のコツ】** 右上の「🖨️ A4横で印刷・PDF化」ボタンを押し、印刷設定のレイアウトを「横」に、余白を「最小」に設定してください。")
        
        if not df_lessons.empty and "日付" in df_lessons.columns:
            df_scope_lessons = df_lessons[df_lessons["日付"].isin(dates_in_scope)]
            
            if not df_scope_lessons.empty:
                view_weeks = [dates_in_scope[i:i+7] for i in range(0, len(dates_in_scope), 7)]
                view_tab_labels = [f"📅 {w[0].split('/', 1)[1]} 〜 ({idx+1}週目)" for idx, w in enumerate(view_weeks[:4])]
                
                if view_tab_labels:
                    view_tabs = st.tabs(view_tab_labels)
                    for idx, w_dates in enumerate(view_weeks[:4]):
                        with view_tabs[idx]:
                            df_view_week_data = df_scope_lessons[df_scope_lessons["日付"].isin(w_dates)]
                            
                            if not df_view_week_data.empty:
                                df_view_week_data = df_view_week_data.copy()
                                df_view_week_data["校舎"] = df_view_week_data["生徒名"].apply(
                                    lambda x: student_branch_map.get(str(x).replace(" ", "").replace(" ", "").strip(), "不明")
                                )
                                
                                df_tabata = df_view_week_data[df_view_week_data["校舎"] == "田端"]
                                df_higashijujo = df_view_week_data[df_view_week_data["校舎"] == "東十条"]
                                
                                st.markdown("### 🏫 田端校舎")
                                if not df_tabata.empty:
                                    html_scroll = generate_weekly_matrix_html(df_tabata, w_dates, slots, days_of_week_map, teacher_branch_map, is_print_mode=False)
                                    html_print = generate_weekly_matrix_html(df_tabata, w_dates, slots, days_of_week_map, teacher_branch_map, is_print_mode=True)
                                    st.markdown(html_scroll + html_print, unsafe_allow_html=True)
                                else:
                                    st.caption("この週の田端校舎の確定予定はありません。")
                                    
                                st.write("") 
                                
                                st.markdown("### 🏫 東十条校舎")
                                if not df_higashijujo.empty:
                                    html_scroll2 = generate_weekly_matrix_html(df_higashijujo, w_dates, slots, days_of_week_map, teacher_branch_map, is_print_mode=False)
                                    html_print2 = generate_weekly_matrix_html(df_higashijujo, w_dates, slots, days_of_week_map, teacher_branch_map, is_print_mode=True)
                                    st.markdown(html_scroll2 + html_print2, unsafe_allow_html=True)
                                else:
                                    st.caption("この週の東十条校舎の確定予定はありません。")
            else:
                st.info("ℹ️ 指定された期間内に確定登録された授業はまだありません。")
        else:
            st.info("ℹ️ 確定済みの授業スケジュールデータ自体がありません。")