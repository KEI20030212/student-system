import streamlit as st
import requests
import base64

def render_self_study_dashboard():
    st.header("📊 学習時間ダッシュボード")
    
    st.write("スプレッドシート側で作成・デザインされた最新のグラフを、安全に画像としてダウンロードできます✨")
    st.caption("※スプレッドシート側でグラフの色やタイトルを変更すると、次に取得した時に即座に反映されます。")
    
    st.divider()

    # 🌟 追加：取得するグラフの対象（学年）を選択
    target_grade = st.radio(
        "🏫 グラフを取得する対象（スプレッドシート）を選択してください", 
        ["小学生", "中学生", "高校生"], 
        horizontal=True
    )

    # ==========================================
    # 🌟 各スプレッドシートごとのGASのURLを設定
    # ==========================================
    # ※ 先ほど作成していただいたURLは「全体」として設定しています
    GAS_URLS = {
        "小学生": "https://script.google.com/macros/s/AKfycbxmaI040Qm0iDYykcP14JWw-eID_jeh_2oauTpW6ysYtYkdamtgn4uMLDYts72AQ71s/exec",
        "中学生": "https://script.google.com/macros/s/AKfycbyFMRO5HJXNH7rh8TELMU5DXta_1qINJ41AexRe5KX0kOMDu-kXMG5ZJxNkiYgHSmQn7w/exec",
        "高校生": "https://script.google.com/macros/s/AKfycbxEXhITzJWJrW7P_LdI1tEzFFm8p3YwoEUQ5u_-ZGmQj_GzV3dCbRJRk4a8v2SeEBgz/exec"
    }
    
    # 選択された対象のURLを取得
    GAS_URL = GAS_URLS.get(target_grade)
    SECRET_KEY = "juku-graph-2026"
    
    if GAS_URL == "https://script.google.com/macros/s/AKfycbxmaI040Qm0iDYykcP14JWw-eID_jeh_2oauTpW6ysYtYkdamtgn4uMLDYts72AQ71s/exec" or GAS_URL == "https://script.google.com/macros/s/AKfycbyFMRO5HJXNH7rh8TELMU5DXta_1qINJ41AexRe5KX0kOMDu-kXMG5ZJxNkiYgHSmQn7w/exec" or GAS_URL == "https://script.google.com/macros/s/AKfycbxEXhITzJWJrW7P_LdI1tEzFFm8p3YwoEUQ5u_-ZGmQj_GzV3dCbRJRk4a8v2SeEBgz/exec":
        st.warning(f"⚠️ 【{target_grade}】用のGASのURLがまだ設定されていません！コードの中のURLを書き換えてください。")
        return
        
    if st.button(f"🚀 【{target_grade}】の最新グラフ画像をスプレッドシートから取得する", type="primary", use_container_width=True):
        
        with st.spinner(f"【{target_grade}】のスプレッドシートからグラフを画像化して引っ張っています...（約3秒）"):
            try:
                # GASの秘密のトンネルにリクエストを送って、画像データを取得する
                response = requests.get(f"{GAS_URL}?key={SECRET_KEY}", timeout=20)
                
                if response.status_code == 200:
                    result_text = response.text
                    
                    if result_text == "認証エラー" or "エラー" in result_text or result_text == "グラフが見つかりません":
                        st.error(f"❌ 画像の取得に失敗しました: {result_text}")
                    else:
                        # 暗号化された文字データを、本物の画像（バイナリ）に復元
                        image_bytes = base64.b64decode(result_text)
                        
                        st.success(f"✅ 【{target_grade}】のグラフ画像の取得に成功しました！プレビューを確認してダウンロードしてください。")
                        
                        # プレビュー表示
                        with st.container(border=True):
                            st.image(image_bytes, use_container_width=True)
                        
                        # 🌟 ダウンロードされるファイル名も「学習時間グラフ_中学生.png」のように自動で変わります！
                        st.download_button(
                            label=f"📥 【{target_grade}】のグラフ画像をダウンロードする（PNG形式）",
                            data=image_bytes,
                            file_name=f"学習時間グラフ_{target_grade}.png",
                            mime="image/png",
                            type="primary",
                            use_container_width=True
                        )
                else:
                    st.error(f"通信エラーが発生しました。（ステータスコード: {response.status_code}）")
            except Exception as e:
                st.error(f"システムエラー: {str(e)}")