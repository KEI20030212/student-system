# views/salary_dashboard.py

import streamlit as st
import pandas as pd
import math
import time
import zipfile
import io
import unicodedata

from utils.api_guard import robust_api_call
from utils.g_sheets import (
    get_all_logs, 
    load_instructor_master, 
    update_instructor_master,
    publish_salary_data
)
from utils.pdf_generator import generate_payslip_pdf

@st.cache_data(ttl=60, show_spinner="☁️ 授業データを一括取得中...（超高速🚀）")
def cached_get_all_logs():
    return robust_api_call(get_all_logs, fallback_value=pd.DataFrame())

@st.cache_data(ttl=3600, show_spinner="☁️ 講師マスタを読み込み中...")
def fetch_instructor_master_cached():
    df = robust_api_call(load_instructor_master, fallback_value=pd.DataFrame())
    if df.empty or "講師名" not in df.columns:
        return pd.DataFrame(columns=["講師名", "1:1単価", "1:2単価", "1:3単価", "交通費", "役職手当"])
    return df

def render_salary_dashboard_page():
    st.header("💰 給与・交通費ダッシュボード")

    df_instructors = fetch_instructor_master_cached().copy()

    # --------------------------------------------------------
    # 操作パネル（一括データ取得＆ゆらぎ吸収）
    # --------------------------------------------------------
    if 'toast_msg' in st.session_state:
        st.toast(st.session_state['toast_msg'], icon="✨")
        del st.session_state['toast_msg']

    df_all_raw = cached_get_all_logs()
    df_all = df_all_raw.copy() if not df_all_raw.empty else pd.DataFrame()
    
    month_options = ["データなし"]
    
    if not df_all.empty and "APIエラー発生" not in df_all.columns and '日時' in df_all.columns:
        name_col = '名前' if '名前' in df_all.columns else '生徒名'
        df_all = df_all.rename(columns={name_col: '生徒名'})
        
        df_all['日時'] = pd.to_datetime(df_all['日時'], format='mixed', errors='coerce')
        df_all = df_all.dropna(subset=['日時'])
        df_all['年月'] = df_all['日時'].dt.strftime("%Y年%m月")
        month_options = sorted(df_all['年月'].unique().tolist(), reverse=True)
    else:
        df_all = pd.DataFrame()

    col_month, col_btn = st.columns([2, 1], vertical_alignment="bottom")
    with col_month:
        selected_month = st.selectbox("📅 集計する月を選択", month_options)
    with col_btn:
        if st.button("🔄 給与データを最新に更新", type="primary", use_container_width=True):
            st.cache_data.clear() 
            st.toast("最新データを取得中...", icon="⏳")
            time.sleep(0.5)
            st.rerun()

    st.divider()

    tab_calc, tab_master = st.tabs(["📊 給与計算・明細発行", "👨‍🏫 講師単価・設定変更"])

    # ==========================================
    # Tab 1: 給与計算・明細発行
    # ==========================================
    with tab_calc:
        if df_all.empty or selected_month == "データなし":
            st.info("集計対象のデータがありません。")
        else:
            df_month = df_all[df_all['年月'] == selected_month].copy()
            df_month['担当講師'] = df_month['担当講師'].astype(str)
            df_month_exploded = df_month.assign(担当講師=df_month['担当講師'].str.split(r'[\n,、]')).explode('担当講師')
            df_month_exploded['担当講師'] = df_month_exploded['担当講師'].str.strip()
            
            if '授業形態' in df_month_exploded.columns:
                df_month_exploded['授業形態'] = df_month_exploded['授業形態'].astype(str).apply(
                    lambda x: unicodedata.normalize('NFKC', x).replace(' ', '')
                )

            valid_teachers = [t for t in df_month_exploded['担当講師'].unique() if t not in ["未入力", "", "nan", "None"]]
            
            if f"allowances_{selected_month}" not in st.session_state:
                st.session_state[f"allowances_{selected_month}"] = {}

            st.markdown(f"#### 💵 {selected_month} の役職手当・特別支給の調整")
            st.caption("※マスタの基本設定が自動入力されています。この月だけ特別に金額を変える場合は、ここで数字を書き換えてください。")
            
            cols_per_row = 3
            cols = st.columns(cols_per_row)
            
            for i, teacher in enumerate(valid_teachers):
                t_row_df = df_instructors[df_instructors["講師名"] == teacher]
                default_allowance = 0
                if not t_row_df.empty:
                    try: 
                        val = t_row_df.iloc[0].get('役職手当', 0)
                        default_allowance = int(float(val)) if not pd.isna(val) and val != "" else 0
                    except: 
                        pass
                
                if teacher not in st.session_state[f"allowances_{selected_month}"]:
                    st.session_state[f"allowances_{selected_month}"][teacher] = default_allowance

                col_idx = i % cols_per_row
                with cols[col_idx]:
                    st.session_state[f"allowances_{selected_month}"][teacher] = st.number_input(
                        f"🧑‍🏫 {teacher} 先生",
                        value=st.session_state[f"allowances_{selected_month}"][teacher],
                        step=500,
                        key=f"allowance_{selected_month}_{teacher}"
                    )

            st.divider()

            # --------------------------------------------------------
            # 🌟 最終的な給与計算ロジック（校舎別のコマ数集計を追加）
            # --------------------------------------------------------
            summary_list = []
            for teacher in valid_teachers:
                df_teacher = df_month_exploded[df_month_exploded['担当講師'] == teacher].copy()
                df_teacher['日付'] = df_teacher['日時'].dt.date
                
                # 🌟 校舎判定ロジック（生徒IDの頭文字から判定）
                def get_branch(sid):
                    sid = str(sid).lower()
                    if sid.startswith('t'): return '田端新町校'
                    elif sid.startswith('h'): return '東十条駅前校'
                    else: return 'その他'

                if '生徒ID' in df_teacher.columns:
                    df_teacher['校舎'] = df_teacher['生徒ID'].apply(get_branch)
                else:
                    df_teacher['校舎'] = '不明'

                # 日付とコマで重複排除（1回の授業を1コマとしてカウント）
                df_teacher_unique = df_teacher.drop_duplicates(subset=['日付', '授業コマ'])

                # 🌟 校舎別のコマ数カウント用の箱
                koma_branch = {
                    '田端新町校': {'1:1': 0, '1:2': 0, '1:3': 0},
                    '東十条駅前校': {'1:1': 0, '1:2': 0, '1:3': 0},
                    'その他': {'1:1': 0, '1:2': 0, '1:3': 0}
                }

                for _, r in df_teacher_unique.iterrows():
                    b = r.get('校舎', 'その他')
                    if b not in koma_branch: b = 'その他'
                    jt = str(r.get('授業形態', ''))
                    
                    if '1:1' in jt: koma_branch[b]['1:1'] += 1
                    elif '1:2' in jt: koma_branch[b]['1:2'] += 1
                    elif '1:3' in jt: koma_branch[b]['1:3'] += 1

                # 全体の合計コマ数を計算
                koma_11 = sum(koma_branch[b]['1:1'] for b in koma_branch)
                koma_12 = sum(koma_branch[b]['1:2'] for b in koma_branch)
                koma_13 = sum(koma_branch[b]['1:3'] for b in koma_branch)

                t_row_df = df_instructors[df_instructors["講師名"] == teacher]
                if t_row_df.empty:
                    p11, p12, p13, trans = 1500, 1800, 2000, 0
                else:
                    t_row = t_row_df.iloc[0]
                    def safe_int(val, d=0):
                        try: return int(float(val)) if not pd.isna(val) and val != "" else d
                        except: return d
                    p11 = safe_int(t_row.get('1:1単価', 1500), 1500)
                    p12 = safe_int(t_row.get('1:2単価', 1800), 1800)
                    p13 = safe_int(t_row.get('1:3単価', 2000), 2000)
                    trans = safe_int(t_row.get('交通費', 0), 0)

                current_allowance = st.session_state[f"allowances_{selected_month}"].get(teacher, 0)

                total_koma = koma_11 + koma_12 + koma_13
                koma_salary = (koma_11 * p11) + (koma_12 * p12) + (koma_13 * p13)
                working_days = df_teacher['日付'].nunique()
                transport_total = working_days * trans
                
                final_salary = koma_salary + transport_total + current_allowance

                summary_list.append({
                    "👨‍🏫 担当講師": teacher, 
                    "合計コマ数": total_koma,
                    "1:1コマ": koma_11, 
                    "1:2コマ": koma_12, 
                    "1:3コマ": koma_13, 
                    "授業給 (円)": int(koma_salary),
                    "役職手当 (円)": int(current_allowance), 
                    "出勤日数": working_days, 
                    "交通費合計 (円)": int(transport_total), 
                    "💰 最終支給額 (円)": int(final_salary),
                    
                    # 🌟 PDF明細へ渡すための詳細データ
                    "田端_1:1": koma_branch['田端新町校']['1:1'],
                    "田端_1:2": koma_branch['田端新町校']['1:2'],
                    "田端_1:3": koma_branch['田端新町校']['1:3'],
                    "東十条_1:1": koma_branch['東十条駅前校']['1:1'],
                    "東十条_1:2": koma_branch['東十条駅前校']['1:2'],
                    "東十条_1:3": koma_branch['東十条駅前校']['1:3'],
                    "単価_1:1": p11,
                    "単価_1:2": p12,
                    "単価_1:3": p13,
                    "単価_交通費": trans
                })

            if summary_list:
                df_summary = pd.DataFrame(summary_list)
                # 表示用には主要な列だけを見せる
                display_cols = ["👨‍🏫 担当講師", "合計コマ数", "1:1コマ", "1:2コマ", "1:3コマ", "授業給 (円)", "役職手当 (円)", "出勤日数", "交通費合計 (円)", "💰 最終支給額 (円)"]
                st.subheader(f"📊 {selected_month} の給与一覧（計算結果）")
                st.dataframe(df_summary[display_cols], hide_index=True, use_container_width=True)

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("📦 全員分の明細をZIP作成", use_container_width=True):
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                            for row_data in summary_list:
                                pdf_bytes = generate_payslip_pdf(row_data, selected_month)
                                zip_file.writestr(f"給与明細_{selected_month}_{row_data['👨‍🏫 担当講師']}.pdf", pdf_bytes)
                        st.download_button("📥 ZIPをダウンロード", zip_buffer.getvalue(), f"{selected_month}_給与明細.zip", "application/zip", type="primary", use_container_width=True)
                
                with c2:
                    if st.button(f"🚀 {selected_month} の給与を公開する", use_container_width=True):
                        with st.spinner("送信中..."):
                            success = robust_api_call(publish_salary_data, selected_month, df_summary[display_cols], fallback_value=False)
                            if success: st.success("✅ 公開・保存しました！")
                            else: st.error("⚠️ 送信に失敗しました。")

    # ==========================================
    # Tab 2: 講師単価・設定変更
    # ==========================================
    with tab_master:
        st.subheader("⚙️ 講師マスタの設定変更")
        
        st.markdown("##### 👤 講師ごとの個別設定（基本給・基本手当）")
        target_teacher = st.selectbox("設定を変更する講師を選択してください", ["選択してください"] + df_instructors["講師名"].tolist())
        
        if target_teacher != "選択してください":
            current_vals = df_instructors[df_instructors["講師名"] == target_teacher].iloc[0]
            
            with st.form("individual_edit_form"):
                col1, col2 = st.columns(2)
                with col1:
                    new_11 = st.number_input("1:1 単価", value=int(current_vals.get('1:1単価', 1500)), step=100)
                    new_12 = st.number_input("1:2 単価", value=int(current_vals.get('1:2単価', 1800)), step=100)
                    new_13 = st.number_input("1:3 単価", value=int(current_vals.get('1:3単価', 2000)), step=100)
                with col2:
                    new_trans = st.number_input("1日あたりの交通費", value=int(current_vals.get('交通費', 0)), step=10)
                    new_allowance = st.number_input("基本の役職手当（毎月の初期値）", value=int(current_vals.get('役職手当', 0)), step=1000)
                
                if st.form_submit_button("✅ この内容で保存する", type="primary"):
                    idx = df_instructors.index[df_instructors["講師名"] == target_teacher][0]
                    df_instructors.at[idx, '1:1単価'] = new_11
                    df_instructors.at[idx, '1:2単価'] = new_12
                    df_instructors.at[idx, '1:3単価'] = new_13
                    df_instructors.at[idx, '交通費'] = new_trans
                    df_instructors.at[idx, '役職手当'] = new_allowance
                    
                    with st.spinner("☁️ 保存中..."):
                        if robust_api_call(update_instructor_master, df_instructors, fallback_value=False):
                            st.cache_data.clear() 
                            st.session_state['toast_msg'] = f"✅ {target_teacher} 先生の基本給設定を更新しました！"
                            st.rerun()
        
        st.divider()
        st.markdown("##### 📋 講師設定一覧（確認用）")
        st.dataframe(df_instructors, hide_index=True, use_container_width=True)