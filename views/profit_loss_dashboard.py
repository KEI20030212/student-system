import streamlit as st
import pandas as pd
import datetime # 🌟 日付を扱うための標準機能をインポート
from utils.g_sheets import load_billing_data, load_fixed_costs

def render_profit_loss_dashboard_page():
    st.header("📈 経営ダッシュボード (純利益管理)")
    
    # --- 🌟ここから修正：現在から過去12ヶ月分を動的に生成する ---
    today = datetime.datetime.now()
    month_options = []
    
    # 過去12ヶ月分のリストを作成（もっと昔まで見たい場合は range(24) などに変更してください）
    for i in range(12):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        month_options.append(f"{y}年{m:02d}月")
        
    # 動的になった月リストをselectboxにセット
    month = st.selectbox("📅 集計月", month_options)
    # --------------------------------------------------------

    # 1. 売上の取得
    billing_df = load_billing_data(month)
    total_revenue = billing_df["💴 今月の請求額 (円)"].sum() if not billing_df.empty else 0

    # 2. 支出（給与）の取得
    # salary_dashboardの集計ロジックをここに
    total_salary = 450000 # 仮。実際はsalaryの保存データから取得

    # 3. 支出（固定費）
    try:
        fixed_df = load_fixed_costs()
        total_fixed = fixed_df["金額"].sum() if not fixed_df.empty else 0
    except Exception:
        total_fixed = 0 # データがない場合のエラー回避

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