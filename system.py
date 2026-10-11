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
from utils.g_sheets import get_textbook_master, add_new_textbook, get_last_homework_info
from utils.g_sheets import get_all_accounts, get_gc_client, SPREADSHEET_ID # 🌟 NEW: スプレッドシート操作用
from utils.api_guard import robust_api_call

# ページの基本設定
img = Image.open("icon.jpg")
st.set_page_config(page_title="学習塾管理システム", page_icon=img, layout="wide")

# 🔑 パスワード設定（管理者用のマスターキー）
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"
TEACHER_USER = "teacher"
TEACHER_PASS = "teacher123"

# --------------------------------------------------
# 🔒 ログイン画面
# --------------------------------------------------
def login_screen():
    st.markdown("<h1 style='text-align: center; color: #1E90FF;'>🌟 統合管理システム</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("👤 ユーザーID", autocomplete="username")
            password = st.text_input("🔑 パスワード", type="password", autocomplete="current-password")
            submit = st.form_submit_button("ログイン 🚀", use_container_width=True)
            
            if submit:
                # 🌟 管理者マスターキーでのログイン
                if username == ADMIN_USER and password == ADMIN_PASS:
                    st.session_state.update({
                        'logged_in': True, 
                        'role': 'admin', 
                        'username': '管理者', 
                        'user_id': 'admin',
                        'needs_setup': False # マスターは設定不要
                    })
                    st.rerun()
                    
                # 🌟 テスト講師キーでのログイン
                elif username == TEACHER_USER and password == TEACHER_PASS:
                    st.session_state.update({
                        'logged_in': True, 
                        'role': 'teacher', 
                        'username': 'テスト講師', 
                        'user_id': 'teacher',
                        'needs_setup': False
                    })
                    st.rerun()
                    
                # 🌟 アカウントシートからのログイン照合
                else:
                    accounts = robust_api_call(get_all_accounts, fallback_value={})

                    if username in accounts and str(accounts[username].get('パスワード')) == str(password):
                        # スプレッドシートから情報を取得
                        acc_info = accounts[username]
                        role = acc_info.get('権限', 'teacher')
                        
                        # 🌟 NEW: 「講師名」と「所属校舎」が空欄かどうかをチェック
                        teacher_name = str(acc_info.get('講師名', '')).strip()
                        branch_name = str(acc_info.get('所属校舎', '')).strip()
                        
                        # どちらかが未入力（初期状態）ならセットアップ画面へ誘導
                        needs_setup = False
                        if not teacher_name or not branch_name:
                            needs_setup = True
                            teacher_name = "新規ユーザー" # 仮の名前
                            
                        st.session_state.update({
                            'logged_in': True, 
                            'role': role,
                            'username': teacher_name,
                            'user_id': username,
                            'branch': branch_name,
                            'needs_setup': needs_setup # 🌟 ここでフラグを立てる
                        })
                        st.rerun()
                    else:
                        st.error("⚠️ IDまたはパスワードが間違っています。")

# --------------------------------------------------
# 🌱 初回セットアップ画面
# --------------------------------------------------
def setup_screen():
    st.markdown("<h2 style='text-align: center; color: #32CD32;'>🌱 はじめまして！初期設定をお願いします</h2>", unsafe_allow_html=True)
    st.write("このシステムを初めてご利用になる方へ。あなたの表示名とメインで担当する校舎を登録してください。（この情報はレポートの署名などに使用されます）")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("setup_form"):
            new_name = st.text_input("📛 あなたのお名前（フルネーム、または苗字のみ）", placeholder="例：山田 太郎")
            
            # 校舎の選択肢（実際の運用に合わせて変更可能）
            branch_options = ["田端新町校", "東十条駅前校", "池上校", "本部・その他"]
            new_branch = st.selectbox("🏫 主な担当校舎", branch_options)
            
            submit_setup = st.form_submit_button("登録してシステムを開始する ✨", use_container_width=True)
            
            if submit_setup:
                if not new_name.strip():
                    st.error("⚠️ お名前を入力してください。")
                else:
                    with st.spinner("設定を保存しています..."):
                        try:
                            # スプレッドシートの「設定_アカウント」を更新する
                            gc = get_gc_client()
                            sh = gc.open_by_key(SPREADSHEET_ID)
                            ws = sh.worksheet("設定_アカウント")
                            
                            # IDが一致する行を探す
                            records = ws.get_all_values()
                            target_row_idx = -1
                            for i, row in enumerate(records):
                                if len(row) > 0 and str(row[0]) == st.session_state['user_id']:
                                    target_row_idx = i + 1 # スプレッドシートは1始まり
                                    break
                            
                            if target_row_idx != -1:
                                # 名前はC列(3)、校舎はD列(4)に保存すると仮定（シートの構造に合わせて調整してください）
                                # ※ここでは「講師名」がC列、「所属校舎」がD列と想定しています
                                ws.update_cell(target_row_idx, 3, new_name.strip())
                                ws.update_cell(target_row_idx, 4, new_branch)
                                
                                # Session Stateを更新
                                st.session_state['username'] = new_name.strip()
                                st.session_state['branch'] = new_branch
                                st.session_state['needs_setup'] = False
                                
                                # キャッシュをクリアして次回から新しい情報を読み込ませる
                                if 'all_accounts' in st.session_state:
                                    del st.session_state['all_accounts']
                                    
                                st.success("✅ 登録が完了しました！")
                                st.rerun()
                            else:
                                st.error("⚠️ アカウント情報が見つかりませんでした。")
                        except Exception as e:
                            st.error(f"⚠️ 保存中にエラーが発生しました: {e}")

# --------------------------------------------------
# 🚀 メイン画面＆ルーティング（司令塔）
# --------------------------------------------------
def main():
    # 1. ログインしていない場合はログイン画面
    if not st.session_state.get('logged_in', False):
        login_screen()
        return

    # 🌟 2. NEW: ログイン直後、名前や校舎が未登録ならセットアップ画面を強制表示
    if st.session_state.get('needs_setup', False):
        setup_screen()
        return

    # 3. 通常のメイン画面（全画面共通のヘッダー）
    branch_badge = f" 🏫 {st.session_state.get('branch', '')}" if st.session_state.get('branch') else ""
    
    st.markdown(f"""
    <div style="background-color:#1E90FF;padding:10px;border-radius:10px;margin-bottom:20px;">
        <h2 style="color:white;text-align:center;margin:0;">🌟 統合管理システム <span style="font-size:0.5em;background-color:white;color:#1E90FF;padding:2px 8px;border-radius:5px;">{st.session_state['username']} モード{branch_badge}</span></h2>
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
        # 👨‍🏫 一般講師専用（自分に関することだけ）
        menu_options.extend([
            "💴 自分の給与確認"
        ])
        
    page = st.sidebar.radio("移動先", menu_options)

    # ログアウトボタン
    st.sidebar.divider()
    if st.sidebar.button("🚪 ログアウト", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    # ==========================================
    # 🎯 選ばれたメニューに応じて、該当する画面関数を呼び出すだけ！
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