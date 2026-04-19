import streamlit as st
import pandas as pd
from utils.g_sheets import load_billing_data, load_fixed_costs

def render_profit_loss_dashboard():
    st.header("📈 経営ダッシュボード (純利益管理)")
    
    # 月の選択（とりあえず最新月）
    month = st.selectbox("集計月", ["2024年05月", "2024年04月"]) # 動的にするとベター

    # 1. 売上の取得
    billing_df = load_billing_data(month)
    total_revenue = billing_df["💴 今月の請求額 (円)"].sum() if not billing_df.empty else 0

    # 2. 支出（給与）の取得
    # salary_dashboardの集計ロジックをここに
    total_salary = 450000 # 仮。実際はsalaryの保存データから取得

    # 3. 支出（固定費）
    fixed_df = load_fixed_costs()
    total_fixed = fixed_df["金額"].sum()

    # 4. 利益計算
    total_expense = total_salary + total_fixed
    net_profit = total_revenue - total_expense

    # 表示
    c1, c2, c3 = st.columns(3)
    c1.metric("総売上", f"{total_revenue:,}円")
    c2.metric("総支出", f"{total_expense:,}円", delta=f"-{total_expense:,}", delta_color="inverse")
    c3.metric("純利益", f"{net_profit:,}円")

    # グラフ
    st.bar_chart(pd.DataFrame({
        "カテゴリ": ["売上", "給与支出", "固定費", "純利益"],
        "金額": [total_revenue, -total_salary, -total_fixed, net_profit]
    }).set_index("カテゴリ"))