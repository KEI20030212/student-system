import streamlit as st
import pandas as pd
import math
import time
import zipfile
import io
import unicodedata # 🌟 必須！全角半角の表記ゆれを矯正する魔法

from utils.g_sheets import get_all_student_names, load_all_data, load_instructor_master, update_instructor_master
from utils.pdf_generator import generate_payslip_pdf
from utils.g_sheets import publish_salary_data

def render_salary_dashboard_page():
    st.header("💰 給与・交通費ダッシュボード")
    
    if st.button("🔄 最新の授業データを読み込み直す"):
        if 'salary_df_all' in st.session_state:
            del st.session_state['salary_df_all']
        st.cache_data.clear() 
        st.rerun()
        
    try:
        student_names = get_all_student_names()
    except Exception as e:
        st.error(f"⚠️ 生徒名リストの取得に失敗しました。再試行してください。: {e}")
        return

    if not student_names: return

    try:
        df_instructors = load_instructor_master()
    except Exception as e:
        st.warning(f"⚠️ 講師マスタが読み込めませんでした。空の状態で開始します。: {e}")
        df_instructors = pd.DataFrame(columns=["講師名", "1:1単価", "1:2単価", "1:3単価", "交通費", "役職手当"])

    with st.expander("🏢 新規講師用の「基本」コマ単価設定", expanded=False):
        c1, c2, c3 = st.columns(3)
        base_price_1on1 = c1.number_input("1:1 基本単価 (円)", value=1500, step=100)
        base_price_1on2 = c2.number_input("1:2 基本単価 (円)", value=1800, step=100)
        base_price_1on3 = c3.number_input("1:3 基本単価 (円)", value=2000, step=100)

    # --- 📊 授業データの集計 ---
    if 'salary_df_all' not in st.session_state:
        all_data_list = []
        st.subheader("☁️ データ集計状況")
        progress_text = st.empty()
        progress_bar = st.progress(0)
        total_students = len(student_names)
        
        for i, s_name in enumerate(student_names):
            progress_text.text(f"📥 {s_name} さんのデータを読み込み中... ({i+1}/{total_students})")
            success = False
            for retry in range(3):
                try:
                    df = load_all_data(s_name)
                    if not df.empty:
                        df['生徒名'] = s_name
                        all_data_list.append(df)
                    success = True
                    break 
                except Exception as e:
                    time.sleep(2) 
                    continue
            if not success:
                st.warning(f"❌ {s_name} さんのデータ読み込みに失敗しました")
            time.sleep(0.3) 
            progress_bar.progress((i + 1) / total_students)
            
        progress_bar.empty()
        progress_text.empty()
        
        if not all_data_list:
            st.error("⚠️ 有効な授業データが1件も見つかりませんでした。")
            return
        
        df_all = pd.concat(all_data_list, ignore_index=True)
        st.session_state['salary_df_all'] = df_all
    else:
        df_all = st.session_state['salary_df_all']
    
    # --- データ処理 ---
    if '担当講師' not in df_all.columns: return
    df_all['日時'] = pd.to_datetime(df_all['日時'], format='mixed', errors='coerce')
    df_all = df_all.dropna(subset=['日時'])
    df_all['年月'] = df_all['日時'].dt.strftime("%Y年%m月")

    month_options = sorted(df_all['年月'].unique().tolist(), reverse=True)
    selected_month = st.selectbox("📅 集計する月を選択", month_options)
    df_month = df_all[df_all['年月'] == selected_month].copy()

    st.divider()

    # --- セル内の改行（複数人）を分割 ---
    df_month['担当講師'] = df_month['担当講師'].astype(str)
    df_month_exploded = df_month.assign(担当講師=df_month['担当講師'].str.split(r'[\n,、]')).explode('担当講師')
    df_month_exploded['担当講師'] = df_month_exploded['担当講師'].str.strip()

    # 🌟 罠① 防御：授業形態の表記ゆれ（「１：２」や「1: 2」など）を完全に半角「1:2」に統一
    if '授業形態' in df_month_exploded.columns:
        df_month_exploded['授業形態'] = df_month_exploded['授業形態'].astype(str).apply(
            lambda x: unicodedata.normalize('NFKC', x).replace(' ', '')
        )

    teachers = df_month_exploded['担当講師'].dropna().unique()
    valid_teachers = [t for t in teachers if t not in ["未入力", "", "nan", "None"]]

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

    # --- 👨‍🏫 講師マスタ設定（変更保存ロジック） ---
    st.subheader("👨‍🏫 講師ごとの単価・設定")
    
    # 🌟 with st.form で囲むことで、入力中の通信（再読み込み）を完全にブロック！
    with st.form("master_edit_form"):
        st.info("💡 表を直接編集できます。編集後は必ず下の「保存する」ボタンを押してください。")
        edited_prices = st.data_editor(
            df_instructors, 
            hide_index=True, 
            use_container_width=True, 
            num_rows="dynamic", 
            key="instructor_editor" # エディタの記憶キー
        )
        submit_btn = st.form_submit_button("💾 変更をスプレッドシート（マスタ）に保存する", type="primary")

    if submit_btn:
        try:
            with st.spinner("☁️ マスタを保存中..."):
                update_instructor_master(edited_prices)
                time.sleep(1)
                st.cache_data.clear() 
                
                # 🌟 直った！エディタの「古い記憶」を強制的に消去して先祖返りを防ぐ
                if "instructor_editor" in st.session_state:
                    del st.session_state["instructor_editor"]
                    
            st.success("✅ 講師マスタを更新しました！")
            time.sleep(0.5)
            st.rerun() 
        except Exception as e:
            st.error(f"⚠️ 保存に失敗しました。: {e}")

    # --- 給与・コマ数計算ロジック（鉄壁版） ---
    summary_list = []
    for teacher in valid_teachers:
        df_teacher = df_month_exploded[df_month_exploded['担当講師'] == teacher].copy()
        df_teacher['日付'] = df_teacher['日時'].dt.date
        
        # 🌟 罠② 防御：空欄による集計漏れ（行の消滅）を防ぐ
        df_teacher['日付'] = df_teacher['日付'].fillna("日付不明")
        df_teacher['授業コマ'] = df_teacher['授業コマ'].fillna("コマ不明")
        
        # 🌟 罠③ 防御：同じ生徒・日付・コマの「重複（二重入力）」を排除し、コマ数の過剰カウントを防ぐ！
        if '生徒名' in df_teacher.columns:
            df_teacher = df_teacher.drop_duplicates(subset=['生徒名', '日付', '授業コマ'])

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

        # コマ数計算
        koma_11, koma_12, koma_13 = 0, 0, 0
        for (date, period), group in df_teacher.groupby(['日付', '授業コマ']):
            koma_11 += math.ceil(len(group[group['授業形態'] == '1:1']) / 1)
            koma_12 += math.ceil(len(group[group['授業形態'] == '1:2']) / 2)
            koma_13 += math.ceil(len(group[group['授業形態'] == '1:3']) / 3)

        total_koma = koma_11 + koma_12 + koma_13
        koma_salary = (koma_11 * p11) + (koma_12 * p12) + (koma_13 * p13)
        
        # 出勤日数は「日付不明」を除いてカウント
        valid_dates = [d for d in df_teacher['日付'].unique() if str(d) != "日付不明"]
        working_days = len(valid_dates)
        
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