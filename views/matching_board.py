import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import datetime
import time
import os # 👈 追加
import json # 👈 追加

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

# 作成したHTMLフォルダへのパスを指定してコンポーネントを宣言
_COMPONENT_PATH = os.path.join(os.path.dirname(__file__), "..", "components", "drag_drop_board")
draggable_board_component = components.declare_component(
    "draggable_board",
    path=_COMPONENT_PATH
)

def get_slots_for_date(date_str, is_summer_mode):
    """
    🌟【時間割最適化ロジック】
    期間モードと曜日を判定し、その日に必要なコマの枠組みだけを動的に返す関数
    """
    if is_summer_mode:
        return ["Aコマ", "Bコマ", "0コマ", "1コマ", "2コマ", "3コマ", "4コマ"]
    else:
        dt_obj = datetime.datetime.strptime(date_str, "%Y/%m/%d")
        if dt_obj.weekday() < 5:  # 月〜金 (0=月, 4=金)
            return ["2コマ", "3コマ", "4コマ"]
        else:  # 土曜日・日曜日
            return ["0コマ", "1コマ", "2コマ", "3コマ", "4コマ"]

def generate_weekly_matrix_html(df_source, dates_for_week, days_of_week_map, teacher_branch_map=None, all_branch_teachers=None, is_summer_mode=False, is_print_mode=False):
    """
    1週間分のデータを『縦軸：講師名』『横軸：日付 × コマ名』のマトリクスHTMLとして生成。
    🌟 CSSを徹底強化し、格子のサイズを完全固定＆美化しました。
    """
    if teacher_branch_map is None: teacher_branch_map = {}
    if all_branch_teachers is None: all_branch_teachers = []
        
    active_teachers = set(df_source["講師名"].dropna().unique()) if not df_source.empty else set()
    all_target_teachers = sorted(list(active_teachers.union(set(all_branch_teachers))))
    
    if not all_target_teachers:
        return "<p style='color: gray; font-style: italic; padding: 10px;'>この校舎に所属する講師がいません。</p>"
        
    last_names_count = {}
    if not df_source.empty:
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
            return f"{last_name}({parts[1][0]})"
        return last_name

    color_map = {
        "国語": "background-color: #C5A059; color: white;",
        "数学": "background-color: #B3E5FC; color: #1A237E;",
        "英語": "background-color: #F8BBD0; color: #880E4F;",
        "理科": "background-color: #C8E6C9; color: #1B5E20;",
        "社会": "background-color: #FFF9C4; color: #F57F17;"
    }
    
    container_class = "print-container" if is_print_mode else "scroll-container"
    
    h = []
    h.append(f"<div class='{container_class}'><table class='print-optimized-table'>")
    
    # コマ幅を均等に計算するためのcolgroup設定 (幅のブレを完全に固定化)
    h.append("<colgroup>")
    h.append("<col class='col-teacher-name'>") # 講師名列の固定
    for d in dates_for_week:
        day_slots = get_slots_for_date(d, is_summer_mode)
        for _ in day_slots:
            h.append("<col class='col-slot-width'>") # 各コマ幅の固定
    h.append("</colgroup>")

    # ヘッダー1行目
    h.append("<tr>")
    h.append("<th rowspan='2' class='sticky-col header-col'>講師名</th>")
    for d in dates_for_week:
        dt_obj = datetime.datetime.strptime(d, "%Y/%m/%d")
        day_str = days_of_week_map[dt_obj.weekday()]
        day_color = "#1565C0" if day_str == "土" else "#C62828" if day_str == "日" else "#333333"
        date_short = d.split('/', 1)[1]
        day_slots = get_slots_for_date(d, is_summer_mode)
        h.append(f"<th colspan='{len(day_slots)}' class='date-header' style='color: {day_color};'><span class='date-text'>{date_short}</span> ({day_str})</th>")
    h.append("</tr><tr>")
    
    # ヘッダー2行目
    for d in dates_for_week:
        day_slots = get_slots_for_date(d, is_summer_mode)
        for s in day_slots:
            h.append(f"<th class='slot-header'>{s.replace('コマ', '')}</th>")
    h.append("</tr>")
    
    # データ行
    for t in all_target_teachers:
        t_branch = teacher_branch_map.get(t, "")
        branch_html = f"<br><span class='branch-badge'>{t_branch}</span>" if t_branch else ""
        h.append(f"<tr><td class='sticky-col name-col'>{t}{branch_html}</td>")
        
        for d in dates_for_week:
            df_date = df_source[(df_source["講師名"] == t) & (df_source["日付"] == d)] if not df_source.empty else pd.DataFrame()
            day_slots = get_slots_for_date(d, is_summer_mode)
            for s in day_slots:
                h.append("<td class='data-cell'>")
                df_cell = df_date[df_date["コマ名"] == s] if not df_date.empty else pd.DataFrame()
                if not df_cell.empty:
                    for _, row in df_cell.iterrows():
                        clean_name = str(row["生徒名"]).replace("\n", " ").strip()
                        disp_name = get_display_name(clean_name)
                        subj = row["科目"]
                        style = color_map.get(subj, "background-color: #e0e0e0; color: #333;")
                        # 三点リーダーで溢れを防止しつつ、title属性でホバー時にフルネーム表示
                        h.append(f"<div class='student-badge' style='{style}' title='{row['生徒名']} ({subj})'>{disp_name}</div>")
                h.append("</td>")
        h.append("</tr>")
    
    h.append("</table></div>")
    return "".join(h)

def render_matching_page():
    # 🎨 グローバルCSSの定義（格子のサイズ固定化・美化用）
    st.markdown("""
    <style>
        .scroll-container { overflow-x: auto; max-width: 100%; border: 1px solid #e0e0e0; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
        .print-container { display: none; } 
        
        /* 🚨 格子サイズ固定化のコアロジック */
        .print-optimized-table { 
            table-layout: fixed; /* これで各列の幅を強制固定 */
            width: auto; 
            border-collapse: separate; 
            border-spacing: 0;
            background-color: #ffffff; 
            color: #333333; 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
            font-size: 12px; 
        }
        
        /* カラム幅の厳密な定義 */
        .col-teacher-name { width: 110px; }
        .col-slot-width { width: 75px; }
        
        .print-optimized-table th, .print-optimized-table td { 
            border-right: 1px solid #e2e8f0; 
            border-bottom: 1px solid #e2e8f0; 
            padding: 6px 4px; 
            text-align: center; 
            box-sizing: border-box;
        }
        
        .header-col { background-color: #f8fafc; font-weight: bold; border-bottom: 2px solid #cbd5e1 !important; }
        .date-header { background-color: #f1f5f9; font-weight: bold; font-size: 12px; border-bottom: 1px solid #cbd5e1; }
        .date-text { font-size: 11px; font-weight: normal; }
        .slot-header { background-color: #f8fafc; font-size: 11px; font-weight: bold; color: #64748b; border-bottom: 2px solid #cbd5e1 !important; }
        
        /* 講師名セルの高さを強制固定 */
        .name-col { 
            font-weight: bold; 
            background-color: #f8fafc; 
            font-size: 12px; 
            text-align: left; 
            padding-left: 8px; 
            border-bottom: 1px solid #e2e8f0;
            height: 40px !important; /* 高さを指定 */
            max-height: 40px !important;
            overflow: hidden; /* はみ出たテキストを隠す */
            white-space: nowrap; /* 複数行になるのを防ぐ */
        }
        .branch-badge { font-size: 9px; color: #64748b; font-weight: normal; background-color:#e2e8f0; padding: 1px 4px; border-radius: 4px; display: inline-block; margin-top: 2px; }
        
        /* データの格子セルの高さと配置を固定 */
        .data-cell { 
            vertical-align: top; 
            background-color: #ffffff; 
            padding: 3px !important; 
            height: 40px !important; /* 講師名セルと同じ高さに指定 */
            max-height: 40px !important;
            overflow: hidden; 
        }
        
        /* 生徒バッジの見た目統一＆文字溢れ対策(三点リーダー) */
        .student-badge { 
            padding: 3px 4px; 
            border-radius: 4px; 
            margin-bottom: 2px; 
            display: block; 
            font-size: 11px; 
            font-weight: bold; 
            width: 100%; 
            box-sizing: border-box;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis; /* 文字が溢れたら自動で「...」にする */
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
            cursor: help;
        }
        
        /* 固定スクロール用 */
        .scroll-container .sticky-col { position: sticky; left: 0; z-index: 2; border-right: 2px solid #cbd5e1 !important; }
        .scroll-container .header-col { z-index: 3; }
        .scroll-container .name-col { z-index: 1; box-shadow: 2px 0 5px rgba(0,0,0,0.04); }
    </style>
    """, unsafe_allow_html=True)

    period_tabs = st.tabs(["🏫 通常期間の予定表管理", "☀️ 夏期講習期間の予定表管理"])
    
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

    # 校舎マッピング・NG・指名講師などの前処理
    student_branch_map = {}
    teacher_branch_map = {}
    if not df_student_master.empty and "生徒名" in df_student_master.columns:
        for _, row in df_student_master.iterrows():
            s_name = str(row["生徒名"]).replace(" ", "").strip()
            sid = str(row.get("生徒ID", "")).strip().lower()
            if s_name:
                if sid.startswith("t"): student_branch_map[s_name] = "田端"
                elif sid.startswith("h"): student_branch_map[s_name] = "東十条"

    for df_temp in [df_contracts, df_student_shifts]:
        if not df_temp.empty and "生徒名" in df_temp.columns:
            for _, row in df_temp.iterrows():
                s_name = str(row["生徒名"]).replace(" ", "").strip()
                if s_name and s_name not in student_branch_map:
                    sid = str(row.get("生徒ID", "")).strip().lower()
                    if sid.startswith("t"): student_branch_map[s_name] = "田端"
                    elif sid.startswith("h"): student_branch_map[s_name] = "東十条"

    teacher_list = []
    if not df_teacher_master.empty and "講師名" in df_teacher_master.columns:
        teacher_list = sorted(df_teacher_master["講師名"].dropna().unique().tolist())
        for _, row in df_teacher_master.iterrows():
            t_name = str(row["講師名"]).replace(" ", "").strip()
            if not t_name: continue
            t_branch = row.get("校舎", "")
            if not t_branch or pd.isna(t_branch):
                t_id = str(row.get("講師ID", "")).strip().lower()
                if t_id.startswith("t"): t_branch = "田端"
                elif t_id.startswith("h"): t_branch = "東十条"
                else: t_branch = "両校"
            teacher_branch_map[t_name] = t_branch

    tabata_teachers = [t for t, b in teacher_branch_map.items() if b in ["田端", "両校"]]
    higashijujo_teachers = [t for t, b in teacher_branch_map.items() if b in ["東十条", "両校"]]

    nomination_map = {}
    if not df_nominate.empty and "指名生徒名" in df_nominate.columns:
        for _, row in df_nominate.iterrows():
            sn = str(row["指名生徒名"]).replace(" ", "").strip()
            tn = str(row["講師名"]).replace(" ", "").strip()
            if sn not in nomination_map: nomination_map[sn] = set()
            nomination_map[sn].add(tn)

    ng_map = {}
    if not df_ng.empty and "NG生徒名" in df_ng.columns:
        for _, row in df_ng.iterrows():
            sn = str(row["NG生徒名"]).replace(" ", "").strip()
            tn = str(row["講師名"]).replace(" ", "").strip()
            if sn not in ng_map: ng_map[sn] = set()
            ng_map[sn].add(tn)

    days_of_week_map = ["月", "火", "水", "木", "金", "土", "日"]

    for tab_idx, is_summer in enumerate([False, True]):
        with period_tabs[tab_idx]:
            st.subheader("🗓️ 表示・作成範囲の選択")
            col1, col2 = st.columns(2)
            today = datetime.date.today()
            
            default_start = today if not is_summer else datetime.date(today.year, 7, 21)
            start_date = col1.date_input("🗓️ 開始日を選択", default_start, key=f"start_date_{is_summer}")
            end_date = col2.date_input("🗓️ 終了日を選択", default_start + datetime.timedelta(days=14), key=f"end_date_{is_summer}")

            if start_date > end_date:
                st.error("⚠️ 開始日は終了日より前の日付を選択してください。")
                continue

            delta = end_date - start_date
            dates_in_scope = [(start_date + datetime.timedelta(days=i)).strftime("%Y/%m/%d") for i in range(delta.days + 1)]

            tab_create, tab_view = st.tabs(["✨ 新しい予定表を作成する", "📋 確定済みの予定表を確認する"])

            # -------------------------------------------------------------
            # ✨ 新しい予定表を作成する（手動微調整 UI 搭載版）
            # -------------------------------------------------------------
            with tab_create:
                btn_label = f"✨ 自動生成ロジックを実行する ({'夏期講習時間割' if is_summer else '通常時間割'})"
                if st.button(btn_label, type="primary", key=f"gen_btn_{is_summer}", use_container_width=True):
                    with st.spinner("アルゴリズムを実行中..."):
                        t_shifts = df_teacher_shifts[df_teacher_shifts["日付"].isin(dates_in_scope)] if not df_teacher_shifts.empty else pd.DataFrame()
                        s_shifts = df_student_shifts[df_student_shifts["日付"].isin(dates_in_scope)] if not df_student_shifts.empty else pd.DataFrame()
                        
                        contract_remains = {} 
                        for _, row in df_contracts.iterrows():
                            c_name = str(row.get("講習名", ""))
                            is_summer_contract = "夏" in c_name
                            if is_summer != is_summer_contract: continue
                            
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
                        
                        schedule = {d: {s: {} for s in get_slots_for_date(d, is_summer)} for d in dates_in_scope}
                        busy_students = {d: {s: set() for s in get_slots_for_date(d, is_summer)} for d in dates_in_scope}
                        teacher_slot_branches = {d: {} for d in dates_in_scope}
                        student_daily_subjects = {d: {} for d in dates_in_scope} 
                        teacher_slot_symbols = {d: {s: {} for s in get_slots_for_date(d, is_summer)} for d in dates_in_scope}
                        
                        if not t_shifts.empty:
                            for _, row in t_shifts.iterrows():
                                d = row["日付"]
                                t_name = row.get("講師名")
                                if not t_name or d not in schedule: continue
                                day_slots = get_slots_for_date(d, is_summer)
                                for s in day_slots:
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
                                    
                                    s_name_clean = str(s_name).replace(" ", "").strip()
                                    existing_s_branch = student_branch_map.get(s_name_clean)
                                    if existing_s_branch in ["田端", "東十条"]:
                                        if t_name not in teacher_slot_branches[d]: teacher_slot_branches[d][t_name] = {}
                                        teacher_slot_branches[d][t_name][s] = existing_s_branch
                                    if subj:
                                        if s_name not in student_daily_subjects[d]: student_daily_subjects[d][s_name] = {}
                                        student_daily_subjects[d][s_name][s] = subj

                        history_map = {}
                        if not df_lessons.empty and "日付" in df_lessons.columns:
                            df_lessons['DateObj'] = pd.to_datetime(df_lessons['日付'], errors='coerce')
                            df_past = df_lessons[df_lessons['DateObj'].dt.date < start_date]
                            for _, row in df_past.iterrows():
                                d_obj = row['DateObj']
                                if pd.isna(d_obj): continue
                                weekday = d_obj.weekday()
                                sn_c = str(row.get("生徒名", "")).replace(" ", "").strip()
                                tn_c = str(row.get("講師名", "")).replace(" ", "").strip()
                                slot = str(row.get("コマ名", ""))
                                subj = str(row.get("科目", ""))
                                if sn_c and tn_c and slot and subj:
                                    if sn_c not in history_map: history_map[sn_c] = {}
                                    if weekday not in history_map[sn_c]: history_map[sn_c][weekday] = {}
                                    if slot not in history_map[sn_c][weekday]: history_map[sn_c][weekday][slot] = {}
                                    if subj not in history_map[sn_c][weekday][slot]: history_map[sn_c][weekday][slot][subj] = {}
                                    history_map[sn_c][weekday][slot][subj][tn_c] = history_map[sn_c][weekday][slot][subj].get(tn_c, 0) + 1

                        new_lessons = []
                        for d in dates_in_scope:
                            current_weekday = datetime.datetime.strptime(d, "%Y/%m/%d").weekday() 
                            day_slots = get_slots_for_date(d, is_summer)
                            
                            for s in day_slots:
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
                                        s_name_clean = str(s_name).replace(" ", "").strip()
                                        
                                        valid_subject = None
                                        s_idx = day_slots.index(s)
                                        available_subjects = list(contract_remains[s_name].keys())
                                        available_subjects.sort(key=lambda x: contract_remains[s_name][x], reverse=True)
                                        
                                        for subj in available_subjects:
                                            if s_idx >= 2:
                                                prev1, prev2 = day_slots[s_idx - 1], day_slots[s_idx - 2]
                                                s_record = student_daily_subjects[d].get(s_name, {})
                                                if s_record.get(prev1) == subj and s_record.get(prev2) == subj: continue 
                                            valid_subject = subj
                                            break
                                        
                                        if not valid_subject: continue 
                                        target_subject = valid_subject
                                        
                                        past_fixed_teacher = None
                                        if s_name_clean in history_map and current_weekday in history_map[s_name_clean] and s in history_map[s_name_clean][current_weekday] and target_subject in history_map[s_name_clean][current_weekday][s]:
                                            teacher_counts = history_map[s_name_clean][current_weekday][s][target_subject]
                                            if teacher_counts: past_fixed_teacher = max(teacher_counts, key=teacher_counts.get)
                                        
                                        available_teachers = schedule[d][s]
                                        s_branch = student_branch_map.get(s_name_clean, "不明")
                                        best_teacher, best_score = None, 9999
                                        
                                        for t_name, assigned_students in available_teachers.items():
                                            if len(assigned_students) >= max_students: continue
                                            t_name_clean = str(t_name).replace(" ", "").strip()
                                            if t_name_clean in ng_map.get(s_name_clean, set()): continue
                                                
                                            t_branch = teacher_branch_map.get(t_name, "両校")
                                            if s_branch in ["田端", "東十条"] and t_branch in ["田端", "東十条"] and t_branch != s_branch: continue 

                                            branch_conflict = False
                                            for assigned_s in assigned_students:
                                                a_name = assigned_s.split('(')[0].replace(" ", "").strip()
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
                                                if t_name_clean in nomination_map.get(s_name_clean, set()): score -= 400  
                                                if t_name_clean == past_fixed_teacher: score -= 300
                                                
                                                same_subj_count = sum(1 for a in assigned_students if f"({target_subject[0]})" in a)
                                                mixed_subj_count = len(assigned_students) - same_subj_count
                                                if mixed_subj_count > 0: score += 100 
                                                if same_subj_count > 0: score -= 50  
                                                score += len(assigned_students) * 5 
                                                
                                                if score < best_score: best_score, best_teacher = score, t_name
                                                
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
                            st.session_state[f"new_lessons_{is_summer}"] = new_lessons
                            st.success("🎉 自動コマ組みが完了しました！下の手動修正パネルおよびプレビューで確認してください。")
                        else:
                            st.warning("⚠️ 新しく割り当てられる契約コマが見つかりませんでした。")

                # 🛠️ 最強のドラッグ＆ドロップ調整UI セクション
                if f"new_lessons_{is_summer}" in st.session_state:
                    st.write("---")
                    st.markdown("### 🖱️ 【最強】ドラッグ＆ドロップ手動調整パネル")
                    st.caption("生徒のパネルをマウスで掴んで、別の先生の枠へ直接移動できます！")
                    
                    # コンポーネントに渡すためのデータを準備
                    draft_lessons = st.session_state[f"new_lessons_{is_summer}"]
                    
                    component_data = {
                        "dates": dates_in_scope[:7], # 画面に収めるため最初の1週間分を渡す例
                        "slots": get_slots_for_date(dates_in_scope[0], is_summer),
                        "teachers": all_target_teachers, # 画面上部で作成した講師リスト
                        "lessons": draft_lessons
                    }

                    # ✨ カスタムコンポーネントの呼び出し（JSと通信開始）
                    updated_lessons = draggable_board_component(
                        data=component_data, 
                        key=f"drag_drop_{is_summer}"
                    )

                    # JS側でドロップが発生し、新しいデータが返ってきたらセッションを上書きして再描画
                    if updated_lessons is not None:
                        st.session_state[f"new_lessons_{is_summer}"] = updated_lessons
                        st.rerun()

                    # 📋 リアルタイムプレビュー
                    st.markdown("#### 📊 修正連動型・時間割表プレビュー")
                    df_latest_draft = pd.DataFrame(st.session_state[f"new_lessons_{is_summer}"])
                    
                    weeks = [dates_in_scope[i:i+7] for i in range(0, len(dates_in_scope), 7)]
                    tab_labels = [f"📅 {w[0].split('/', 1)[1]} 〜 ({idx+1}週目)" for idx, w in enumerate(weeks[:4])]
                    
                    if tab_labels:
                        preview_tabs = st.tabs(tab_labels)
                        df_combined = pd.concat([df_lessons, df_latest_draft], ignore_index=True) if not df_lessons.empty else df_latest_draft
                        for idx, w_dates in enumerate(weeks[:4]):
                            with preview_tabs[idx]:
                                html_code = generate_weekly_matrix_html(df_combined[df_combined["日付"].isin(w_dates)], w_dates, days_of_week_map, teacher_branch_map, all_branch_teachers=list(teacher_branch_map.keys()), is_summer_mode=is_summer, is_print_mode=False)
                                st.markdown(html_code, unsafe_allow_html=True)

                    st.write("")
                    if st.button("💾 この予定表をすべて確定してスプレッドシートに保存", type="primary", key=f"save_btn_{is_summer}", use_container_width=True):
                        with st.spinner("スプレッドシートへ授業データを保存中..."):
                            df_to_save = pd.DataFrame(st.session_state[f"new_lessons_{is_summer}"])
                            if not df_to_save.empty:
                                success = robust_api_call(lambda: save_lesson_schedule(df_to_save), fallback_value=False)
                                if success:
                                    st.success("✅ 授業予定表をすべて確定保存しました！")
                                    st.cache_data.clear() 
                                    del st.session_state[f"new_lessons_{is_summer}"]
                                    time.sleep(1.5)
                                    st.rerun()
                                else: st.error("❌ 保存に失敗しました。")

            # -------------------------------------------------------------
            # 📋 確定済みの予定表を確認する
            # -------------------------------------------------------------
            with tab_view:
                c_title, c_print = st.columns([0.8, 0.2])
                c_title.subheader("📋 確定済みの授業予定表")
                
                with c_print:
                    components.html(f"""
                        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
                        <button onclick="downloadPDF()" id="pdfBtn" style="padding: 8px 15px; background: #dc2626; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; width: 100%; font-family: sans-serif; font-size: 14px; box-sizing: border-box;">
                            📄 PDFをダウンロード
                        </button>
                        <script>
                        function downloadPDF() {{
                            const btn = document.getElementById('pdfBtn');
                            btn.innerText = '⏳ PDF変換中...';
                            setTimeout(() => {{
                                const parentDoc = window.parent.document;
                                const elements = parentDoc.querySelectorAll('.print-container-{is_summer}');
                                if(elements.length === 0) {{
                                    alert('予定表が見つかりません。');
                                    btn.innerText = '📄 PDFをダウンロード';
                                    return;
                                }}
                                const wrapper = document.createElement('div');
                                const style = document.createElement('style');
                                style.innerHTML = `
                                    .print-optimized-table {{ table-layout: fixed; width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 11px; }}
                                    .print-optimized-table th, .print-optimized-table td {{ border: 1px solid #000; padding: 4px; text-align: center; }}
                                    .col-teacher-name {{ width: 90px; }}
                                    .col-slot-width {{ width: 60px; }}
                                    .header-col {{ background-color: #f7f9fa; font-weight: bold; }}
                                    .date-header {{ background-color: #f7f9fa; font-weight: bold; font-size: 13px; }}
                                    .slot-header {{ background-color: #fcfcfc; font-size: 11px; font-weight: bold; color: #555; }}
                                    .name-col {{ font-weight: bold; background-color: #fafafa; font-size: 12px; text-align: left; padding-left: 5px; }}
                                    .branch-badge {{ font-size: 9px; color: #777; background-color:#eee; padding:1px 2px; border-radius:2px; }}
                                    .student-badge {{ font-size: 10px; font-weight: bold; padding: 3px; margin: 1px 0; border-radius: 2px; border: 1px solid rgba(0,0,0,0.1); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
                                    .print-container-{is_summer} {{ margin-bottom: 20px; page-break-after: always; display: block !important; }}
                                `;
                                wrapper.appendChild(style);
                                elements.forEach(el => {{
                                    const clone = el.cloneNode(true);
                                    clone.style.display = 'block';
                                    wrapper.appendChild(clone);
                                }});
                                const opt = {{
                                    margin:       0.2,
                                    filename:     '{"夏期講習_" if is_summer else "通常_"}授業予定表.pdf',
                                    image:        {{ type: 'jpeg', quality: 0.98 }},
                                    html2canvas:  {{ scale: 2, useCORS: true }},
                                    jsPDF:        {{ unit: 'in', format: 'a4', orientation: 'landscape' }}
                                }};
                                html2pdf().set(opt).from(wrapper).save().then(() => {{
                                    btn.innerText = '📄 PDFをダウンロード';
                                }}).catch(() => {{
                                    btn.innerText = '📄 PDFをダウンロード';
                                }});
                            }}, 100);
                        }}
                        </script>
                    """, height=60)
                
                st.caption(f"登録されている **{start_date.strftime('%Y/%m/%d')} 〜 {end_date.strftime('%m/%d')}** のスケジュールです。")
                
                if not df_lessons.empty:
                    date_col = "日付" if "日付" in df_lessons.columns else "日時" if "日時" in df_lessons.columns else None
                    if date_col:
                        df_lessons_ready = df_lessons.rename(columns={date_col: "日付"})
                        df_scope_lessons = df_lessons_ready[df_lessons_ready["日付"].isin(dates_in_scope)]
                        
                        view_weeks = [dates_in_scope[i:i+7] for i in range(0, len(dates_in_scope), 7)]
                        view_tab_labels = [f"📅 {w[0].split('/', 1)[1]} 〜 ({idx+1}週目)" for idx, w in enumerate(view_weeks[:4])]
                        
                        if view_tab_labels:
                            view_tabs = st.tabs(view_tab_labels)
                            for idx, w_dates in enumerate(view_weeks[:4]):
                                with view_tabs[idx]:
                                    df_view_week_data = df_scope_lessons[df_scope_lessons["日付"].isin(w_dates)] if not df_scope_lessons.empty else pd.DataFrame()
                                    
                                    if not df_view_week_data.empty:
                                        df_view_week_data = df_view_week_data.copy()
                                        df_view_week_data["校舎"] = df_view_week_data["生徒名"].apply(
                                            lambda x: student_branch_map.get(str(x).replace(" ", "").strip(), "不明")
                                        )
                                        df_tabata = df_view_week_data[df_view_week_data["校舎"] == "田端"]
                                        df_higashijujo = df_view_week_data[df_view_week_data["校舎"] == "東十条"]
                                    else:
                                        df_tabata = pd.DataFrame()
                                        df_higashijujo = pd.DataFrame()
                                        
                                    st.markdown("### 🏫 田端校舎")
                                    html_scroll = generate_weekly_matrix_html(df_tabata, w_dates, days_of_week_map, teacher_branch_map, all_branch_teachers=tabata_teachers, is_summer_mode=is_summer, is_print_mode=False)
                                    html_print = generate_weekly_matrix_html(df_tabata, w_dates, days_of_week_map, teacher_branch_map, all_branch_teachers=tabata_teachers, is_summer_mode=is_summer, is_print_mode=True)
                                    html_print = html_print.replace("print-container", f"print-container-{is_summer}")
                                    st.markdown(html_scroll + html_print, unsafe_allow_html=True)
                                        
                                    st.write("") 
                                    
                                    st.markdown("### 🏫 東十条校舎")
                                    html_scroll2 = generate_weekly_matrix_html(df_higashijujo, w_dates, days_of_week_map, teacher_branch_map, all_branch_teachers=higashijujo_teachers, is_summer_mode=is_summer, is_print_mode=False)
                                    html_print2 = generate_weekly_matrix_html(df_higashijujo, w_dates, days_of_week_map, teacher_branch_map, all_branch_teachers=higashijujo_teachers, is_summer_mode=is_summer, is_print_mode=True)
                                    html_print2 = html_print2.replace("print-container", f"print-container-{is_summer}")
                                    st.markdown(html_scroll2 + html_print2, unsafe_allow_html=True)
                        else:
                            st.info("ℹ️ 指定された期間内に確定登録された授業はまだありません。")