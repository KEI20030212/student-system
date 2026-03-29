import streamlit as st
import pandas as pd
import math  # 👈 math.ceil（切り上げ）を使うために必須の道具です！
from utils.g_sheets import get_all_student_names, load_all_data  # 👈 スプレッドシートからの呼び出し！

def render_salary_dashboard_page():
    st.header("💰 給与・交通費ダッシュボード")
    student_names = get_all_student_names()
    if not student_names: return

    with st.expander("🏢 塾全体の「基本」コマ単価", expanded=True):
        c1, c2, c3 = st.columns(3)
        base_price_1on1 = c1.number_input("1:1 基本単価 (円)", value=1500, step=100)
        base_price_1on2 = c2.number_input("1:2 基本単価 (円)", value=1800, step=100)
        base_price_1on3 = c3.number_input("1:3 基本単価 (円)", value=2000, step=100)

    all_data_list = []
    with st.spinner('集計中...'):
        for s_name in student_names:
            df = load_all_data(s_name)
            if not df.empty:
                df['生徒名'] = s_name
                all_data_list.append(df)
    
    if not all_data_list: return
    df_all = pd.concat(all_data_list, ignore_index=True)
    if '担当講師' not in df_all.columns: return

    df_all['日時'] = pd.to_datetime(df_all['日時'], format='mixed', errors='coerce')
    df_all = df_all.dropna(subset=['日時'])
    df_all['年月'] = df_all['日時'].dt.strftime("%Y年%m月")

    month_options = sorted(df_all['年月'].unique().tolist(), reverse=True)
    selected_month = st.selectbox("📅 集計する月を選択", month_options)
    df_month = df_all[df_all['年月'] == selected_month]

    st.divider()
    st.subheader("👨‍🏫 講師ごとの「個別」単価 ＆ 交通費設定")
    teachers = df_month['担当講師'].dropna().unique()
    valid_teachers = [t for t in teachers if t not in ["未入力", ""]]

    teacher_prices_df = pd.DataFrame({
        "講師名": valid_teachers, "1:1 単価": [base_price_1on1] * len(valid_teachers),
        "1:2 単価": [base_price_1on2] * len(valid_teachers), "1:3 単価": [base_price_1on3] * len(valid_teachers),
        "1日あたりの交通費": [0] * len(valid_teachers)
    })

    edited_prices = st.data_editor(teacher_prices_df, hide_index=True, use_container_width=True)

    st.divider()
    summary_list = []
    for teacher in valid_teachers:
        df_teacher = df_month[df_month['担当講師'] == teacher]
        t_row = edited_prices[edited_prices["講師名"] == teacher].iloc[0]
        
        count_1on1 = len(df_teacher[df_teacher['授業形態'] == '1:1'])
        count_1on2 = len(df_teacher[df_teacher['授業形態'] == '1:2'])
        count_1on3 = len(df_teacher[df_teacher['授業形態'] == '1:3'])

        koma_1on1 = math.ceil(count_1on1 / 1)
        koma_1on2 = math.ceil(count_1on2 / 2)
        koma_1on3 = math.ceil(count_1on3 / 3)
        total_koma = koma_1on1 + koma_1on2 + koma_1on3
        koma_salary = (koma_1on1 * t_row["1:1 単価"]) + (koma_1on2 * t_row["1:2 単価"]) + (koma_1on3 * t_row["1:3 単価"])

        working_days = df_teacher['日時'].dt.date.nunique()
        transport_total = working_days * t_row["1日あたりの交通費"]
        final_salary = koma_salary + transport_total

        summary_list.append({
            "👨‍🏫 担当講師": teacher, "合計コマ数": total_koma, "授業給 (円)": koma_salary,
            "出勤日数": working_days, "交通費合計 (円)": transport_total, "💰 最終支給額 (円)": final_salary
        })

    if summary_list:
        df_summary = pd.DataFrame(summary_list)
        df_summary = df_summary.sort_values(by="💰 最終支給額 (円)", ascending=False)
        st.subheader(f"📊 {selected_month} の稼働・給与一覧")
        st.dataframe(df_summary, hide_index=True, use_container_width=True)