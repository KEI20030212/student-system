import streamlit as st
from utils.g_sheets import get_all_accounts, save_message

def render_message_sender_page():
    st.header("💌 メッセージ送信")
    st.markdown("他の先生や教室長にダイレクトメッセージを送ることができます。")

    # スプレッドシートから全アカウントのリストを取得
    accounts = get_all_accounts()

    # プルダウンで選びやすいように「〇〇 先生 (ID: xxx)」というリストを作ります
    user_options = {}
    for target_id, info in accounts.items():
        name = info.get("講師名", "不明")
        # 例: {"鈴木 先生 (ID: suzuki_t)": "suzuki_t"} 
        user_options[f"{name} 先生 (ID: {target_id})"] = target_id

    # 送信フォーム
    with st.container(border=True):
        with st.form("send_message_form", clear_on_submit=True):
            # 宛先を選択（上で作ったリストの「キー（日本語名）」を表示します）
            selected_label = st.selectbox("👤 宛先を選択", options=list(user_options.keys()))
            
            # メッセージ入力欄
            message_body = st.text_area("💬 メッセージ内容", height=150, placeholder="お疲れ様です。明日の授業についてですが...")
            
            # 送信ボタン
            submit = st.form_submit_button("メッセージを送信する 🚀", use_container_width=True)
            
            if submit:
                if not message_body.strip():
                    st.error("⚠️ メッセージを入力してください。")
                else:
                    # 宛先のIDと、自分のIDを取得
                    receiver_id = user_options[selected_label]
                    sender_id = st.session_state.get('user_id', 'unknown')
                    
                    with st.spinner("送信中..."):
                        # utils/g_sheets.py で作った関数を実行！
                        success = save_message(sender_id, receiver_id, message_body)
                        
                    if success:
                        st.success(f"✅ {selected_label} 宛にメッセージを送信しました！")