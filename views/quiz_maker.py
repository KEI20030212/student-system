import streamlit as st
import json
import streamlit.components.v1 as components
import time
import base64
import io
from pypdf import PdfWriter

# 裏方部隊から、スプレッドシートのURL（ID）を管理する関数などを呼び出します
from utils.g_sheets import (
    get_quiz_maker_sheets,
    add_quiz_maker_sheet,
    delete_quiz_maker_sheet,
    get_gc_client
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
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning("⚠️ 名前とIDの両方を入力してください。")

    st.divider()

    if not quiz_dict:
        st.warning("小テストが登録されていません。上のメニューから登録してください。")
        return

    # リストを名前順に整列
    sorted_quiz_names = sorted(quiz_dict.keys())

    c_sel, c_del = st.columns([4, 1])
    with c_sel:
        quiz_name = st.selectbox("📚 使用する小テストのファイルを選択", sorted_quiz_names)
    
    with c_del:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        with st.popover("🗑️ 削除", use_container_width=True):
            st.warning(f"本当に「{quiz_name}」をリストから削除しますか？")
            if st.button("はい、削除します", type="primary", use_container_width=True):
                delete_quiz_maker_sheet(quiz_name)
                st.toast(f"🗑️ 「{quiz_name}」を削除しました！")
                time.sleep(1)
                st.rerun()

    # 選ばれた小テストのIDを取得
    sheet_id = quiz_dict[quiz_name]

    with st.container(border=True):
        st.markdown("#### ⚙️ 印刷設定")
        
        # ==========================================
        # 🌟 修正ポイント1: テストの種類を選ぶラジオボタン
        # ==========================================
        test_type = st.radio(
            "📝 テストの種類を選択", 
            ["確認テスト", "良問テスト(簡)", "良問テスト(難)"], 
            horizontal=True
        )
        
        # 選んだテストの種類によって、入力項目とターゲットシートを切り替えます
        if test_type == "確認テスト":
            target_sheet_name = "確認テスト"
            st.write("▼ 範囲を指定して問題を作成します")
            c1, c2, c3 = st.columns(3)
            start_num = c1.number_input("はじめの番号 (B2セル)", min_value=1, value=1)
            end_num = c2.number_input("終わりの番号 (B3セル)", min_value=1, value=20)
            shuffle = c3.checkbox("🔀 問題をシャッフルする (D3セル)", value=False)
        else:
            # 良問テストの場合は「章番号」を入力させる
            c_chap, _ = st.columns([1, 2])
            chapter_num = c_chap.number_input("🔢 章番号 (〇に入る数字)", min_value=1, value=1, step=1)
            target_sheet_name = f"{test_type}{chapter_num}"
            st.info(f"💡 スプレッドシートの「{target_sheet_name}」シートをそのままPDF化します。")

        # ボタンの文字も動的に変わるようにしました
        if st.button(f"✨ {target_sheet_name} を作成する", type="primary", use_container_width=True):
            with st.spinner(f"魔法の小テストジェネレーターを起動中... [{target_sheet_name}]"):
                try:
                    gc = get_gc_client()
                    sh = gc.open_by_key(sheet_id)
                    
                    # ==========================================
                    # 🌟 修正ポイント2: 確認テストの時だけ範囲指定シートを操作
                    # ==========================================
                    if test_type == "確認テスト":
                        setting_ws = sh.worksheet("テスト範囲指定")
                        setting_ws.update_acell('B2', start_num)
                        setting_ws.update_acell('B3', end_num)
                        setting_ws.update_acell('D3', shuffle) 
                        time.sleep(3) # 反映を待つ
                    
                    # ターゲットとなるシート（確認テスト or 良問テスト〇）を探す
                    try:
                        target_ws = sh.worksheet(target_sheet_name)
                    except Exception:
                        st.error(f"❌ 「{target_sheet_name}」という名前のシートが見つかりません！スプレッドシートにその章のシートがあるか確認してください。")
                        st.stop() # シートがない場合はここで処理をストップ
                        
                    gid = target_ws.id
                    
                    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=pdf&gid={gid}&portrait=true&size=A4&gridlines=false&fitw=true"
                    # 良問テストも「A1:I28が問題、J1:R28が解答」の形式と想定しています
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
                    
                    # 1. 問題と解答をそれぞれダウンロード
                    res_q = requests.get(url_q, headers=headers)
                    res_a = requests.get(url_a, headers=headers)
                    
                    # 2. PDFの結合処理（ガッチャンコ！）
                    merger = PdfWriter()
                    merger.append(io.BytesIO(res_q.content))
                    merger.append(io.BytesIO(res_a.content))
                    
                    merged_pdf_stream = io.BytesIO()
                    merger.write(merged_pdf_stream)
                    
                    # 3. 画面に渡すためにセッションに保存（どのテストを作ったかの名前も保存！）
                    st.session_state['pdf_q'] = res_q.content
                    st.session_state['pdf_a'] = res_a.content
                    st.session_state['pdf_merged'] = merged_pdf_stream.getvalue()
                    st.session_state['generated_test_name'] = target_sheet_name # ← 追加！
                    
                    st.success(f"✅ 【{target_sheet_name}】のセットPDF生成が完了しました！")
                except Exception as e:
                    st.error(f"❌ エラーが発生しました。詳細: {e}")

    # ==========================================
    # ダウンロードUI
    # ==========================================
    if 'pdf_merged' in st.session_state:
        st.divider()
        st.subheader("👀 ダウンロード ＆ 印刷 (PDF)")

        def display_pdf(pdf_bytes, filename, color="#FF4B4B"):
            b64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
            html_button = f'''
            <a href="data:application/pdf;base64,{b64_pdf}" download="{filename}" target="_blank" 
               style="display: block; text-align: center; padding: 12px; background-color: {color}; 
                      color: white; text-decoration: none; border-radius: 8px; font-weight: bold; 
                      margin-bottom: 10px; transition: 0.3s;">
                📥 【 {filename} 】を開く / 印刷する
            </a>
            '''
            st.markdown(html_button, unsafe_allow_html=True)

        # 実際に作成したテストの名前をファイル名に組み込む
        gen_name = st.session_state.get('generated_test_name', 'テスト')

        st.markdown("#### 📚 セット印刷（おすすめ！）")
        st.info("💡 1ページ目が問題、2ページ目が解答になっています。これ1つを両面印刷または2ページ印刷すれば完了です！")
        display_pdf(st.session_state['pdf_merged'], f"{quiz_name}_{gen_name}_問題解答セット.pdf", color="#28a745") 

        st.markdown("<br>#### 📄 個別データ（必要な場合のみ）", unsafe_allow_html=True)
        tab_q, tab_a = st.tabs(["📝 問題のみ", "💡 解答のみ"])
        with tab_q: display_pdf(st.session_state['pdf_q'], f"{quiz_name}_{gen_name}_問題のみ.pdf")
        with tab_a: display_pdf(st.session_state['pdf_a'], f"{quiz_name}_{gen_name}_解答のみ.pdf")