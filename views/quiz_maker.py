import streamlit as st
import json
import streamlit.components.v1 as components
import time     # ← これを追加！
import base64   # ← これを追加！

# 裏方部隊から、スプレッドシートのURL（ID）を管理する関数などを呼び出します
from utils.g_sheets import (
    get_quiz_maker_sheets,
    add_quiz_maker_sheet,
    delete_quiz_maker_sheet,
    get_gc_client  # ← これを追加！
)
def render_quiz_maker_page():
    st.header("🖨️ 小テスト作成・印刷")
    st.write("設定したスプレッドシートと連動して、自動で問題を抽出し、印刷用データを作成します。")

    quiz_dict = get_quiz_maker_sheets()

    with st.expander("➕ 新しい小テストをリストに登録する"):
        st.write("他の先生も使えるように、新しい小テストのファイルをリストに保存します！")
        with st.form("add_quiz_form"):
            new_name = st.text_input("📝 テストの名前 (例: 中2 数学 計算ドリル)")
            new_id = st.text_input("🔑 スプレッドシートのID", placeholder="1A2B3C4D5E6F7G...")
            submit_new = st.form_submit_button("リストに登録する ✨")
            
            if submit_new:
                if new_name and new_id:
                    add_quiz_maker_sheet(new_name, new_id)
                    st.success(f"「{new_name}」をリストに登録しました！")
                    st.rerun()
                else:
                    st.warning("⚠️ 名前とIDの両方を入力してください。")

    st.divider()

    if not quiz_dict:
        st.warning("小テストが登録されていません。上のメニューから登録してください。")
        return

    c_sel, c_del = st.columns([4, 1])
    with c_sel:
        quiz_name = st.selectbox("📚 使用する小テストのファイルを選択", list(quiz_dict.keys()))
    with c_del:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        if st.button("🗑️ リストから削除", use_container_width=True):
            delete_quiz_maker_sheet(quiz_name)
            st.toast(f"🗑️ 「{quiz_name}」を削除しました！")
            time.sleep(1)
            st.rerun()

    sheet_id = quiz_dict[quiz_name]

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        start_num = c1.number_input("はじめの番号 (B2セル)", min_value=1, value=1)
        end_num = c2.number_input("終わりの番号 (B3セル)", min_value=1, value=20)
        shuffle = c3.checkbox("🔀 問題をシャッフルする (D3セル)", value=False)

        if st.button("✨ 問題を作成する", type="primary", use_container_width=True):
            with st.spinner("魔法の小テストジェネレーターを起動中... (約5秒かかります)"):
                try:
                    gc = get_gc_client()
                    sh = gc.open_by_key(sheet_id)
                    
                    setting_ws = sh.worksheet("テスト範囲指定")
                    setting_ws.update_acell('B2', start_num)
                    setting_ws.update_acell('B3', end_num)
                    setting_ws.update_acell('D3', shuffle) 
                    
                    time.sleep(3)
                    
                    test_ws = sh.worksheet("確認テスト")
                    gid = test_ws.id
                    
                    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=pdf&gid={gid}&portrait=true&size=A4&gridlines=false&fitw=true"
                    url_q = f"{base_url}&range=A1:I28"
                    url_a = f"{base_url}&range=J1:R28"
                    
                    import google.auth.transport.requests
                    import requests
                    from google.oauth2.service_account import Credentials
                    
                    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
                    secret_dict = json.loads(st.secrets["gcp_service_account_json"])
                    creds = Credentials.from_service_account_info(secret_dict, scopes=scopes)
                    req = google.auth.transport.requests.Request()
                    creds.refresh(req)
                    headers = {"Authorization": f"Bearer {creds.token}"}
                    
                    res_q = requests.get(url_q, headers=headers)
                    res_a = requests.get(url_a, headers=headers)
                    
                    st.session_state['pdf_q'] = res_q.content
                    st.session_state['pdf_a'] = res_a.content
                    st.success("✅ スプレッドシートそのままのPDF生成が完了しました！")
                except Exception as e:
                    st.error(f"❌ エラーが発生しました。IDが間違っているか、権限がありません。詳細: {e}")

    if 'pdf_q' in st.session_state and 'pdf_a' in st.session_state:
        st.divider()
        st.subheader("👀 ダウンロード ＆ 印刷 (PDF)") # タイトルを少し変えました
        tab_q, tab_a = st.tabs(["📝 問題 (A〜I列)", "💡 解答 (J〜R列)"])

        def display_pdf(pdf_bytes, filename):
            st.download_button(
                label=f"📥 【 {filename} 】を開く / 印刷する",
                data=pdf_bytes, 
                file_name=filename, 
                mime="application/pdf", 
                type="primary", 
                use_container_width=True
            )
            # ▼ ここにあったプレビュー用の iframe のコードを削除しました！▼

        with tab_q: display_pdf(st.session_state['pdf_q'], "確認テスト_問題.pdf")
        with tab_a: display_pdf(st.session_state['pdf_a'], "確認テスト_解答.pdf")
