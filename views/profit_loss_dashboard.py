import streamlit as st
import pandas as pd
from utils.g_sheets import load_billing_data, load_fixed_costs
# 既存の給与計算ロジックがあればここから呼び出す
# from views.salary_dashboard import calculate_total_salary 

def render_profit_loss_dashboard():
    st.header("📈 経営・損益ダッシュボード")
    
    # 1. 月の選択
    # (tuition_dashboardと同様の月選択ロジック)
    selected_month = st.selectbox("集計月を選択", ["2024年04月", "2024年03月"]) 

    # 2. 売上（請求確定データから）の集計
    billing_df = load_billing_data(selected_month)
    revenue = billing_df["💴 今月の請求額 (円)"].sum() if not billing_df.empty else 0

    # 3. 支出の集計
    # a. 給与（salary_dashboardのロジックを流用。ここでは仮に50万とします）
    salaries = 500000 
    
    # b. 固定費
    fixed_costs_df = load_fixed_costs()
    total_fixed_costs = fixed_costs_df["金額"].sum()

    # 4. 指標の表示
    total_expenses = salaries + total_fixed_costs
    net_profit = revenue - total_expenses

    col1, col2, col3 = st.columns(3)
    col1.metric("総売上", f"{revenue:,}円")
    col2.metric("総支出", f"{total_expenses:,}円", delta=f"-{total_expenses:,}", delta_color="inverse")
    col3.metric("純利益", f"{net_profit:,}円")

    # 5. 支出の内訳グラフ
    st.subheader("支出の内訳")
    expense_data = pd.DataFrame({
        "項目": ["講師給与"] + fixed_costs_df["項目"].tolist(),
        "金額": [salaries] + fixed_costs_df["金額"].tolist()
    })
    st.bar_chart(expense_data.set_index("項目"))

    # 6. 詳細テーブル
    st.write("### 経費詳細")
    st.table(fixed_costs_df)