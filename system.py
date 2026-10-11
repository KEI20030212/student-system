# app.py

import streamlit as st
from PIL import Image
# ==========================================
# 📦 1. 画面部隊（views）のインポート
# ==========================================
from views.home import render_combined_home_page
from views.attendance_seat import render_attendance_seat_page
from views.multi_input import render_multi_input_page
from views.input_combined import render_combined_input_page
from views.student_portal import render_student_portal_page
from views.student_details import render_student_details_page
from views.analysis import render_analysis_page
from views.dashboard_combined import render_combined_dashboard_page
from views.quiz_management import render_quiz_management_page
from views.school_homework import render_school_homework_page
from views.line_report import render_line_report_page
from views.search_page import render_search_page
from views.analytics_dashboard import render_analytics_dashboard_page
from views.my_salary import render_my_salary_page
from views.account_manager import render_account_manager_page
from views.finance_integrated import render_finance_integrated_page

# ==========================================
# 🛠️ 2. 裏方部隊（utils）のインポート
# ==========================================
from utils.calc_logic import calculate_hw_rate, calculate_quiz_points, calculate_motivation_rank
from utils.g_sheets import (
    get_textbook_master, 
    add_new_textbook, 
    get_last_homework_info,
    get_all_accounts,
    load_system_settings,    # 🌟 NEW: 追加した関数をインポート
    save_system_settings     # 🌟 NEW: 追加した関数をインポート
)
from utils.api_guard import robust_api_call

# ページの基本設定
try:
    img = Image.open("icon.jpg")
    st.set_page_config(page_title="学習塾管理システム", page_icon=img, layout="wide")
except Exception:
    st.set_page_config(page_title="学習塾管理システム", page_icon="🏫", layout="wide")

# --------------------------------------------------
# 🔒 初回セットアップ ＆ ログイン画面
# --------------------------------------------------
def login_screen():
    # まずシステム設定がすでにあるかチェック
    settings = robust_api_call(load_system_settings, fallback_value={})
    
    # 🌟 もし「教室長名」が設定されていなければ、初回セットアップ画面を表示
    if not settings or not settings.get("教室長名"):
        st.markdown("<h1 style='text-align: center; color: #FF4500;'>🚀 システム初回セットアップ</h1>", unsafe_allow_html=True)
        st.info("ようこそ！まずはこのシステムを利用する教室の基本設定を行ってください。")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.form("setup_form"):
                setup_manager = st.text_input("👤 あなたのお名前（教室長名）", placeholder="例：山田 太郎")
                setup_branch = st.text_input("🏫 校舎名", placeholder="例：田端新町校")
                setup_prefix = st.text_input("🔑 生徒IDの頭文字（アルファベット1〜2文字）", placeholder="例：T （T001などの場合）")
                
                st.caption("※ここで設定したお名前は、LINEレポートなどの自動署名に使用されます。")
                
                submit_setup = st.form_submit_button("設定を保存してシステムを開始 🚀", use_container_width=True)
                
                if submit_setup:
                    if setup_manager and setup_branch and setup_prefix:
                        with st.spinner("スプレッドシートに設定を保存しています..."):
                            success = robust_api_call(save_system_settings, setup_manager, setup_branch, setup_prefix.upper(), fallback_value=False)
                            if success:
                                st.success("✅ 設定が完了しました！自動的にログインします。")
                                # 自動的に初期管理者としてログインさせる
                                st.session_state.update({
                                    'logged_in': True, 
                                    'role': 'admin', 
                                    'username': setup_manager, 
                                    'user_id': 'admin',
                                    'sys_branch': setup_branch,
                                    'sys_prefix': setup_prefix.upper()
                                })
                                st.rerun()
                            else:
                                st.error("❌ 保存に失敗しました。Googleスプレッドシートの連携を確認してください。")
                    else:
                        st.warning("すべての項目を入力してください。")
        return # セットアップ画面表示中は下のログイン画面は出さない

    # 🌟 設定が完了している場合は、通常のログイン画面を表示
    st.markdown("<h1 style='text-align: center; color: #1E90FF;'>🌟 統合管理システム</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center;'>現在の校舎: <b>{settings.get('メイン校舎名', '未設定')}</b></p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("👤 ユーザーID", autocomplete="username")
            password = st.text_input("🔑 パスワード", type="password", autocomplete="current-password")
            submit = st.form_submit_button("ログイン 🚀", use_container_width=True)
            
            if submit:
                # 緊急バックドア（万が一アカウントシートが壊れた時用）
                if username == "admin" and password == "admin123":
                    st.session_state.update({
                        'logged_in': True, 
                        'role': 'admin', 
                        'username': settings.get("教室長名", "管理者"), 
                        'user_id': 'admin',
                        'sys_branch': settings.get("メイン校舎名", ""),
                        'sys_prefix': settings.get("生徒IDの頭文字", "")
                    })
                    st.rerun()
                else:
                    accounts = robust_api_call(get_all_accounts, fallback_value={})

                    if username in accounts and str(accounts[username].get('パスワード')) == str(password):
                        st.session_state.update({
                            'logged_in': True, 
                            'role': accounts[username].get('権限', 'teacher'),
                            'username': accounts[username].get('講師名', accounts[username].get('名前', '先生')),
                            'user_id': username,
                            'sys_branch': settings.get("メイン校舎名", ""),
                            'sys_prefix': settings.get("生徒IDの頭文字", "")
                        })
                        st.rerun()
                    else:
                        st.error("⚠️ IDまたはパスワードが間違っています。")

# --------------------------------------------------
# 🚀 メイン画面＆ルーティング（司令塔）
# --------------------------------------------------
def main():
    if not st.session_state.get('logged_in', False):
        login_screen()
        return

    # 全画面共通のヘッダー
    sys_branch = st.session_state.get('sys_branch', '')
    branch_display = f"【{sys_branch}】" if sys_branch else ""
    
    st.markdown(f"""
    <div style="background-color:#1E90FF;padding:10px;border-radius:10px;margin-bottom:20px;">
        <h2 style="color:white;text-align:center;margin:0;">🌟 統合管理システム {branch_display} <span style="font-size:0.5em;background-color:white;color:#1E90FF;padding:2px 8px;border-radius:5px;">{st.session_state['username']} モード</span></h2>
    </div>
    """, unsafe_allow_html=True)

    # サイドバーのメニュー作成
    st.sidebar.title(f"👤 {st.session_state['username']} メニュー")
    
    menu_options = [
        "📢 ホーム",
        "📝 授業・自習記録の入力 (出欠対応)",
        "🏫 教室・学習状況ダッシュボード",
        "👤 生徒個別ポータル",
        "💯 小テスト管理センター",
        "🔍 全生徒の過去ログ検索",
        "🎒 学校課題管理",
    ]

    if st.session_state['role'] in ['admin', 'sub_admin', 'owner', 'am', 'head_teacher']:
        menu_options.extend([
            "📱 LINE用 学習レポート生成"
        ])

    if st.session_state['role'] in ['admin', 'sub_admin', 'owner', 'am']:
        menu_options.extend([
            "📈 講師分析ダッシュボード",
            "⚙️ アカウント・システム設定",
            "💰 財務・請求ダッシュボード"
        ])
    else:
        # 👨‍🏫 一般講師専用
        menu_options.extend([
            "💴 自分の給与確認"
        ])
        
    page = st.sidebar.radio("移動先", menu_options)

    st.sidebar.divider()
    if st.sidebar.button("🚪 ログアウト", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    # ==========================================
    # 🎯 画面遷移
    # ==========================================
    if page == "📢 ホーム": render_combined_home_page()
    elif page == "📝 授業・自習記録の入力 (出欠対応)": render_combined_input_page()
    elif page == "👤 生徒個別ポータル": render_student_portal_page()
    elif page == "💯 小テスト管理センター": render_quiz_management_page()
    elif page == "🏫 教室・学習状況ダッシュボード":render_combined_dashboard_page()
    elif page == "🎒 学校課題管理": render_school_homework_page()
    elif page == "📱 LINE用 学習レポート生成": render_line_report_page()
    elif page == "🔍 全生徒の過去ログ検索": render_search_page()
    elif page == "📈 講師分析ダッシュボード": render_analytics_dashboard_page()
    elif page == "💴 自分の給与確認": render_my_salary_page()
    elif page == "💰 財務・請求ダッシュボード": render_finance_integrated_page()
    elif page == "⚙️ アカウント・システム設定": render_account_manager_page()

if __name__ == "__main__":
    main()