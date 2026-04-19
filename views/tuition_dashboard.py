import streamlit as st
import pandas as pd
import time
from fpdf import FPDF
import io
import re
from utils.g_sheets import (
    get_all_student_names, 
    load_all_data, 
    load_billing_data, 
    save_billing_data,
    get_student_master_data, # 名前を変更
    load_price_master
)

def generate_invoice_pdf(student_name, month, amount, course, extra, discount_koma):
    """請求書PDFをバイナリで生成する"""
    pdf = FPDF()
    pdf.add_page()
    # 日本語フォントの設定（環境に合わせてパスを指定してください）
    # pdf.add_font("IPAexG", "", "font/ipaexg.ttf") 
    # pdf.set_font("IPAexG", size=16)
    
    pdf.cell(200, 10, txt=f"{month}分 授業料請求書", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    pdf.cell(200, 10, txt=f"Guest: {student_name} 様", ln=True)
    pdf.cell(200, 10, txt=f"Total Amount: {amount:,} yen", ln=True)
    pdf.ln(5)
    pdf.cell(200, 10, txt=f"Details:", ln=True)
    pdf.cell(200, 10, txt=f"- Course: {course}", ln=True)
    if extra > 0:
        pdf.cell(200, 10, txt=f"- Extra Lessons: {extra}", ln=True)
    if discount_koma > 0:
        pdf.cell(200, 10, txt=f"- Free Lessons: -{discount_koma}", ln=True)
        
    return pdf.output()

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
    
    # 授業データが全くない場合でも、空のDFを作って進めるように修正
    if all_data_list:
        df_all = pd.concat(all_data_list, ignore_index=True)
        df_all['日時'] = pd.to_datetime(df_all['日時'], format='mixed', errors='coerce')
        df_all = df_all.dropna(subset=['日時'])
        df_all['年月'] = df_all['日時'].dt.strftime("%Y年%m月")
        month_options = sorted(df_all['年月'].unique().tolist(), reverse=True)
    else:
        # 授業データが1件もない場合の予備
        from datetime import datetime
        month_options = [datetime.now().strftime("%Y年%m月")]

    selected_month = st.selectbox("📅 請求月を選択", month_options)
    
    # 選択された月の授業データだけに絞り込む
    if all_data_list:
        df_month = df_all[df_all['年月'] == selected_month]
    else:
        df_month = pd.DataFrame(columns=['生徒名'])

    st.divider()
    st.subheader(f"👤 {selected_month} の請求設定")

    # 実受講数のカウント
    actual_koma_dict = {s: len(df_month[df_month['生徒名'] == s]) for s in student_names}
    
    # 既存の保存済みデータ
    saved_billing_df = load_billing_data(selected_month)

    table_data = []
    for student in student_names:
        actual_koma = actual_koma_dict.get(student, 0)
        m_info = student_master.get(student, {"学年": "未設定", "契約コース": "未設定"})
        grade = str(m_info["学年"]).strip()
        master_course = str(m_info["契約コース"]).strip()
        
        # 保存済みデータがある場合
        if not saved_billing_df.empty and student in saved_billing_df['👤 生徒名'].values:
            row = saved_billing_df[saved_billing_df['👤 生徒名'] == student].iloc[0]
            course = next((row[c] for c in saved_billing_df.columns if "契約コース" in c), master_course)
            price = next((row[c] for c in saved_billing_df.columns if "請求額" in c), 0)
            extra_count = next((row[c] for c in saved_billing_df.columns if "追加コマ" in c), 0)
        
        # 保存データがない（新規計算）の場合
        else:
            course = master_course
            # 1. 契約コマ数を取得 (例: "月8回" -> 8)
            try:
                import re
                koma_nums = re.findall(r'\d+', course)
                base_koma = int(koma_nums[0]) if koma_nums else 0
            except:
                base_koma = 0
            
            # 2. 基本料金と追加単価をマスタから取得
            match = price_master[(price_master['学年'] == grade) & (price_master['コマ数'] == base_koma)]
            
            if not match.empty:
                base_price = int(match.iloc[0]['料金'])
                unit_extra_price = int(match.iloc[0]['追加単価'])
            else:
                base_price = 15000 # マスタにない場合のデフォルト
                unit_extra_price = 3000 # 追加単価のデフォルト
            
            # 3. 追加コマ数の計算 (実際の受講数 - 契約コマ数) ※マイナスにはしない
            extra_count = max(0, actual_koma - base_koma)
            
            discount_koma = m_info.get("特別割引コマ", 0)
            discount_amount = discount_koma * unit_extra_price
            
            # 合計額 = 基本料金 + (追加コマ × 追加単価) - (割引コマ × 追加単価)
            price = max(0, base_price + (extra_count * unit_extra_price) - discount_amount)
        table_data.append({
            "👤 生徒名": student,
            "🎓 学年": grade,
            "📚 契約コース": course,
            "📝 実際の受講数": actual_koma,
            "➕ 追加コマ": extra_count, # 🌟 これを表示に追加！
            "💴 今月の請求額 (円)": int(price)
        })
    
    display_df = pd.DataFrame(table_data)

    with st.form("billing_form"):
        edited_df = st.data_editor(
            display_df,
            hide_index=True,
            use_container_width=True,
            disabled=["👤 生徒名", "🎓 学年", "📝 実際の受講数", "➕ 追加コマ"] # 追加コマも自動計算なので固定
        )
        submitted = st.form_submit_button("💾 確定して保存", use_container_width=True)
                
        if submitted:
            with st.spinner("保存中..."):
                # 📝 「実際の受講数」は保存しない（計算用なので）
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