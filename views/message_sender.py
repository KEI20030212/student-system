import streamlit as st
from utils.g_sheets import get_all_accounts, save_message, get_sent_messages

def render_message_sender_page():
    st.header("💌 メッセージ送信")

    # 🌟 タブを作成
    tab1, tab2 = st.tabs(["✏️ メッセージを送る", "🕰️ 送信履歴を見る"])

    # IDのズレをなくす最強の辞書を準備
    raw_accounts = get_all_accounts()
    safe_accounts = {str(k).strip(): v for k, v in raw_accounts.items()}

    # ==========================================
    # タブ1：送信フォーム
    # ==========================================
    with tab1:
        st.markdown("他の先生や教室長にダイレクトメッセージを送ることができます。")
        
        user_options = {}
        for target_id, info in safe_accounts.items():
            name = info.get("講師名", "不明")
            user_options[f"{name} 先生 (ID: {target_id})"] = target_id

        with st.container(border=True):
            with st.form("send_message_form", clear_on_submit=True):
                selected_label = st.selectbox("👤 宛先を選択", options=list(user_options.keys()))
                message_body = st.text_area("💬 メッセージ内容", height=150, placeholder="お疲れ様です。明日の授業についてですが...")
                submit = st.form_submit_button("メッセージを送信する 🚀", use_container_width=True)
                
                if submit:
                    if not message_body.strip():
                        st.error("⚠️ メッセージを入力してください。")
                    else:
                        receiver_id = user_options[selected_label]
                        # 自分のIDも空白を消して綺麗にします
                        sender_id = str(st.session_state.get('user_id', 'unknown')).strip()
                        
                        with st.spinner("送信中..."):
                            success = save_message(sender_id, receiver_id, message_body)
                        if success:
                            st.success(f"✅ {selected_label} 宛にメッセージを送信しました！")

    # ==========================================
    # タブ2：送信履歴の表示
    # ==========================================
    with tab2:
        st.markdown("あなたがこれまでに送信したメッセージの履歴です。")
        
        my_user_id = str(st.session_state.get('user_id', '')).strip()
        if my_user_id:
            sent_msgs = get_sent_messages(my_user_id)
            
            if not sent_msgs:
                st.info("まだ送信したメッセージはありません。")
            else:
                # 👇 スクロールできるコンテナ
                with st.container(height=500):
                    for msg in sent_msgs:
                        date_str = msg.get("送信日時", "")
                        raw_receiver_id = msg.get("受信者ID", "")
                        text = msg.get("メッセージ内容", "")
                        
                        receiver_id = str(raw_receiver_id).strip()
                        # 受信者の名前を検索
                        receiver_name = safe_accounts.get(receiver_id, {}).get("講師名", receiver_id)
                        
                        with st.chat_message("assistant"):
                            st.markdown(f"**{receiver_name} 先生** 宛て 🕒 {date_str}")
                            st.write(text)