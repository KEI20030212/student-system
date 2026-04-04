# views/my_salary.py

import streamlit as st
import pandas as pd
from utils.g_sheets import load_published_salary
from utils.pdf_generator import generate_payslip_pdf # 👈 先生ページでもPDF職人を召喚！

def render_my_salary_page():
    # ログインしている先生の名前を取得
    teacher_name = st.session_state.get('username', '先生')
    
    st.header(f"💴 {teacher_name} 先生の給与確認")
    st.write("※教室長から公開された確定済みの給与明細を表示しています。")

    # 1. 公開された給与データを読み込む（API通信は1回だけで爆速！）
    df_all_salaries = load_published_salary()
    
    if df_all_salaries.empty:
        st.warning("現在、公開されている給与データはありません。")
        return
        
    # 2. 自分のデータだけに絞り込む
    my_data = df_all_salaries[df_all_salaries['👨‍🏫 担当講師'] == teacher_name]
    
    if my_data.empty:
        st.warning(f"現在、{teacher_name} 先生の公開済み給与データはありません。")
        return

    # 年月で降順（新しい月を上に）並び替え
    my_data = my_data.sort_values('年月', ascending=False).reset_index(drop=True)
    
    # 3. 表示月を選択（デフォルトは一番新しい月）
    month_options = my_data['年月'].unique().tolist()
    selected_month = st.selectbox("📅 確認する月を選択してください", month_options)
    
    # 選んだ月のデータ行を取得
    selected_row = my_data[my_data['年月'] == selected_month].iloc[0]
    
    # 4. 見やすいカード形式で表示
    st.markdown(f"### 📊 {selected_month} の給与概要")
    col1, col2, col3 = st.columns(3)
    col1.metric("最終支給額", f"¥{int(selected_row['💰 最終支給額 (円)']):,}")
    col2.metric("授業給", f"¥{int(selected_row['授業給 (円)']):,}")
    col3.metric("交通費・手当", f"¥{int(selected_row['交通費合計 (円)'] + selected_row['役職手当 (円)']):,}")

    st.write("**詳細データ**")
    # 不要な「年月」列などを隠して綺麗にテーブル表示
    display_df = pd.DataFrame([selected_row]).drop(columns=['年月'])
    st.dataframe(display_df, hide_index=True, use_container_width=True)

    st.divider()

    # 5. 🌟 先生自身でPDFダウンロード！
    st.subheader("📄 給与明細のダウンロード")
    
    # PDF職人に渡すための辞書データに変換
    row_dict = selected_row.to_dict()
    
    # PDFを生成（教室長ページと同じ関数を使うのでデザインも同じ！）
    pdf_bytes = generate_payslip_pdf(row_dict, selected_month)
    
    st.download_button(
        label=f"📥 {selected_month} の給与明細 (PDF) をダウンロード",
        data=pdf_bytes,
        file_name=f"給与明細_{selected_month}_{teacher_name}.pdf",
        mime="application/pdf",
        type="primary"
    )