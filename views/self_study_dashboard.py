import streamlit as st
import requests
import base64

def render_self_study_dashboard():
    st.header("📊 学習時間ダッシュボード")
    
    st.write("スプレッドシート側で作成・デザインされた最新のグラフを、安全に画像としてダウンロードできます✨")
    st.caption("※スプレッドシート側でグラフの色やタイトルを変更すると、次に取得した時に即座に反映されます。")
    
    st.divider()

    # ==========================================
    # 🌟 ここにGASでコピーしたURLを貼り付けてください！
    # ==========================================
    GAS_URL = "https://script.google.com/macros/s/AKfycbyFMRO5HJXNH7rh8TELMU5DXta_1qINJ41AexRe5KX0kOMDu-kXMG5ZJxNkiYgHSmQn7w/exec"
    SECRET_KEY = "juku-graph-2026"
    
    if GAS_URL == "ここにコピーしたURLを貼り付けます":
        st.warning("⚠️ まずは準備手順に従ってGASをデプロイし、URLをコードに貼り付けてください！")
        return
        
    if st.button("🚀 最新のグラフ画像をスプレッドシートから取得する", type="primary", use_container_width=True):
        
        with st.spinner("スプレッドシートの裏側からグラフを画像化して引っ張っています...（約3秒）"):
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
                        
                        st.success("✅ グラフ画像の取得に成功しました！プレビューを確認してダウンロードしてください。")
                        
                        # プレビュー表示
                        with st.container(border=True):
                            st.image(image_bytes, use_container_width=True)
                        
                        # ダウンロードボタン
                        st.download_button(
                            label="📥 このグラフ画像をダウンロードする（PNG形式）",
                            data=image_bytes,
                            file_name="学習時間グラフ.png",
                            mime="image/png",
                            type="primary",
                            use_container_width=True
                        )
                else:
                    st.error(f"通信エラーが発生しました。（ステータスコード: {response.status_code}）")
            except Exception as e:
                st.error(f"システムエラー: {str(e)}")