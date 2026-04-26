import streamlit as st
import json
import time
import base64
import io
from pypdf import PdfWriter
from utils.g_sheets import (
    get_quiz_maker_sheets,
    add_quiz_maker_sheet,
    delete_quiz_maker_sheet,
    get_gc_client
)

def render_word_quiz_maker_page():
    st.header("🔤 単語テスト作成・印刷")
    st.write("単語テスト専用のレイアウトでPDFを作成します。")

    # 既存のリスト取得機能を流用
    quiz_dict = get_quiz_maker_sheets()

    # --- 新規登録機能（既存と同じ） ---
    with st.expander("➕ 新しい単語テストをリストに登録する"):
        with st.form("add_word_quiz_form"):
            new_name = st.text_input("📝 テスト名 (例: 英単語ターゲット1900)")
            new_id = st.text_input("🔑 スプレッドシートID")
            new_full_marks = st.number_input("💯 満点", min_value=1, value=100)
            # 単語テストは選択肢でサイズが決まるため、登録時はデフォルトでOK
            submit_new = st.form_submit_button("リストに登録する ✨")
            if submit_new and new_name:
                add_quiz_maker_sheet(new_name, new_id.strip(), new_full_marks, "B5") # デフォルトB5
                st.success(f"「{new_name}」を登録しました！")
                time.sleep(1)
                st.rerun()

    if not quiz_dict:
        st.warning("テストが登録されていません。")
        return

    # --- メイン設定 ---
    quiz_name = st.selectbox("📚 ファイルを選択", sorted(quiz_dict.keys()), key="word_quiz_select")
    quiz_data = quiz_dict[quiz_name]
    sheet_id = quiz_data.get("id", "") if isinstance(quiz_data, dict) else quiz_data

    with st.container(border=True):
        st.markdown("#### ⚙️ 単語テスト設定")
        
        # 🌟 ここがポイント：問題数によってサイズと範囲を自動定義
        word_type = st.radio(
            "📝 問題数を選択してください",
            ["8問 (B5)", "16問 (B5)", "32問 (A4)", "50問 (A3)"],
            horizontal=True
        )

        # 設定の振り分け
        if word_type == "8問 (B5)":
            q_range, a_range, p_size = "A1:I18", "J1:R18", "B5"
        elif word_type == "16問 (B5)":
            q_range, a_range, p_size = "A1:I18", "J1:R18", "B5"
        elif word_type == "32問 (A4)":
            q_range, a_range, p_size = "A1:N18", "O1:AB18", "A4"
        else: # 50問
            q_range, a_range, p_size = "A1:N27", "O1:AB27", "A3"

        st.info(f"💡 【{word_type}】設定: 範囲 {q_range} / 用紙 {p_size}")

        # 範囲指定（既存の確認テストと同じロジック）
        target_sheet_name = "確認テスト"
        c1, c2, c3 = st.columns(3)
        start_num = c1.number_input("はじめの番号", min_value=1, value=1, key="word_s")
        end_num = c2.number_input("おわりの番号", min_value=1, value=20, key="word_e")
        shuffle = c3.checkbox("🔀 シャッフルする", value=False, key="word_sh")

        if st.button(f"✨ 単語テスト({word_type})を作成する", type="primary", use_container_width=True):
            with st.spinner("単語テスト生成中..."):
                try:
                    gc = get_gc_client()
                    sh = gc.open_by_key(sheet_id)
                    
                    # 1. 範囲書き込み
                    setting_ws = sh.worksheet("テスト範囲指定")
                    setting_ws.update_acell('B2', start_num)
                    setting_ws.update_acell('B3', end_num)
                    setting_ws.update_acell('D3', shuffle) 
                    time.sleep(3) 

                    # 2. シート取得
                    target_ws = sh.worksheet(target_sheet_name)
                    gid = target_ws.id

                    # 3. PDF URL作成 (前回の最強設定を適用)
                    base_url = (
                        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export"
                        f"?format=pdf&gid={gid}&size={p_size}&portrait=true"
                        f"&gridlines=false&scale=3&fitw=true"
                        f"&top_margin=0.2&bottom_margin=0.2&left_margin=0.2&right_margin=0.2"
                        f"&horizontal_alignment=CENTER&fzr=false&fzc=false"
                    )
                    url_q = f"{base_url}&range={q_range}"
                    url_a = f"{base_url}&range={a_range}"

                    # 4. ダウンロード処理
                    import requests
                    import google.auth.transport.requests
                    from google.oauth2.service_account import Credentials
                    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
                    secret_dict = json.loads(st.secrets["gcp_service_account_json"])
                    creds = Credentials.from_service_account_info(secret_dict, scopes=scopes)
                    creds.refresh(google.auth.transport.requests.Request())
                    headers = {"Authorization": f"Bearer {creds.token}"}
                    
                    res_q = requests.get(url_q, headers=headers)
                    res_a = requests.get(url_a, headers=headers)
                    
                    merger = PdfWriter()
                    merger.append(io.BytesIO(res_q.content))
                    merger.append(io.BytesIO(res_a.content))
                    
                    merged_stream = io.BytesIO()
                    merger.write(merged_stream)
                    
                    st.session_state['word_pdf_merged'] = merged_stream.getvalue()
                    st.session_state['word_pdf_q'] = res_q.content
                    st.session_state['word_pdf_a'] = res_a.content
                    st.success("✅ 生成完了！")

                except Exception as e:
                    st.error(f"エラー: {e}")

    # --- ダウンロードUI ---
    if 'word_pdf_merged' in st.session_state:
        st.divider()
        def display_pdf(pdf_bytes, filename, color="#28a745"):
            b64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
            st.markdown(f'<a href="data:application/pdf;base64,{b64_pdf}" download="{filename}" style="display: block; text-align: center; padding: 12px; background-color: {color}; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; margin-bottom: 10px;">📥 {filename} を開く</a>', unsafe_allow_html=True)

        display_pdf(st.session_state['word_pdf_merged'], "単語テスト_問題解答セット.pdf")