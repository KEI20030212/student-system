import streamlit as st
import pandas as pd
import datetime
import time
import io
from PIL import Image, ImageEnhance, ImageOps 

from utils.g_sheets import get_student_master
from utils.g_drive import upload_image_to_drive, list_student_images
from utils.api_guard import robust_api_call

@st.cache_data(ttl=600)
def cached_get_student_master():
    return robust_api_call(get_student_master, fallback_value=pd.DataFrame())

def process_image_quality(file_bytes, mode):
    """本格的なスキャナー品質に引き上げる魔法の画像処理関数"""
    try:
        img = Image.open(io.BytesIO(file_bytes))
        
        if img.mode != 'RGB':
            img = img.convert('RGB')
            
        if mode == "✨ 文字くっきり（コントラストUP）":
            # 1. オートコントラストで写真全体の明暗バランスを最適化
            img = ImageOps.autocontrast(img, cutoff=2)
            # 2. シャープネスを限界まで上げて文字のフチを強調
            img = ImageEnhance.Sharpness(img).enhance(2.5)
            # 3. コントラストと明るさを微調整
            img = ImageEnhance.Contrast(img).enhance(1.3)
            img = ImageEnhance.Brightness(img).enhance(1.1)
            
        elif mode == "📄 モノクロスキャン風（白黒強調）":
            # 1. まず白黒にする
            img = ImageOps.grayscale(img)
            # 2. オートコントラストで薄い文字を浮かび上がらせる
            img = ImageOps.autocontrast(img, cutoff=2)
            
            # 🌟 3. 新技術：影を完全に消し去る魔法の閾値（しきい値）処理
            # （160以上の明るいグレーは影とみなして真っ白(255)に飛ばし、それ以下の文字部分はより真っ黒(0)に近づける）
            def clean_background(p):
                if p > 160: 
                    return 255
                else:
                    return max(0, int(p * 0.7))
            
            img = img.point(clean_background)
            img = img.convert('RGB')

        out_buf = io.BytesIO()
        # 🌟 保存時の劣化をゼロにする（最高画質100、色にじみ防止）
        img.save(out_buf, format="JPEG", quality=100, subsampling=0)
        return out_buf.getvalue(), "image/jpeg"
    except Exception as e:
        return file_bytes, None

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

    # 画質補正オプション
    quality_mode = st.radio(
        "🎨 画像の画質補正モードを選択してください",
        ["オリジナル（そのまま）", "✨ 文字くっきり（コントラストUP）", "📄 モノクロスキャン風（白黒強調）"],
        horizontal=True,
        help="鉛筆の文字や影を補正します。おすすめは「モノクロスキャン風」です！"
    )

    # 🌟 画質を上げるための重要なアナウンスを変更
    st.info("💡 **高画質で残すコツ:** スマホ標準のカメラアプリで明るく綺麗に撮影してからアップロードするのが最も高画質になります！")

    # タブをなくし、ファイルアップローダーを直接表示
    uploaded_file = st.file_uploader("📂 画像ファイルを選択してください (JPG / PNG)", type=["jpg", "jpeg", "png"], key=f"file_{student_id}")

    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        mime_type = uploaded_file.type
        
        if quality_mode != "オリジナル（そのまま）":
            with st.spinner("✨ 画像を最高画質でクッキリ補正中..."):
                file_bytes, new_mime = process_image_quality(file_bytes, quality_mode)
                if new_mime:
                    mime_type = new_mime
        
        now_date = datetime.date.today().strftime("%Y%m%d")
        
        c_meta1, c_meta2 = st.columns(2)
        subj = c_meta1.selectbox("教科", ["英語", "数学", "国語", "理科", "社会", "その他"], key=f"meta_sub_{student_id}")
        title_suffix = c_meta2.text_input("補足名 (任意)", placeholder="単元名やテスト名", key=f"meta_title_{student_id}")
        
        suffix_str = f"_{title_suffix}" if title_suffix.strip() else ""
        ext = "jpg" if quality_mode != "オリジナル（そのまま）" else mime_type.split('/')[-1]
        file_name = f"{now_date}_{subj}{suffix_str}.{ext}"

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
        
        cols = st.columns(3)
        for idx, img in enumerate(images):
            col_idx = idx % 3
            with cols[col_idx]:
                with st.container(border=True):
                    st.markdown(f"**{img.get('name')}**")
                    
                    c_time = img.get('createdTime', '')
                    if c_time:
                        try:
                            dt = datetime.datetime.strptime(c_time, "%Y-%m-%dT%H:%M:%S.%fZ")
                            st.caption(f"📅 {dt.strftime('%Y/%m/%d %H:%M')}")
                        except:
                            st.caption(f"📅 {c_time[:10]}")
                    
                    thumb = img.get('thumbnailLink')
                    if thumb:
                        st.image(thumb, use_container_width=True)
                    else:
                        st.caption("（プレビュー不可）")
                        
                    st.markdown(f"[🔗 Google Driveで開く]({img.get('webViewLink')})")