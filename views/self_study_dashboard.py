import streamlit as st
import streamlit.components.v1 as components

def render_self_study_dashboard():
    # --- 🖨️ iframe（埋め込み）に最適化された印刷用の魔法 ---
    st.markdown("""
        <style>
        @media print {
            @page {
                size: landscape; 
                margin: 5mm 10mm;
            }

            /* 枠の制限を完全に解除 */
            html, body, [data-testid="stApp"], .main, .block-container, 
            [data-testid="stAppViewContainer"], [data-testid="stAppViewBlockContainer"] {
                display: block !important;
                width: 100% !important;
                max-width: 100% !important;
                padding: 0 !important;
                margin: 0 !important;
            }

            /* 印刷に不要なものをすべて隠す */
            header, footer, [data-testid="stHeader"], [data-testid="stSidebar"], 
            .stButton, [data-testid="stAlert"], iframe[title="streamlit_components.v1.components.html"] { 
                display: none !important; 
            }

            /* 🌟 iframe（スプレッドシート）を印刷画面いっぱいに広げる */
            iframe {
                display: block !important;
                width: 100% !important;
                height: 1000px !important; /* 印刷時に見切れないように高さを固定 */
                border: none !important;
            }

            /* 背景色・文字色の調整 */
            * {
                background-color: transparent !important;
                color: black !important;
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
            }
        }
        </style>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([3, 2])
    with col1:
        st.subheader("📊 学習時間ダッシュボード")
    with col2:
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("🔄 画面を更新", use_container_width=True):
                st.rerun() 
                
        with btn_col2:
            components.html(
                """
                <style>body { margin: 0; padding: 2px; box-sizing: border-box; }</style>
                <div style="display: flex; justify-content: center; align-items: center; height: 100%;">
                    <button onclick="window.parent.print()" style="
                        background-color: white; border: 1px solid #dcdcdc; color: #31333F;
                        padding: 0.35rem 0.75rem; font-size: 16px; border-radius: 8px;
                        cursor: pointer; width: 100%; font-family: sans-serif;
                        box-shadow: 0px 1px 2px rgba(0,0,0,0.05); transition: all 0.2s ease;
                    " onmouseover="this.style.borderColor='#ff4b4b'; this.style.color='#ff4b4b';" 
                      onmouseout="this.style.borderColor='#dcdcdc'; this.style.color='#31333F';">
                        🖨️ グラフを印刷
                    </button>
                </div>
                """,
                height=55
            )

    st.info("💡 裏側のスプレッドシートで自動生成された最新のグラフを直接表示しています。")

    # ==========================================
    # 🌟 ここにコピーしたURLを貼り付けてください！
    # ==========================================
    SPREADSHEET_EMBED_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS78tDbT0Ik0qBDg1zYBVz5zhWiIBlM_SAbYB4XWaq-7sVPr3-71VvMBkQpJ6Wfh_UTWGieeUOoXa2O/pubhtml?gid=1075469916&amp;single=true&amp;widget=true&amp;headers=false"

    if SPREADSHEET_EMBED_URL == "https://docs.google.com/spreadsheets/d/e/2PACX-1vS78tDbT0Ik0qBDg1zYBVz5zhWiIBlM_SAbYB4XWaq-7sVPr3-71VvMBkQpJ6Wfh_UTWGieeUOoXa2O/pubhtml?gid=1075469916&amp;single=true&amp;widget=true&amp;headers=false":
        st.warning("⚠️ コード内の `SPREADSHEET_EMBED_URL` に、スプレッドシートの公開URLを貼り付けてください！")
    else:
        # スプレッドシートの画面を埋め込み表示（スクロールバー付き）
        components.iframe(SPREADSHEET_EMBED_URL, height=800, scrolling=True)