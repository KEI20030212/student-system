import streamlit as st
import pandas as pd
import math
import time # 🌟 必須！APIエラー防止の息継ぎ用に追加

from utils.g_sheets import get_all_student_names, load_all_data, load_instructor_master, update_instructor_master
from utils.pdf_generator import generate_payslip_pdf # 👈 PDF職人もバッチリ読み込み！
from utils.g_sheets import publish_salary_data

def render_salary_dashboard_page():
    st.header("💰 給与・交通費ダッシュボード")
    
    # 🔄 最新データ再読み込みボタン
    if st.button("🔄 最新の授業データを読み込み直す"):
        if 'salary_df_all' in st.session_state:
            del st.session_state['salary_df_all'] # 記憶を消去
        st.rerun() # 画面を再読み込み
        
    # 1. データのロード
    student_names = get_all_student_names()
    if not student_names: return

    # 講師マスタを読み込む
    df_instructors = load_instructor_master()
    if df_instructors.empty:
        df_instructors = pd.DataFrame(columns=["講師名", "1:1単価", "1:2単価", "1:3単価", "交通費", "役職手当"])

    with st.expander("🏢 新規講師用の「基本」コマ単価設定", expanded=False):
        st.caption("※マスタに登録されていない新しい先生が今月いた場合、この基本単価が初期セットされます。")
        c1, c2, c3 = st.columns(3)
        base_price_1on1 = c1.number_input("1:1 基本単価 (円)", value=1500, step=100)
        base_price_1on2 = c2.number_input("1:2 基本単価 (円)", value=1800, step=100)
        base_price_1on3 = c3.number_input("1:3 基本単価 (円)", value=2000, step=100)

    # 授業データの集計
    if 'salary_df_all' not in st.session_state:
        all_data_list = []
        with st.spinner('☁️ 生徒の授業データを集計中...（APIエラー防止のため、少しずつ読み込みます☕）'):
            progress_bar = st.progress(0)
            total_students = len(student_names)
            
            for i, s_name in enumerate(student_names):
                df = load_all_data(s_name)
                if not df.empty:
                    df['生徒名'] = s_name
                    all_data_list.append(df)
                
                time.sleep(0.5) # 息継ぎ
                progress_bar.progress((i + 1) / total_students)
                
            progress_bar.empty()
            
        if not all_data_list: return
        
        # 読み込んだデータを一つにまとめて、Streamlitの脳内に記憶させる🧠
        df_all = pd.concat(all_data_list, ignore_index=True)
        st.session_state['salary_df_all'] = df_all
        
    else:
        # 既に記憶していれば、APIを使わずに脳内から一瞬で取り出す！⚡
        df_all = st.session_state['salary_df_all']
    
    if '担当講師' not in df_all.columns: return

    df_all['日時'] = pd.to_datetime(df_all['日時'], format='mixed', errors='coerce')
    df_all = df_all.dropna(subset=['日時'])
    df_all['年月'] = df_all['日時'].dt.strftime("%Y年%m月")

    month_options = sorted(df_all['年月'].unique().tolist(), reverse=True)
    selected_month = st.selectbox("📅 集計する月を選択", month_options)
    df_month = df_all[df_all['年月'] == selected_month]

    st.divider()

    teachers = df_month['担当講師'].dropna().unique()
    valid_teachers = [t for t in teachers if t not in ["未入力", ""]]

    # 今月稼働したのにマスタにいない先生を自動追加
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

    st.subheader("👨‍🏫 講師ごとの単価・設定")
    with st.form("master_edit_form"):
        edited_prices = st.data_editor(df_instructors, hide_index=True, use_container_width=True, num_rows="dynamic")

        # 🌟 st.button ではなく st.form_submit_button に変えるのがポイント！
        submit_btn = st.form_submit_button("💾 変更をスプレッドシート（マスタ）に保存する")

    # 保存ボタンが押された時だけの処理
    if submit_btn:
        with st.spinner("☁️ マスタを保存中...（連打しないでね）"):
            update_instructor_master(edited_prices)
            time.sleep(1) # 息継ぎ
            st.cache_data.clear() # 古い記憶を消去
        st.success("✅ 講師マスタを更新しました！次回の計算からはこの設定が適用されます。")
        time.sleep(1.5) # メッセージを見せるための待機
        st.rerun() # リロードして画面をスッキリ最新状態に！

    st.divider()

    # 計算ループ
    summary_list = []
    for teacher in valid_teachers:
        df_teacher = df_month[df_month['担当講師'] == teacher].copy()
        df_teacher['日付'] = df_teacher['日時'].dt.date
        
        t_row_df = edited_prices[edited_prices["講師名"] == teacher]
        if t_row_df.empty: continue
        t_row = t_row_df.iloc[0]

        def safe_int(val, default=0):
            try:
                if pd.isna(val) or val == "": 
                    return default
                return int(float(val))
            except:
                return default

        p11 = safe_int(t_row.get('1:1単価', 1500), 1500)
        p12 = safe_int(t_row.get('1:2単価', 1800), 1800)
        p13 = safe_int(t_row.get('1:3単価', 2000), 2000)
        trans = safe_int(t_row.get('交通費', 0), 0)
        allowance = safe_int(t_row.get('役職手当', 0), 0)

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

    # 結果表示とPDFボタン
    if summary_list:
        df_summary = pd.DataFrame(summary_list)
        df_summary = df_summary.sort_values(by="💰 最終支給額 (円)", ascending=False)
        st.subheader(f"📊 {selected_month} の稼働・給与一覧")
        st.dataframe(df_summary, hide_index=True, use_container_width=True)

        st.divider()
        st.subheader("📄 給与明細PDFの自動発行")

        # --- 🌟 神アイデア：塾長専用！「全員分の一括ZIPダウンロード」 ---
        st.write("💡 **管理者用：** 全員の明細を1つのフォルダ（ZIP）にまとめて一括ダウンロードします。")
        
        import zipfile
        import io
        
        # ZIPファイルを作る準備
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for row_data in summary_list:
                pdf_bytes = generate_payslip_pdf(row_data, selected_month)
                file_name = f"給与明細_{selected_month}_{row_data['👨‍🏫 担当講師']}.pdf"
                zip_file.writestr(file_name, pdf_bytes)
        
        st.download_button(
            label=f"📦 【一括作成】{selected_month}の全員分の明細をZIPでダウンロード",
            data=zip_buffer.getvalue(),
            file_name=f"{selected_month}_給与明細一括.zip",
            mime="application/zip",
            type="primary", 
            use_container_width=True 
        )

        st.write("---")
        
        # --- 🌟 先生のアイデア：プルダウン式の個別ダウンロード ---
        st.write("👤 **個別発行（先生を指定してダウンロード）**")
        
        teacher_names = [row['👨‍🏫 担当講師'] for row in summary_list]
        selected_teacher_for_pdf = st.selectbox("👩‍🏫 明細を発行する先生を選択してください", teacher_names)
        
        if selected_teacher_for_pdf:
            selected_data = next(item for item in summary_list if item['👨‍🏫 担当講師'] == selected_teacher_for_pdf)
            pdf_bytes_single = generate_payslip_pdf(selected_data, selected_month)
            
            st.download_button(
                label=f"📥 {selected_teacher_for_pdf} 先生の明細をダウンロード",
                data=pdf_bytes_single,
                file_name=f"給与明細_{selected_month}_{selected_teacher_for_pdf}.pdf",
                mime="application/pdf"
            )
        
        st.divider()
        st.subheader("📢 先生のページへ給与データを公開")
        st.info("※給与が確定したら、以下のボタンを押して先生たちの「自分の給与確認」ページにデータを送ってください。")
        
        if st.button(f"🚀 {selected_month} の給与を確定して公開する", use_container_width=True):
            with st.spinner("☁️ 先生たちのページにデータを送信中..."):
                publish_salary_data(selected_month, df_summary)
                time.sleep(1)
            st.success(f"✅ {selected_month} の給与データを公開しました！先生が自分のアカウントで確認・PDFダウンロードできるようになりました。")