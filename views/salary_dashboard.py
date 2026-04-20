import streamlit as st
import pandas as pd
import math
import time
import zipfile
import io
import unicodedata

from utils.g_sheets import get_all_student_names, load_all_data, load_instructor_master, update_instructor_master
from utils.pdf_generator import generate_payslip_pdf
from utils.g_sheets import publish_salary_data

def render_salary_dashboard_page():
    st.header("💰 給与・交通費ダッシュボード")
    
    # 1. 講師マスタの読み込み（一番最初に、かつ独立して行う）
    try:
        # 🌟 ここで確実に最新のマスタを取る
        df_instructors = load_instructor_master()
    except Exception as e:
        st.error(f"⚠️ 講師マスタが読み込めませんでした。通信状況を確認してください。: {e}")
        df_instructors = pd.DataFrame(columns=["講師名", "1:1単価", "1:2単価", "1:3単価", "交通費", "役職手当"])

    # --- 👨‍🏫 講師ごとの単価・設定（ここを一番上に持ってくることで、消えるのを防ぐ） ---
    st.subheader("👨‍🏫 講師ごとの単価・設定")
    
    # 🌟 罠回避：formとeditorを確実に同期させる
    with st.form("master_edit_form"):
        st.info("💡 単価を変更した後は、必ず下の「保存する」ボタンを押してください。")
        # editorの結果を直接変数に受ける
        current_editor_df = st.data_editor(
            df_instructors, 
            hide_index=True, 
            use_container_width=True, 
            num_rows="dynamic",
            key="master_editor_key" # 固定キーを持たせる
        )
        submit_btn = st.form_submit_button("💾 変更をスプレッドシート（マスタ）に保存する", type="primary")

    if submit_btn:
        try:
            with st.spinner("☁️ スプレッドシートに保存中..."):
                # 🌟 current_editor_df（編集後のデータ）を直接渡す
                update_instructor_master(current_editor_df)
                st.cache_data.clear() # 記憶をリセット
                # 🌟 保存成功後に少し待ってからリロード
                time.sleep(1)
            st.success("✅ スプレッドシートを更新しました！")
            st.rerun() 
        except Exception as e:
            st.error(f"⚠️ 保存に失敗しました。: {e}")

    st.divider()

    # --- 📊 授業データの集計セクション ---
    # ここでエラーが起きても、上の「マスタ設定」は消えなくなります。
    
    if st.button("🔄 最新の授業データを読み込み直す"):
        if 'salary_df_all' in st.session_state:
            del st.session_state['salary_df_all']
        st.cache_data.clear() 
        st.rerun()

    # 生徒名リスト取得（リトライ機能付き）
    student_names = []
    try:
        student_names = get_all_student_names()
    except Exception as e:
        st.warning(f"⚠️ 生徒データの取得で一時的なエラーが発生しました。再読み込みボタンを押してください。: {e}")
        # ここで return せず、下の処理を条件付きで止める

    if not student_names:
        st.info("生徒データが読み込まれていません。上の「最新の授業データを読み込み直す」を押してください。")
        return # ここから下（集計結果）だけを表示しない

    # --- 以降、データの集計・表示処理 ---
    if 'salary_df_all' not in st.session_state:
        all_data_list = []
        st.subheader("☁️ データ集計状況")
        p_bar = st.progress(0)
        t_status = st.empty()
        
        for i, s_name in enumerate(student_names):
            t_status.text(f"📥 {s_name} さんのデータを読み込み中... ({i+1}/{len(student_names)})")
            try:
                df = load_all_data(s_name)
                if not df.empty:
                    df['生徒名'] = s_name
                    all_data_list.append(df)
            except:
                pass
            p_bar.progress((i + 1) / len(student_names))
        
        t_status.empty()
        p_bar.empty()
        
        if all_data_list:
            df_all = pd.concat(all_data_list, ignore_index=True)
            st.session_state['salary_df_all'] = df_all
        else:
            st.error("有効な授業データが見つかりませんでした。")
            return
    else:
        df_all = st.session_state['salary_df_all']

    # --- 計算ロジック ---
    df_all['日時'] = pd.to_datetime(df_all['日時'], format='mixed', errors='coerce')
    df_all = df_all.dropna(subset=['日時'])
    df_all['年月'] = df_all['日時'].dt.strftime("%Y年%m月")

    month_options = sorted(df_all['年月'].unique().tolist(), reverse=True)
    selected_month = st.selectbox("📅 集計する月を選択", month_options)
    df_month = df_all[df_all['年月'] == selected_month].copy()

    # 表記ゆれ・改行対策
    df_month['担当講師'] = df_month['担当講師'].astype(str)
    df_month_exploded = df_month.assign(担当講師=df_month['担当講師'].str.split(r'[\n,、]')).explode('担当講師')
    df_month_exploded['担当講師'] = df_month_exploded['担当講師'].str.strip()
    
    if '授業形態' in df_month_exploded.columns:
        df_month_exploded['授業形態'] = df_month_exploded['授業形態'].astype(str).apply(
            lambda x: unicodedata.normalize('NFKC', x).replace(' ', '')
        )

    valid_teachers = [t for t in df_month_exploded['担当講師'].unique() if t not in ["未入力", "", "nan", "None"]]

    summary_list = []
    for teacher in valid_teachers:
        df_teacher = df_month_exploded[df_month_exploded['担当講師'] == teacher].copy()
        df_teacher['日付'] = df_teacher['日時'].dt.date
        
        # 重複排除（同じ生徒・同じ日・同じコマ）
        df_teacher = df_teacher.drop_duplicates(subset=['生徒名', '日付', '授業コマ'])

        # マスタから単価取得（保存済みの df_instructors を使用）
        t_row_df = df_instructors[df_instructors["講師名"] == teacher]
        if t_row_df.empty: continue
        t_row = t_row_df.iloc[0]

        def safe_int(val, default=0):
            try: return int(float(val)) if not pd.isna(val) and val != "" else default
            except: return default

        p11 = safe_int(t_row.get('1:1単価', 1500), 1500)
        p12 = safe_int(t_row.get('1:2単価', 1800), 1800)
        p13 = safe_int(t_row.get('1:3単価', 2000), 2000)
        trans = safe_int(t_row.get('交通費', 0), 0)
        allowance = safe_int(t_row.get('役職手当', 0), 0)

        koma_11, koma_12, koma_13 = 0, 0, 0
        for _, group in df_teacher.groupby(['日付', '授業コマ']):
            # 🌟 ここが重要：グループ内の授業形態を判別して正しくコマを割る
            koma_11 += math.ceil(len(group[group['授業形態'] == '1:1']) / 1)
            koma_12 += math.ceil(len(group[group['授業形態'] == '1:2']) / 2)
            koma_13 += math.ceil(len(group[group['授業形態'] == '1:3']) / 3)

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

    # --- 結果表示とPDF/公開セクション ---
    if summary_list:
        df_summary = pd.DataFrame(summary_list)
        df_summary = df_summary.sort_values(by="💰 最終支給額 (円)", ascending=False)
        st.subheader(f"📊 {selected_month} の稼働・給与一覧")
        st.dataframe(df_summary, hide_index=True, use_container_width=True)

        st.divider()
        st.subheader("📄 給与明細PDFの一括作成")
        
        if st.button(f"📦 全員分の明細をZIPで作成する", use_container_width=True):
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                p_bar_zip = st.progress(0)
                for j, row_data in enumerate(summary_list):
                    pdf_bytes = generate_payslip_pdf(row_data, selected_month)
                    file_name = f"給与明細_{selected_month}_{row_data['👨‍🏫 担当講師']}.pdf"
                    zip_file.writestr(file_name, pdf_bytes)
                    p_bar_zip.progress((j + 1) / len(summary_list))
                p_bar_zip.empty()
            
            st.download_button(
                label="📥 ZIPファイルをダウンロード",
                data=zip_buffer.getvalue(),
                file_name=f"{selected_month}_給与明細一括.zip",
                mime="application/zip",
                type="primary",
                use_container_width=True
            )

        st.divider()
        st.subheader("📢 先生のページへ給与データを公開")
        
        if st.button(f"🚀 {selected_month} の給与を確定して公開する", use_container_width=True):
            try:
                with st.spinner("☁️ データを送信中..."):
                    publish_salary_data(selected_month, df_summary)
                    time.sleep(1)
                st.success(f"✅ {selected_month} のデータを公開しました！")
            except Exception as e:
                st.error(f"⚠️ 公開に失敗しました。: {e}")