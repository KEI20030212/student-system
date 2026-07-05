import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import datetime
import time
import os
import json

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
from utils.optimizer import run_optimization_engine

# 🌟 JSコンポーネントの読み込み
_COMPONENT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "components", "drag_drop_board"))
draggable_board_component = components.declare_component(
    "draggable_board",
    path=_COMPONENT_PATH
)

def get_slots_for_date(date_str, is_summer_mode):
    """期間モードと曜日を判定し、必要なコマ枠を返す"""
    if is_summer_mode:
        return ["Aコマ", "Bコマ", "0コマ", "1コマ", "2コマ", "3コマ", "4コマ"]
    else:
        dt_obj = datetime.datetime.strptime(date_str, "%Y/%m/%d")
        if dt_obj.weekday() < 5:  # 月〜金
            return ["2コマ", "3コマ", "4コマ"]
        else:  # 土日
            return ["0コマ", "1コマ", "2コマ", "3コマ", "4コマ"]

def generate_weekly_matrix_html(df_source, dates_for_week, days_of_week_map, teacher_branch_map=None, all_branch_teachers=None, is_summer_mode=False, is_print_mode=False):
    """
    確定済み予定表のHTML生成ロジック。
    🌟 PDF印刷時(is_print_mode=True)は、横幅がはみ出さないように「数日単位」で表を分割（チャンク化）し、
    縦幅が必ず1ページに収まるように改ページ制御を行います。
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
        "国語": "background-color: #FDE68A; color: #92400E;", # 優しいイエロー
        "数学": "background-color: #BAE6FD; color: #075985;", # 爽やかなブルー
        "英語": "background-color: #FECDD3; color: #9F1239;", # 柔らかいピンク
        "理科": "background-color: #BBF7D0; color: #166534;", # 落ち着いたグリーン
        "社会": "background-color: #FED7AA; color: #9A3412;"  # 温かみのあるオレンジ
    }
    
    # 🌟 印刷時は横に長くなりすぎないよう、夏期は2日ごと、通常は3日ごとに表をぶつ切りにする
    if is_print_mode:
        chunk_size = 2 if is_summer_mode else 3
        date_chunks = [dates_for_week[i:i + chunk_size] for i in range(0, len(dates_for_week), chunk_size)]
    else:
        date_chunks = [dates_for_week]
    
    h = []
    
    for chunk_idx, chunk_dates in enumerate(date_chunks):
        container_class = "print-container print-page" if is_print_mode else "scroll-container"
        # 印刷時は表ごとに改ページを入れる
        page_break_style = "page-break-after: always;" if is_print_mode else ""
        
        h.append(f"<div class='{container_class}' style='{page_break_style}'><table class='print-optimized-table'>")
        
        # コマ幅の完全固定
        h.append("<colgroup><col class='col-teacher-name'>")
        for d in chunk_dates:
            for _ in get_slots_for_date(d, is_summer_mode):
                h.append("<col class='col-slot-width'>")
        h.append("</colgroup>")

        # ヘッダー1行目（日付）
        h.append("<tr><th rowspan='2' class='sticky-col header-col'>講師名</th>")
        for d in chunk_dates:
            dt_obj = datetime.datetime.strptime(d, "%Y/%m/%d")
            day_str = days_of_week_map[dt_obj.weekday()]
            day_color = "#1565C0" if day_str == "土" else "#C62828" if day_str == "日" else "#333333"
            date_short = d.split('/', 1)[1]
            day_slots = get_slots_for_date(d, is_summer_mode)
            h.append(f"<th colspan='{len(day_slots)}' class='date-header' style='color: {day_color};'><span class='date-text'>{date_short}</span> ({day_str})</th>")
        h.append("</tr><tr>")
        
        # ヘッダー2行目（コマ名）
        for d in chunk_dates:
            for s in get_slots_for_date(d, is_summer_mode):
                h.append(f"<th class='slot-header'>{s.replace('コマ', '')}</th>")
        h.append("</tr>")
        
        # データ行
        for t in all_target_teachers:
            t_branch = teacher_branch_map.get(t, "")
            branch_html = f"<br><span class='branch-badge'>{t_branch}</span>" if t_branch else ""
            h.append(f"<tr><td class='sticky-col name-col'>{t}{branch_html}</td>")
            
            for d in chunk_dates:
                df_date = df_source[(df_source["講師名"] == t) & (df_source["日付"] == d)] if not df_source.empty else pd.DataFrame()
                for s in get_slots_for_date(d, is_summer_mode):
                    h.append("<td class='data-cell'>")
                    df_cell = df_date[df_date["コマ名"] == s] if not df_date.empty else pd.DataFrame()
                    if not df_cell.empty:
                        for _, row in df_cell.iterrows():
                            clean_name = str(row["生徒名"]).replace("\n", " ").strip()
                            disp_name = get_display_name(clean_name)
                            subj = row["科目"]
                            style = color_map.get(subj, "background-color: #e0e0e0; color: #333;")
                            h.append(f"<div class='student-badge' style='{style}' title='{row['生徒名']} ({subj})'>{disp_name}</div>")
                    h.append("</td>")
            h.append("</tr>")
        
        h.append("</table></div>")
        
    return "".join(h)


def render_matching_page():
    # 🎨 画面描画用CSS (モダンSaaS風にアップデート)
    st.markdown("""
    <style>
        /* コンテナ全体 */
        .scroll-container { 
            overflow-x: auto; max-width: 100%; 
            border: 1px solid #e2e8f0; border-radius: 12px; 
            margin-bottom: 24px; 
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03); 
            background-color: #ffffff;
        }
        .print-container { display: none; } 
        
        /* テーブル基本設定 */
        .print-optimized-table { 
            table-layout: fixed; width: auto; border-collapse: separate; border-spacing: 0;
            color: #334155; font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 13px; 
        }
        .col-teacher-name { width: 120px; }
        .col-slot-width { width: 85px; }
        
        /* セルの境界線とパディング */
        .print-optimized-table th, .print-optimized-table td { 
            border-right: 1px solid #f1f5f9; border-bottom: 1px solid #f1f5f9; 
            padding: 8px 6px; text-align: center; box-sizing: border-box;
        }
        
        /* ヘッダー周り */
        .header-col { background-color: #ffffff; font-weight: 600; border-bottom: 2px solid #e2e8f0 !important; color: #475569;}
        .date-header { background-color: #f8fafc; font-weight: 600; font-size: 13px; border-bottom: 1px solid #e2e8f0; }
        .date-text { font-size: 12px; font-weight: 500; }
        .slot-header { background-color: #f8fafc; font-size: 12px; font-weight: 600; color: #64748b; border-bottom: 2px solid #e2e8f0 !important; }
        
        /* 講師名カラム (Sticky) */
        .name-col { 
            font-weight: 600; background-color: #ffffff; font-size: 13px; text-align: left; padding-left: 12px; 
            border-bottom: 1px solid #f1f5f9; height: 48px !important; max-height: 48px !important;
            overflow: hidden; white-space: nowrap; color: #334155;
        }
        .branch-badge { 
            font-size: 10px; color: #64748b; background-color:#f1f5f9; 
            padding: 2px 6px; border-radius: 6px; display: inline-block; margin-top: 4px; font-weight: normal;
        }
        
        /* データセルとバッジ */
        .data-cell { vertical-align: top; background-color: #ffffff; padding: 4px !important; height: 48px !important; max-height: 48px !important; }
        
        .student-badge { 
            padding: 4px 6px; border-radius: 6px; margin-bottom: 4px; display: block; 
            font-size: 12px; font-weight: 600; text-align: center;
            width: 100%; box-sizing: border-box; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; 
            cursor: help; box-shadow: 0 1px 2px rgba(0,0,0,0.05); border: 1px solid rgba(255,255,255,0.3);
        }
        
        /* スクロール時の追従（Sticky）設定 */
        .scroll-container .sticky-col { position: sticky; left: 0; z-index: 2; border-right: 2px solid #e2e8f0 !important; }
        .scroll-container .header-col { z-index: 3; }
        .scroll-container .name-col { z-index: 1; box-shadow: 3px 0 6px rgba(0,0,0,0.02); }
    </style>
    """, unsafe_allow_html=True)

    period_tabs = st.tabs(["🏫 通常期間の予定表管理", "☀️ 夏期講習期間の予定表管理"])
    
    with st.spinner("データを同期中..."):
        df_student_master = robust_api_call(get_student_master, fallback_value=pd.DataFrame())
        df_contracts = robust_api_call(load_contract_master, fallback_value=pd.DataFrame())
        df_lessons = robust_api_call(load_lesson_schedule, fallback_value=pd.DataFrame())
        df_teacher_shifts = robust_api_call(lambda: load_all_shifts("講師"), fallback_value=pd.DataFrame())
        df_student_shifts = robust_api_call(lambda: load_all_shifts("生徒"), fallback_value=pd.DataFrame())
        df_teacher_master = robust_api_call(load_teacher_master, fallback_value=pd.DataFrame())
        df_nominate = robust_api_call(load_nominated_teacher_master, fallback_value=pd.DataFrame())
        df_ng = robust_api_call(load_compatibility_ng_master, fallback_value=pd.DataFrame())

    if df_contracts.empty:
        st.warning("⚠️ 契約マスタが登録されていません。")
        st.stop()

    # マッピング等の前処理
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
    if not df_nominate.empty:
        for _, row in df_nominate.iterrows():
            sn = str(row["指名生徒名"]).replace(" ", "").strip()
            tn = str(row["講師名"]).replace(" ", "").strip()
            if sn not in nomination_map: nomination_map[sn] = set()
            nomination_map[sn].add(tn)

    ng_map = {}
    if not df_ng.empty:
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
            # ✨ 新しい予定表を作成する（ドラッグ＆ドロップ完全統合版）
            # -------------------------------------------------------------
            with tab_create:
                btn_label = f"✨ 自動生成ロジックを実行する ({'夏期講習時間割' if is_summer else '通常時間割'})"
                if st.button(btn_label, type="primary", key=f"gen_btn_{is_summer}", use_container_width=True):
                    with st.spinner("AI最適化アルゴリズムを実行中...（最大数十秒かかります）"):
                        
                        # 🌟 分離した最適化エンジンを呼び出す
                        new_lessons = run_optimization_engine(
                            dates_in_scope=dates_in_scope,
                            is_summer=is_summer,
                            df_contracts=df_contracts,
                            df_teacher_shifts=df_teacher_shifts,
                            df_student_shifts=df_student_shifts,
                            df_lessons=df_lessons,
                            df_teacher_master=df_teacher_master,
                            student_branch_map=student_branch_map,
                            teacher_branch_map=teacher_branch_map,
                            nomination_map=nomination_map,
                            ng_map=ng_map
                        )

                        if new_lessons:
                            st.session_state[f"new_lessons_{is_summer}"] = new_lessons
                            st.success("🎉 自動コマ組みが完了しました！下の手動修正パネルで確認・確定してください。")
                        else:
                            st.warning("⚠️ 新しく割り当てられる契約コマが見つかりませんでした、または制約を満たす解が存在しません。")

                if f"new_lessons_{is_summer}" in st.session_state:
                    st.write("---")
                    st.markdown("### 🖱️ 【最強】ドラッグ＆ドロップ手動調整パネル")
                    st.caption("生徒のパネルをマウスで掴んで移動できます。（※半透明のパネルは既に確定済みの授業で、動かせません）")
                    
                    df_existing = df_lessons[df_lessons["日付"].isin(dates_in_scope)].fillna("") if not df_lessons.empty else pd.DataFrame()
                    existing_list = df_existing.to_dict(orient="records") if not df_existing.empty else []
                    for i, l in enumerate(existing_list):
                        l["is_new"] = False
                        l["授業ID"] = f"OLD-{i}"

                    draft_list = st.session_state[f"new_lessons_{is_summer}"]
                    for l in draft_list:
                        l["is_new"] = True

                    all_lessons_for_js = existing_list + draft_list

                    component_data = {
                        "dates": dates_in_scope, 
                        "slots": get_slots_for_date(dates_in_scope[0], is_summer),
                        "teachers": teacher_list, 
                        "lessons": all_lessons_for_js
                    }

                    component_result = draggable_board_component(
                        data=component_data, 
                        key=f"drag_drop_{is_summer}"
                    )

                    if isinstance(component_result, dict) and component_result.get("action") == "save":
                        with st.spinner("スプレッドシートへ授業データを保存中..."):
                            df_to_save = pd.DataFrame(component_result["lessons"])
                            if "is_new" in df_to_save.columns:
                                df_to_save = df_to_save.drop(columns=["is_new"]) 

                            if not df_to_save.empty:
                                success = robust_api_call(lambda: save_lesson_schedule(df_to_save), fallback_value=False)
                                if success:
                                    st.success("✅ 授業予定表をすべて確定保存しました！")
                                    st.cache_data.clear() 
                                    del st.session_state[f"new_lessons_{is_summer}"]
                                    time.sleep(1.5)
                                    st.rerun()
                                else: 
                                    st.error("❌ 保存に失敗しました。")

            # -------------------------------------------------------------
            # 📋 確定済みの予定表を確認する（PDF出力機能付き・極限レイアウト）
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
                                // 🌟 PDF印刷用の洗練されたCSS（波括弧を二重に修正）
                                style.innerHTML = `
                                    .print-page {{ 
                                        width: 100%; 
                                        page-break-after: always; 
                                        box-sizing: border-box;
                                        padding: 10px 0;
                                    }}
                                    .print-optimized-table {{ table-layout: fixed; width: 100%; border-collapse: collapse; font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 10px; line-height: 1.2; color: #333; }}
                                    .print-optimized-table th, .print-optimized-table td {{ border: 1px solid #cbd5e1; padding: 4px 2px; text-align: center; height: auto !important; max-height: none !important; }}
                                    .col-teacher-name {{ width: 70px; }}
                                    .col-slot-width {{ width: 55px; }}
                                    .header-col {{ background-color: #f8fafc; font-weight: bold; font-size: 11px; }}
                                    .date-header {{ background-color: #f8fafc; font-weight: bold; font-size: 11px; border-bottom: 2px solid #cbd5e1 !important; }}
                                    .slot-header {{ background-color: #ffffff; font-size: 10px; font-weight: normal; color: #475569; }}
                                    .name-col {{ font-weight: bold; background-color: #f8fafc; font-size: 11px; text-align: left; padding-left: 4px; }}
                                    .branch-badge {{ font-size: 8px; color: #64748b; background-color:#e2e8f0; padding:1px 4px; border-radius:4px; display: block; margin-top: 2px; text-align: center; width: max-content; }}
                                    .student-badge {{ font-size: 10px; font-weight: bold; padding: 2px; margin: 1px 0; border-radius: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
                                `;
                                wrapper.appendChild(style);
                                elements.forEach(el => {{
                                    const clone = el.cloneNode(true);
                                    clone.style.display = 'block';
                                    wrapper.appendChild(clone);
                                }});
                                const opt = {{
                                    margin:       0.1, /* マージンを最小限にして縦幅を稼ぐ */
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
                                    # 画面表示用（横長スクロール）
                                    html_scroll = generate_weekly_matrix_html(df_tabata, w_dates, days_of_week_map, teacher_branch_map, all_branch_teachers=tabata_teachers, is_summer_mode=is_summer, is_print_mode=False)
                                    # PDF出力用（はみ出さないように数日ごとに分割されたHTML）
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