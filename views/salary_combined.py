import streamlit as st

# 完成している2つのファイルを部品として読み込む
from views.my_salary import render_my_salary_page
from views.salary_dashboard import render_salary_dashboard_page

def render_salary_combined_page():
    # 🌟 ログイン中のユーザー権限を取得
    # ※ "role" の部分は、ログイン機能で使っている変数名に合わせてください（例: user_role など）
    role = st.session_state.get("role", "講師") 

    # 👨‍💼 オーナー・教室長の場合（タブで両方表示）
    if role in ["オーナー", "教室長"]:
        # ここでタイトルを付けると、my_salary側とダブるかもしれないのでシンプルにタブだけで構成します
        tab1, tab2 = st.tabs(["💴 自分の給与確認", "💰 給与ダッシュボード（管理者用）"])
        
        with tab1:
            render_my_salary_page()
            
        with tab2:
            render_salary_dashboard_page()
            
    # 👩‍🏫 主任講師・講師の場合（自分の給与確認のみ、そのまま表示）
    elif role in ["主任講師", "講師"]:
        render_my_salary_page()
        
    # それ以外（予期せぬエラー防止）
    else:
        st.error("権限が設定されていないため、このページを表示できません。")