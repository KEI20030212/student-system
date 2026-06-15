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

def generate_weekly_matrix_html(df_source, dates_for_week, slots, days_of_week_map, teacher_branch_map=None):
    """
    1週間分のデータを『縦軸：講師名』『横軸：日付（曜日）』のマトリクスHTMLとして生成する関数
    授業科目を指定された背景色で色分けします。
    """
    if teacher_branch_map is None:
        teacher_branch_map = {}
        
    if df_source.empty or not dates_for_week:
        return "<p style='color: gray; font-style: italic; padding: 10px;'>この期間の授業予定はありません。</p>"
        
    teachers = sorted(df_source["講師名"].dropna().unique())
    if not teachers:
        return "<p style='color: gray; font-style: italic; padding: 10px;'>配置された講師がいません。</p>"
        
    # 🎨 ユーザー指定の科目カラーマップ
    color_map = {
        "国語": "background-color: #C5A059; color: white;", # 黄土色
        "数学": "background-color: #B3E5FC; color: #1A237E;", # 水色
        "英語": "background-color: #F8BBD0; color: #880E4F;", # ピンク
        "理科": "background-color: #C8E6C9; color: #1B5E20;", # 緑
        "社会": "background-color: #FFF9C4; color: #F57F17;"  # 黄色
    }
    
    html = """
    <div style="overflow-x: auto;">
    <table style="width:100%; border-collapse: collapse; border: 1px solid #ddd; min-width: 800px; background-color: #ffffff; color: #333333; font-family: sans-serif;">
    """
    
    # --- ヘッダー行 (日付・曜日) ---
    html += "<tr style='background-color: #f7f9fa; border-bottom: 2px solid #ccc;'>"
    html += "<th style='border: 1px solid #ddd; padding: 10px; text-align: center; font-size: 0.9rem; font-weight: bold; width: 120px;'>講師名</th>"
    
    for d in dates_for_week:
        dt_obj = datetime.datetime.strptime(d, "%Y/%m/%d")
        day_str = days_of_week_map[dt_obj.weekday()]
        
        # 土日の色分け
        day_color = "#333333"
        if day_str == "土": day_color = "#1565C0"
        elif day_str == "日": day_color = "#C62828"
        
        html += f"""
        <th style='border: 1px solid #ddd; padding: 10px; text-align: center; font-size: 0.85rem; color: {day_color};'>
            <span style='font-size: 0.75rem; color: #666;'>{d.split('/', 1)[1]}</span><br>({day_str})
        </th>
        """
    html += "</tr>"
    
    # --- データ行 (講師ごと) ---
    for t in teachers:
        t_branch = teacher_branch_map.get(t, "")
        branch_html = f"<br><span style='font-size: 0.7rem; color: #888; font-weight: normal; background-color:#eee; padding:2px 4px; border-radius:3px;'>{t_branch}</span>" if t_branch else ""
        
        html += "<tr style='border-bottom: 1px solid #eee;'>"
        html += f"<td style='border: 1px solid #ddd; padding: 10px; font-weight: bold; background-color: #fafafa; font-size: 0.85rem;'>{t}{branch_html}</td>"
        
        for d in dates_for_week:
            html += "<td style='border: 1px solid #ddd; padding: 6px; vertical-align: top; width: 14%;'>"
            
            df_cell = df_source[(df_source["講師名"] == t) & (df_source["日付"] == d)]
            
            if not df_cell.empty:
                df_cell = df_cell.copy()
                df_cell["slot_idx"] = df_cell["コマ名"].apply(lambda x: slots.index(x) if x in slots else 99)
                df_cell = df_cell.sort_values("slot_idx")
                
                slot_groups = df_cell.groupby("コマ名")
                for slot_name in slots:
                    if slot_name in slot_groups.groups:
                        group = slot_groups.get_group(slot_name)
                        html += f"<div style='margin-bottom: 8px; padding: 4px; background-color: #fcfcfc; border: 1px solid #f0f0f0; border-radius: 4px;'>"
                        html += f"<span style='font-size: 0.7rem; font-weight: bold; color: #777;'>{slot_name}</span><br>"
                        
                        for _, row in group.iterrows():
                            s_name = row["生徒名"]
                            subj = row["科目"]
                            style = color_map.get(subj, "background-color: #e0e0e0; color: #333;")
                            
                            html += f"""
                            <span style='{style} padding: 2px 6px; border-radius: 3px; margin: 2px 1px 0 1px; display: inline-block; font-size: 0.75rem; font-weight: bold; width: calc(100% - 4px); text-align: center; box-shadow: 0 1px 2px rgba(0,0,0,0.05);' title='{subj}'>
                                {s_name}
                            </span>
                            """
                        html += "</div>"
            html += "</td>"
        html += "</tr>"
        
    html += "</table></div>"
    html = "".join([line.strip() for line in html.split("\n")])
    return html


def render_matching_page():
    st.header("🧩 スマート・自動予定表作成")
    st.write("生徒と講師のシフト・指導科目・**所属校舎**を考慮して、最適な授業予定表を自動生成します🚀")

    # ------------------------------------------
    # 1. 本番データのロード
    # ------------------------------------------
    with st.spinner("スプレッドシートから最新データを同期中..."):
        df_student_master = robust_api_call(get_student_master, fallback_value=pd.DataFrame())
        df_contracts = robust_api_call(load_contract_master, fallback_value=pd.DataFrame())
        df_lessons = robust_api_call(load_lesson_schedule, fallback_value=pd.DataFrame())
        df_teacher_shifts = robust_api_call(lambda: load_all_shifts("講師"), fallback_value=pd.DataFrame())
        df_student_shifts = robust_api_call(lambda: load_all_shifts("生徒"), fallback_value=pd.DataFrame())
        df_teacher_master = robust_api_call(load_teacher_master, fallback_value=pd.DataFrame())

    if df_contracts.empty:
        st.warning("⚠️ 講習契約マスタにデータが登録されていません。先に契約を登録してください。")
        st.stop()

    # ------------------------------------------
    # 校舎マッピングの準備 (生徒・講師)
    # ------------------------------------------
    student_branch_map = {}
    teacher_branch_map = {}

    # 生徒の校舎をIDから判定 ('t'始まり=田端, 'h'始まり=東十条)
    if not df_student_master.empty and "生徒名" in df_student_master.columns and "生徒ID" in df_student_master.columns:
        for _, row in df_student_master.iterrows():
            sid = str(row.get("生徒ID", "")).strip().lower()
            if sid.startswith("t"):
                student_branch_map[row["生徒名"]] = "田端"
            elif sid.startswith("h"):
                student_branch_map[row["生徒名"]] = "東十条"

    # 生徒マスタになければ契約・シフトデータからもフォールバック推測
    for df_temp in [df_contracts, df_student_shifts]:
        if not df_temp.empty and "生徒ID" in df_temp.columns and "生徒名" in df_temp.columns:
            for _, row in df_temp.iterrows():
                s_name = row["生徒名"]
                if s_name not in student_branch_map:
                    sid = str(row.get("生徒ID", "")).strip().lower()
                    if sid.startswith("t"):
                        student_branch_map[s_name] = "田端"
                    elif sid.startswith("h"):
                        student_branch_map[s_name] = "東十条"

    # 講師の校舎を特定 (マスタ優先、シフトの「校舎」列も確認)
    if not df_teacher_master.empty and "校舎" in df_teacher_master.columns:
        for _, row in df_teacher_master.iterrows():
            teacher_branch_map[row["講師名"]] = row["校舎"]
            
    if not df_teacher_shifts.empty and "校舎" in df_teacher_shifts.columns:
        for _, row in df_teacher_shifts.iterrows():
            t_name = row.get("講師名")
            if t_name and t_name not in teacher_branch_map and pd.notna(row.get("校舎")):
                teacher_branch_map[t_name] = row["校舎"]

    # ------------------------------------------
    # 2. スケジュール作成・確認範囲の選択
    # ------------------------------------------
    st.subheader("📅 表示・作成範囲の選択")
    st.caption("任意の期間をカレンダーから指定して自動生成・確認ができます。")
    
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

    # ------------------------------------------
    # 【タブ1】 自動コマ組みの実行とプレビュー
    # ------------------------------------------
    with tab_create:
        btn_label = f"✨ {start_date.strftime('%m/%d')} 〜 {end_date.strftime('%m/%d')} の予定表を一括自動生成する"
        if st.button(btn_label, type="primary", use_container_width=True):
            with st.spinner("校舎間の移動制限などを考慮してアルゴリズムを実行中...（数秒かかります）"):
                
                t_shifts = df_teacher_shifts[df_teacher_shifts["日付"].isin(dates_in_scope)] if not df_teacher_shifts.empty else pd.DataFrame()
                s_shifts = df_student_shifts[df_student_shifts["日付"].isin(dates_in_scope)] if not df_student_shifts.empty else pd.DataFrame()
                
                # 契約残数の計算
                contract_remains = {} 
                for _, row in df_contracts.iterrows():
                    s_name = row["生徒名"]
                    subj = row["科目"]
                    count = int(row["契約コマ数"])
                    
                    scheduled = 0
                    if not df_lessons.empty and "生徒名" in df_lessons.columns:
                        scheduled = len(df_lessons[(df_lessons["生徒名"] == s_name) & (df_lessons["科目"] == subj)])
                    
                    remains = count - scheduled
                    if remains > 0:
                        if s_name not in contract_remains:
                            contract_remains[s_name] = {}
                        contract_remains[s_name][subj] = remains

                # 講師の指導スキルの用意
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
                
                schedule = {d: {s: {} for s in slots} for d in dates_in_scope}
                busy_students = {d: {s: set() for s in slots} for d in dates_in_scope}
                
                # 講師の「一日における現在勤務中の校舎」を記録する辞書（移動ペナルティ計算用）
                teacher_daily_branch = {d: {} for d in dates_in_scope}
                
                # 〇シフトの反映
                if not t_shifts.empty:
                    for _, row in t_shifts.iterrows():
                        d = row["日付"]
                        t_name = row.get("講師名")
                        if not t_name or d not in schedule: continue
                        for s in slots:
                            if row.get(s) == "〇":
                                schedule[d][s][t_name] = []
                                
                # 既存授業の反映（これによって既に特定の校舎での勤務が決まっているかも記録）
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
                            
                            # 既にアサイン済みの校舎を記録
                            existing_s_branch = student_branch_map.get(s_name)
                            if existing_s_branch in ["田端", "東十条"]:
                                curr_b = teacher_daily_branch[d].get(t_name)
                                if not curr_b:
                                    teacher_daily_branch[d][t_name] = existing_s_branch
                                elif curr_b != existing_s_branch:
                                    teacher_daily_branch[d][t_name] = "混在"

                # 自動マッチング実行
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
                                s_branch = student_branch_map.get(s_name, "不明")
                                
                                best_teacher = None
                                best_score = 9999
                                
                                for t_name, assigned_students in available_teachers.items():
                                    if len(assigned_students) >= max_students:
                                        continue
                                        
                                    t_branch = teacher_branch_map.get(t_name, "両校")
                                    
                                    # 🛑 校舎の絶対ルールによるブロック
                                    if s_branch in ["田端", "東十条"]:
                                        if t_branch in ["田端", "東十条"] and t_branch != s_branch:
                                            continue # 所属校舎が違うためNG
                                            
                                    # ⚠️ 「両校」講師の同日内移動ペナルティ計算
                                    travel_penalty = 0
                                    if t_branch == "両校" and s_branch in ["田端", "東十条"]:
                                        current_day_branch = teacher_daily_branch[d].get(t_name)
                                        if current_day_branch and current_day_branch != s_branch and current_day_branch != "混在":
                                            # すでにその日別の校舎で教えている場合、重いペナルティ（なるべく別講師を探させる）
                                            travel_penalty = 100 
                                            
                                    skills = teacher_skills.get(t_name, {"priority": 5, "subjects": []})
                                    can_teach = target_subject in skills["subjects"] if skills["subjects"] else True
                                    
                                    if can_teach:
                                        # スコアが低いほど優先的にアサイン
                                        score = (skills["priority"] * 10) + (len(assigned_students) * 15) + travel_penalty
                                        if score < best_score:
                                            best_score = score
                                            best_teacher = t_name
                                            
                                if best_teacher:
                                    schedule[d][s][best_teacher].append(f"{s_name}({target_subject[0]})")
                                    busy_students[d][s].add(s_name)
                                    
                                    # その日その講師が勤務している校舎を記録・更新
                                    if s_branch in ["田端", "東十条"]:
                                        curr_b = teacher_daily_branch[d].get(best_teacher)
                                        if not curr_b:
                                            teacher_daily_branch[d][best_teacher] = s_branch
                                        elif curr_b != s_branch:
                                            teacher_daily_branch[d][best_teacher] = "混在"
                                    
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

                for lesson in new_lessons:
                    d_val = lesson["日付"]
                    s_val = lesson["コマ名"]
                    t_val = lesson["講師名"]
                    total_students = len(schedule[d_val][s_val][t_val])
                    lesson["指導形態"] = f"1:{total_students}"

                if new_lessons:
                    st.session_state["new_lessons"] = new_lessons
                    st.success(f"🎉 期間内の自動コマ組みが完了しました！下の一覧とボードで確認してください。")
                else:
                    st.warning("⚠️ 指定された期間内で新しく割り当てられる授業が見つかりませんでした。")

        if "new_lessons" in st.session_state:
            st.subheader("📋 【下書き】自動生成された授業予定表")
            
            df_new_flat = pd.DataFrame(st.session_state["new_lessons"])
            st.markdown(f"**🔥 新規マッチング授業一覧（全 {len(df_new_flat)} 件）**")
            st.dataframe(
                df_new_flat[["日付", "コマ名", "講師名", "生徒名", "科目", "指導形態"]], 
                use_container_width=True, 
                hide_index=True
            )
            
            st.markdown("---")
            st.markdown("#### 🔍 週別スケジュールボードで配置を確認")
            st.caption("指定された期間を1週間(7日間)ごとに分割しています。タブを切り替えてカラー配置を確認してください。")
            
            weeks = [dates_in_scope[i:i+7] for i in range(0, len(dates_in_scope), 7)]
            tab_labels = [f"📅 {w[0].split('/', 1)[1]} 〜 ({idx+1}週目)" for idx, w in enumerate(weeks[:4])]
            
            if tab_labels:
                preview_tabs = st.tabs(tab_labels)
                df_combined = pd.concat([df_lessons, df_new_flat], ignore_index=True) if not df_lessons.empty else df_new_flat
                
                for idx, w_dates in enumerate(weeks[:4]):
                    with preview_tabs[idx]:
                        df_week_data = df_combined[df_combined["日付"].isin(w_dates)]
                        html_code = generate_weekly_matrix_html(
                            df_week_data, w_dates, slots, days_of_week_map, teacher_branch_map
                        )
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
                        else:
                            st.error("❌ 保存に失敗しました。ネットワーク状況を確認してください。")

    # ------------------------------------------
    # 【タブ2】 確定済みデータの常時確認
    # ------------------------------------------
    with tab_view:
        st.subheader(f"📋 確定済みの授業予定表")
        st.caption(f"現在本番登録されている **{start_date.strftime('%Y/%m/%d')} 〜 {end_date.strftime('%m/%d')}** の確定スケジュールです。")
        
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
                            html_code_view = generate_weekly_matrix_html(
                                df_view_week_data, w_dates, slots, days_of_week_map, teacher_branch_map
                            )
                            st.markdown(html_code_view, unsafe_allow_html=True)
            else:
                st.info("ℹ️ 指定された期間内に確定登録された授業はまだありません。")
        else:
            st.info("ℹ️ 確定済みの授業スケジュールデータ自体がありません。")