import streamlit as st

# 各画面の描画関数を直接読み込む
from views.tuition_dashboard import render_tuition_dashboard_page
from views.salary_dashboard import render_salary_dashboard_page
from views.my_salary import render_my_salary_page
from views.profit_loss_dashboard import render_profit_loss_dashboard_page

def render_finance_integrated_page():
    # --- サイドバーでメニューを作成 ---
    st.sidebar.title("🧭 ナビゲーション")
    
    # st.radio（ラジオボタン）を使って、絶対に1画面しか選べないようにする
    menu_selection = st.sidebar.radio(
        "表示する画面を選択してください",
        (
            "💴 月謝管理ダッシュボード", 
            "💰 給与・交通費ダッシュボード", 
            "👩‍🏫 講師用マイページ", 
            "📈 損益ダッシュボード"
        )
    )

    # --- 選択された画面「だけ」を実行する（ここが超重要！） ---
    if menu_selection == "💴 月謝管理ダッシュボード":
        render_tuition_dashboard_page()
        
    elif menu_selection == "💰 給与・交通費ダッシュボード":
        render_salary_dashboard_page()
        
    elif menu_selection == "👩‍🏫 講師用マイページ":
        render_my_salary_page()
        
    elif menu_selection == "📈 損益ダッシュボード":
        render_profit_loss_dashboard_page()

# もしこのファイルが直接実行された場合の処理（必要に応じて）
if __name__ == "__main__":
    render_finance_integrated_page()