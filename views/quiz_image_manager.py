import streamlit as st
import pandas as pd
import datetime
import time
from utils.g_sheets import get_student_master
from utils.g_drive import upload_image_to_drive, list_student_images
from utils.api_guard import robust_api_call

@st.cache_data(ttl=600)
def cached_get_student_master():
    return robust_api_call(get_student_master, fallback_value=pd.DataFrame())

def render_quiz_image_manager_page():
    st.header("📸 小テスト・画像管理")
    st.write("生徒の小テストの答案や、残しておきたいノートの写真をGoogle Driveへ保存・確認できます✨")

    df_students = cached_get_student_master()
    if df_students.empty:
        st.error("生徒データの取得に失敗しました。時間をおいて再読み込みしてください。")
        st.stop()

    student_options = (df_students['生徒ID'].astype(str) + " - " + df_students['生徒名']).tolist()
    selected_student = st.selectbox("👤 生徒を選択してください", student_options, index=None, placeholder="--選択--")

    if selected_student is None:
        st.info("👆 生徒を選択すると、画像のアップロードや過去の答案ギャラリーが開きます。")
        return

    student_id = selected_student.split(" - ")[0]
    student_name = selected_student.split(" - ")[1]

    st.divider()
    st.subheader(f"✍️ {student_name} さんの小テスト登録")

    # 🌟 アップロード方法をタブで切り替え（カメラ or ファイル選択）
    tab_cam, tab_file = st.tabs(["📷 スマホカメラで撮影", "📂 写真ファイルを選択"])
    
    uploaded_file = None
    file_bytes = None
    mime_type = None

    with tab_cam:
        cam_image = st.camera_input("答案をカメラに正対させて撮影してください", key=f"cam_{student_id}")
        if cam_image:
            uploaded_file = cam_image
            
    with tab_file:
        file_image = st.file_uploader("画像ファイルを選択してください (JPG / PNG)", type=["jpg", "jpeg", "png"], key=f"file_{student_id}")
        if file_image:
            uploaded_file = file_image

    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        mime_type = uploaded_file.type
        
        # わかりやすいファイル名を自動生成（例: 20260520_数学_小テスト.png）
        now_date = datetime.date.today().strftime("%Y%m%d")
        
        c_meta1, c_meta2 = st.columns(2)
        subj = c_meta1.selectbox("教科", ["英語", "数学", "国語", "理科", "社会", "その他"], key=f"meta_sub_{student_id}")
        title_suffix = c_meta2.text_input("補足名 (任意)", placeholder="単元名やテスト名", key=f"meta_title_{student_id}")
        
        suffix_str = f"_{title_suffix}" if title_suffix.strip() else ""
        file_name = f"{now_date}_{subj}{suffix_str}.{mime_type.split('/')[-1]}"

        if st.button("🚀 Google Driveへ写真を保存する", type="primary", use_container_width=True):
            with st.spinner("Google Driveへアップロード中..."):
                success, result = robust_api_call(
                    upload_image_to_drive,
                    student_id=student_id,
                    student_name=student_name,
                    file_name=file_name,
                    file_bytes=file_bytes,
                    mime_type=mime_type,
                    fallback_value=(False, "タイムアウト")
                )
                
                if success:
                    st.success(f"✅ 【{file_name}】を正常に保存しました！")
                    time.sleep(1.5)
                    st.rerun()
                else:
                    st.error(f"❌ アップロードに失敗しました: {result}")

    # ==========================================
    # 🖼️ 過去の答案ギャラリー表示セクション
    # ==========================================
    st.divider()
    st.subheader("🖼️ 過去の答案ギャラリー")
    
    with st.spinner("Google Driveから画像履歴を読み込み中..."):
        images = robust_api_call(list_student_images, student_id, student_name, fallback_value=[])

    if not images:
        st.info("まだこの生徒のフォルダに写真はありません。上のフォームから最初の1枚を登録してみましょう！")
    else:
        st.caption("💡 新しい写真から順番に並んでいます。クリックするとGoogle Drive上で原寸大の確認が可能です。")
        
        # 3列のグリッド形式できれいに写真を並べる
        cols = st.columns(3)
        for idx, img in enumerate(images):
            col_idx = idx % 3
            with cols[col_idx]:
                with st.container(border=True):
                    st.markdown(f"**{img.get('name')}**")
                    
                    # タイムスタンプの整形
                    c_time = img.get('createdTime', '')
                    if c_time:
                        try:
                            dt = datetime.datetime.strptime(c_time, "%Y-%m-%dT%H:%M:%S.%fZ")
                            st.caption(f"📅 {dt.strftime('%Y/%m/%d %H:%M')}")
                        except:
                            st.caption(f"📅 {c_time[:10]}")
                    
                    # サムネイル表示（Drive APIから提供される高速軽量リンクを使用）
                    thumb = img.get('thumbnailLink')
                    if thumb:
                        st.image(thumb, use_container_width=True)
                    else:
                        st.caption("（プレビュー不可）")
                        
                    # 原寸大リンクボタン
                    st.markdown(f"[🔗 Google Driveで開く]({img.get('webViewLink')})")