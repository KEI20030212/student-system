import streamlit as st
import pandas as pd
import time
import re
import unicodedata # 🌟全角半角の文字揺れを直すための標準機能
from utils.g_sheets import (
    get_all_student_names, 
    load_all_data, 
    load_billing_data, 
    save_billing_data,
    get_student_master_data,
    load_price_master
)
from utils.pdf_generator import generate_invoice_pdf

def render_tuition_dashboard_page():
    st.header("💴 月謝（請求額）管理ダッシュボード")
    
    # --- データ準備 ---
    student_names = get_all_student_names()
    student_master = get_student_master_data()
    price_master = load_price_master()
    
    if not student_names: 
        st.warning("生徒データが見つかりません。")
        return

    # 🌟【重要】マスタデータの「ゆらぎ（全角半角、文字と数字の違い）」をここで強制的に統一！
    if not price_master.empty:
        price_master['学年'] = price_master['学年'].astype(str).apply(lambda x: unicodedata.normalize('NFKC', x).strip())
        price_master['コマ数'] = pd.to_numeric(price_master['コマ数'], errors='coerce').fillna(0).astype(int)

    # プログレスバーで授業データを集計
    all_data_list = []
    total_students = len(student_names)
    st.caption("🔄 最新の授業データを取得中...")
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, s_name in enumerate(student_names):
        status_text.text(f"集計中 ({i+1}/{total_students}) : {s_name}")
        try:
            df = load_all_data(s_name)
            if not df.empty:
                df['生徒名'] = s_name
                all_data_list.append(df)
        except:
            pass
        progress_bar.progress((i + 1) / total_students)
        time.sleep(0.3)

    progress_bar.empty()
    status_text.empty()
    
    if all_data_list:
        df_all = pd.concat(all_data_list, ignore_index=True)
        df_all['日時'] = pd.to_datetime(df_all['日時'], format='mixed', errors='coerce')
        df_all = df_all.dropna(subset=['日時'])
        df_all['年月'] = df_all['日時'].dt.strftime("%Y年%m月")
        month_options = sorted(df_all['年月'].unique().tolist(), reverse=True)
    else:
        from datetime import datetime
        month_options = [datetime.now().strftime("%Y年%m月")]

    selected_month = st.selectbox("📅 請求月を選択", month_options)
    
    if all_data_list:
        df_month = df_all[df_all['年月'] == selected_month]
    else:
        df_month = pd.DataFrame(columns=['生徒名'])

    st.divider()
    st.subheader(f"👤 {selected_month} の請求設定")

    # 🌟【新機能】マスタ変更時などに、強制的に最新のマスタ料金で計算し直すスイッチ
    force_recalc = st.checkbox("🔄 過去の保存データを無視して、現在の料金マスタで強制的に再計算する")

    actual_koma_dict = {s: len(df_month[df_month['生徒名'] == s]) for s in student_names}
    saved_billing_df = load_billing_data(selected_month)

    table_data = []
    missing_master_warnings = [] # マスタに見つからなかった生徒の警告用

    for student in student_names:
        actual_koma = actual_koma_dict.get(student, 0)
        
        m_info = student_master.get(student, {"学年": "未設定", "契約コース": "未設定", "特別割引コマ": 0})
        # 検索キーも全角半角を統一する
        grade = unicodedata.normalize('NFKC', str(m_info["学年"])).strip()
        master_course = unicodedata.normalize('NFKC', str(m_info["契約コース"])).strip()
        
        raw_discount = str(m_info.get("特別割引コマ", "0")).strip()
        discount_nums = re.findall(r'\d+', raw_discount)
        discount_koma = int(discount_nums[0]) if discount_nums else 0

        course = master_course
        saved_price = None
        saved_extra_count = 0
        
        # ① 保存データの読み込み
        if not saved_billing_df.empty and student in saved_billing_df['👤 生徒名'].values:
            row = saved_billing_df[saved_billing_df['👤 生徒名'] == student].iloc[0]
            course = next((row[c] for c in saved_billing_df.columns if "契約コース" in c), master_course)
            saved_price = next((row[c] for c in saved_billing_df.columns if "請求額" in c), None)
            
            try:
                saved_extra_count = int(next((row[c] for c in saved_billing_df.columns if "追加コマ" in c), 0))
            except:
                saved_extra_count = 0

            try:
                discount_koma = int(next((row[c] for c in saved_billing_df.columns if "割引コマ" in c), discount_koma))
            except:
                pass

        # ② 最新のベースコマと追加コマの計算
        try:
            koma_nums = re.findall(r'\d+', course)
            base_koma = int(koma_nums[0]) if koma_nums else 0
        except:
            base_koma = 0
            
        actual_extra_count = max(0, actual_koma - base_koma)
        
        # ③ マスタからの料金取得（型を完全に合わせて検索）
        match = price_master[(price_master['学年'] == grade) & (price_master['コマ数'] == base_koma)]
        
        if not match.empty:
            base_price = int(match.iloc[0]['料金'])
            unit_extra_price = int(match.iloc[0]['追加単価'])
        else:
            # 🌟 マスタに見つからない場合は警告リストに追加し、金額を0にする
            missing_master_warnings.append(f"{student} さん (学年: {grade}, コマ数: {base_koma})")
            base_price = 0 
            unit_extra_price = 0 
            
        discount_amount = discount_koma * unit_extra_price
        calculated_price = max(0, base_price + (actual_extra_count * unit_extra_price) - discount_amount)

        # ④ 最終金額の決定（強制再計算のチェックが入っていれば、マスタ価格を最優先）
        if force_recalc:
            price = calculated_price
        elif saved_price is not None and actual_extra_count == saved_extra_count:
            price = saved_price
        else:
            price = calculated_price 

        table_data.append({
            "👤 生徒名": student,
            "🎓 学年": grade,
            "📚 契約コース": course,
            "📝 実際の受講数": actual_koma,
            "➕ 追加コマ": actual_extra_count,
            "🉐 割引コマ": discount_koma, 
            "💴 今月の請求額 (円)": int(price)
        })
    
    # ⚠️ もし料金マスタに該当しないデータがあれば画面に警告を表示！
    if missing_master_warnings:
        st.error("以下の生徒の料金設定が「料金マスタ」に見つかりません。マスタの設定（学年・コマ数）を確認してください。")
        for w in missing_master_warnings:
            st.write(f"- {w}")

    display_df = pd.DataFrame(table_data)

    with st.form("billing_form"):
        edited_df = st.data_editor(
            display_df,
            hide_index=True,
            use_container_width=True,
            disabled=["👤 生徒名", "🎓 学年", "📝 実際の受講数", "➕ 追加コマ", "🉐 割引コマ"] 
        )
        submitted = st.form_submit_button("💾 確定して保存", use_container_width=True)
                
        if submitted:
            with st.spinner("保存中..."):
                save_df = edited_df.drop(columns=["📝 実際の受講数"])
                if save_billing_data(selected_month, save_df):
                    st.success("✅ 保存しました！")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ 保存に失敗しました。")

    st.divider()
    total = edited_df["💴 今月の請求額 (円)"].sum()
    st.metric(label=f"🌟 {selected_month} の合計請求額", value=f"{total:,} 円")

    # --- 📄 PDF発行セクション ---
    st.divider()
    st.subheader("📄 請求書PDFの発行")
    target_student = st.selectbox("請求書を発行する生徒を選択してください", student_names)
    
    if target_student:
        pdf_data = edited_df[edited_df["👤 生徒名"] == target_student].to_dict('records')[0]
        
        try:
            pdf_file = generate_invoice_pdf(pdf_data, selected_month)
            st.download_button(
                label=f"📥 {target_student} 様の請求書をダウンロード",
                data=pdf_file,
                file_name=f"請求書_{selected_month}_{target_student}.pdf",
                mime="application/pdf"
            )
        except Exception as e:
            st.error(f"PDF生成エラー: {e}")