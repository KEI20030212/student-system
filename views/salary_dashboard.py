import streamlit as st
import pandas as pd
import math
from utils.g_sheets import get_all_student_names, load_all_data, load_instructor_master, update_instructor_master # 👈 updateも追加！
from utils.pdf_generator import generate_payslip_pdf

def render_salary_dashboard_page():
    st.header("💰 給与・交通費ダッシュボード")
    
    # 1. データのロード
    student_names = get_all_student_names()
    if not student_names: return

    # 🌟 講師マスタを読み込む
    df_instructors = load_instructor_master()
    if df_instructors.empty:
        # マスタが空の場合の仮データ（列の枠組みだけ作る）
        df_instructors = pd.DataFrame(columns=["講師名", "1:1単価", "1:2単価", "1:3単価", "交通費", "役職手当"])

    with st.expander("🏢 新規講師用の「基本」コマ単価設定", expanded=False):
        st.caption("※マスタに登録されていない新しい先生が今月いた場合、この基本単価が初期セットされます。")
        c1, c2, c3 = st.columns(3)
        base_price_1on1 = c1.number_input("1:1 基本単価 (円)", value=1500, step=100)
        base_price_1on2 = c2.number_input("1:2 基本単価 (円)", value=1800, step=100)
        base_price_1on3 = c3.number_input("1:3 基本単価 (円)", value=2000, step=100)

    # 授業データの集計
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

    # 今月稼働した先生のリストを取得
    teachers = df_month['担当講師'].dropna().unique()
    valid_teachers = [t for t in teachers if t not in ["未入力", ""]]

    # 🌟 ここがポイント！今月稼働したのにマスタにいない先生を自動追加する
    master_teacher_names = df_instructors['講師名'].tolist() if not df_instructors.empty else []
    new_rows = []
    for t in valid_teachers:
        if t not in master_teacher_names:
            new_rows.append({
                "講師名": t, "1:1単価": base_price_1on1, "1:2単価": base_price_1on2, 
                "1:3単価": base_price_1on3, "交通費": 0, "役職手当": 0
            })
    
    if new_rows:
        df_instructors = pd.concat([df_instructors, pd.DataFrame(new_rows)], ignore_index=True)

    st.subheader("👨‍🏫 講師ごとの単価・設定（ここで直接編集できます！）")
    
    # 🌟 data_editor でマスタの情報を直接いじれるようにする！
    edited_prices = st.data_editor(df_instructors, hide_index=True, use_container_width=True, num_rows="dynamic")

    # 🌟 保存ボタン
    if st.button("💾 変更をスプレッドシート（マスタ）に保存する"):
        update_instructor_master(edited_prices)
        st.success("✅ 講師マスタを更新しました！次回の計算からはこの設定が適用されます。")

    st.divider()

    # 計算ループ（正確なコマ数計算）
    summary_list = []
    for teacher in valid_teachers:
        df_teacher = df_month[df_month['担当講師'] == teacher].copy()
        df_teacher['日付'] = df_teacher['日時'].dt.date
        
        # 画面の表（edited_prices）から先生の行を引っ張る
        t_row_df = edited_prices[edited_prices["講師名"] == teacher]
        if t_row_df.empty: continue
        t_row = t_row_df.iloc[0]

        p11 = t_row.get('1:1単価', 1500)
        p12 = t_row.get('1:2単価', 1800)
        p13 = t_row.get('1:3単価', 2000)
        trans = t_row.get('交通費', 0)
        allowance = t_row.get('役職手当', 0)

        # 高精度コマ数計算
        koma_11, koma_12, koma_13 = 0, 0, 0
        if '授業コマ' in df_teacher.columns:
            for (date, period), group in df_teacher.groupby(['日付', '授業コマ']):
                koma_11 += math.ceil(len(group[group['授業形態'] == '1:1']) / 1)
                koma_12 += math.ceil(len(group[group['授業形態'] == '1:2']) / 2)
                koma_13 += math.ceil(len(group[group['授業形態'] == '1:3']) / 3)
        else:
            koma_11 = math.ceil(len(df_teacher[df_teacher['授業形態'] == '1:1']) / 1)
            koma_12 = math.ceil(len(df_teacher[df_teacher['授業形態'] == '1:2']) / 2)
            koma_13 = math.ceil(len(df_teacher[df_teacher['授業形態'] == '1:3']) / 3)

        total_koma = koma_11 + koma_12 + koma_13
        koma_salary = (koma_11 * p11) + (koma_12 * p12) + (koma_13 * p13)

        working_days = df_teacher['日付'].nunique()
        transport_total = working_days * trans
        final_salary = koma_salary + transport_total + allowance

        summary_list.append({
            "👨‍🏫 担当講師": teacher, "合計コマ数": total_koma, "授業給 (円)": int(koma_salary),
            "役職手当 (円)": int(allowance), "出勤日数": working_days, 
            "交通費合計 (円)": int(transport_total), "💰 最終支給額 (円)": int(final_salary)
        })

    if summary_list:
        df_summary = pd.DataFrame(summary_list)
        df_summary = df_summary.sort_values(by="💰 最終支給額 (円)", ascending=False)
        st.subheader(f"📊 {selected_month} の稼働・給与一覧")
        st.dataframe(df_summary, hide_index=True, use_container_width=True)

        # === views/salary_dashboard.py の一番最後に追加 ===
        st.divider()
        st.subheader("📄 給与明細PDFの自動発行")
        st.write("各先生の給与明細をPDFでダウンロードできます。")
    
        # ボタンを横に並べるためのコンテナ
        col_count = 3 # 3列で並べる
        cols = st.columns(col_count)
        for i, row_data in enumerate(summary_list):
            # PDFデータを生成
            pdf_bytes = generate_payslip_pdf(row_data, selected_month)
            
            # 順番にカラムにボタンを配置
            with cols[i % col_count]:
                st.download_button(
                    label=f"📥 {row_data['👨‍🏫 担当講師']} 先生",
                    data=pdf_bytes,
                    file_name=f"給与明細_{selected_month}_{row_data['👨‍🏫 担当講師']}.pdf",
                    mime="application/pdf",
                    key=f"pdf_{row_data['👨‍🏫 担当講師']}" # ボタンの重複エラーを防ぐキー
                    )