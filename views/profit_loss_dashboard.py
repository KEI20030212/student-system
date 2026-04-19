import streamlit as st
import pandas as pd
import datetime # 🌟 日付を扱うための標準機能をインポート
from utils.g_sheets import load_billing_data, load_fixed_costs

def render_profit_loss_dashboard_page():
    st.header("📈 経営ダッシュボード (純利益管理)")
    
    # --- 現在から過去12ヶ月分を動的に生成する ---
    today = datetime.datetime.now()
    month_options = []
    
    for i in range(12):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        month_options.append(f"{y}年{m:02d}月")
        
    month = st.selectbox("📅 集計月", month_options)
    # --------------------------------------------------------

    # 1. 売上の取得
    billing_df = load_billing_data(month)
    total_revenue = billing_df["💴 今月の請求額 (円)"].sum() if not billing_df.empty else 0

    # 2. 支出（給与）の取得
    # salary_dashboardの集計ロジックをここに
    total_salary = 450000 # 仮。実際はsalaryの保存データから取得

    # 3. 支出（固定費）の取得
    try:
        fixed_df = load_fixed_costs()
        total_fixed = fixed_df["金額"].sum() if not fixed_df.empty else 0
    except Exception:
        fixed_df = pd.DataFrame() # 内訳表示用に空のデータフレームを用意
        total_fixed = 0 # データがない場合のエラー回避

    # 4. 利益計算
    total_expense = total_salary + total_fixed
    net_profit = total_revenue - total_expense

    # ==========================================
    # 🖥️ 画面表示セクション
    # ==========================================
    
    # 🌟 上部：重要指標（KPI）サマリー
    c1, c2, c3 = st.columns(3)
    c1.metric("総売上", f"{total_revenue:,}円")
    c2.metric("総支出", f"{total_expense:,}円", delta=f"-{total_expense:,}", delta_color="inverse")
    c3.metric("純利益", f"{net_profit:,}円")

    st.divider() # 区切り線

    # 🌟 中部：グラフと損益計算書（P&L）を左右に並べる
    col_chart, col_pnl = st.columns([1, 1])

    with col_chart:
        st.subheader("📊 収支バランス")
        st.bar_chart(pd.DataFrame({
            "カテゴリ": ["売上", "給与支出", "固定費", "純利益"],
            "金額": [total_revenue, -total_salary, -total_fixed, net_profit]
        }).set_index("カテゴリ"))

    with col_pnl:
        st.subheader("📋 損益計算書 (P&L)")
        
        # 損益計算書風のデータフレームを作成
        pnl_data = [
            {"科目": "【売上高】", "金額 (円)": ""},
            {"科目": "　授業料等売上", "金額 (円)": f"{total_revenue:,}"},
            {"科目": "【経費】", "金額 (円)": ""},
            {"科目": "　講師給与手当", "金額 (円)": f"{total_salary:,}"},
            {"科目": "　固定費・その他経費", "金額 (円)": f"{total_fixed:,}"},
            {"科目": "【経費合計】", "金額 (円)": f"{total_expense:,}"},
            {"科目": "【営業利益】 (純利益)", "金額 (円)": f"{net_profit:,}"}
        ]
        # hide_index=True でスッキリした表にする
        st.dataframe(pd.DataFrame(pnl_data), hide_index=True, use_container_width=True)


    # 🌟 下部：各データの内訳をドリルダウン
    st.divider()
    st.subheader("🔍 経費・売上の詳細内訳")
    
    col_detail1, col_detail2 = st.columns(2)
    
    with col_detail1:
        st.markdown("**💸 固定費一覧**")
        if not fixed_df.empty:
            st.dataframe(fixed_df, hide_index=True, use_container_width=True)
        else:
            st.info("今月の固定費データはありません。")
            
    with col_detail2:
        st.markdown("**💴 売上（生徒別 月謝）一覧**")
        if not billing_df.empty:
            # 全部表示すると見にくいので、名前と金額だけを抽出して表示
            display_cols = [col for col in ["生徒名", "💴 今月の請求額 (円)"] if col in billing_df.columns]
            if display_cols:
                st.dataframe(billing_df[display_cols], hide_index=True, use_container_width=True)
            else:
                st.dataframe(billing_df, hide_index=True, use_container_width=True) # 列名が違う場合はそのまま表示
        else:
            st.info("今月の売上データはありません。")