import streamlit as st
import pandas as pd
import time
import re
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

    actual_koma_dict = {s: len(df_month[df_month['生徒名'] == s]) for s in student_names}
    saved_billing_df = load_billing_data(selected_month)

    table_data = []
    for student in student_names:
        actual_koma = actual_koma_dict.get(student, 0)
        
        m_info = student_master.get(student, {"学年": "未設定", "契約コース": "未設定", "特別割引コマ": 0})
        grade = str(m_info["学年"]).strip()
        master_course = str(m_info["契約コース"]).strip()
        
        raw_discount = str(m_info.get("特別割引コマ", "0")).strip()
        discount_nums = re.findall(r'\d+', raw_discount)
        discount_koma = int(discount_nums[0]) if discount_nums else 0

        # --- 🌟ここから修正：必ず最新の追加コマを再計算するロジック ---
        course = master_course
        saved_price = None
        saved_extra_count = 0
        
        # ① もし保存データがあれば、以前の金額や設定を一旦読み込む
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

        # ② 最新の「実際の受講数」をもとに、ベースコマと追加コマを常に計算し直す
        try:
            koma_nums = re.findall(r'\d+', course)
            base_koma = int(koma_nums[0]) if koma_nums else 0
        except:
            base_koma = 0
            
        actual_extra_count = max(0, actual_koma - base_koma)
        
        # ③ マスタから料金を取得し、最新の理論価格を計算する
        match = price_master[(price_master['学年'] == grade) & (price_master['コマ数'] == base_koma)]
        if not match.empty:
            base_price = int(match.iloc[0]['料金'])
            unit_extra_price = int(match.iloc[0]['追加単価'])
        else:
            base_price = 15000 
            unit_extra_price = 3000 
            
        discount_amount = discount_koma * unit_extra_price
        calculated_price = max(0, base_price + (actual_extra_count * unit_extra_price) - discount_amount)

        # ④ 最終金額の決定：もし保存時から追加コマ数に変動があれば最新の計算結果を強制適用！
        if saved_price is not None and actual_extra_count == saved_extra_count:
            price = saved_price # 変動がなければ、手入力修正されているかもしれない保存金額をキープ
        else:
            price = calculated_price # 追加コマ数が増えていたら再計算！

        table_data.append({
            "👤 生徒名": student,
            "🎓 学年": grade,
            "📚 契約コース": course,
            "📝 実際の受講数": actual_koma,
            "➕ 追加コマ": actual_extra_count, # 🌟常に最新！
            "🉐 割引コマ": discount_koma, 
            "💴 今月の請求額 (円)": int(price)
        })
    
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