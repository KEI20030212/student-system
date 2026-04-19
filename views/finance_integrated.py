import streamlit as st

# 各ページの関数をインポート
from views.tuition_dashboard import render_tuition_dashboard_page
from views.salary_combined import render_salary_combined_page  # ※実際の関数名に合わせてください
from views.profit_loss_dashboard import render_profit_loss_dashboard_page # ※実際の関数名に合わせてください

def render_finance_integrated_page():
    st.title("💰 財務・請求ダッシュボード")
    st.caption("月謝の請求、講師の給与計算、全体の収支を管理します。")
    
    # 🌟 3つのタブを作成
    tab1, tab2, tab3 = st.tabs([
        "💴 月謝（請求額）管理", 
        "💸 給与計算", 
        "📈 収支ダッシュボード"
    ])
    
    # タブ1の中身
    with tab1:
        render_tuition_dashboard_page()
        
    # タブ2の中身
    with tab2:
        render_salary_combined_page()
        
    # タブ3の中身
    with tab3:
        render_profit_loss_dashboard_page()