import streamlit as st
import pandas as pd
from utils.g_sheets import (
    get_quiz_master_dict, 
    upload_library_file, 
    list_library_files
)
from utils.api_guard import robust_api_call

# --- カテゴリーの定義 ---
CAT_QUIZ = "小テスト・確認テスト"
CAT_EXAM = "定期テスト過去問"

def render_cloud_library_page():
    st.header("📚 教材クラウド書庫")
    st.write("塾の公式プリント（小テスト、過去問など）を1秒で検索・ダウンロードできる共有書庫です。")
    
    # 権限の確認（アップロードエリアの表示制御）
    user_role = str(st.session_state.get('role', st.session_state.get('user_role', 'guest'))).lower()
    is_admin = user_role in ['admin', 'owner', 'am']
    
    # ==========================================
    # 🌟 検索用のマスターデータを取得
    # ==========================================
    with st.spinner("書庫のインデックスを読み込み中..."):
        # 小テスト名の一覧を取得（設定シートから自動抽出）
        quiz_details = robust_api_call(get_quiz_master_dict, fallback_value={})
        quiz_names = []
        for key in quiz_details.keys():
            if "_" in key:
                q_name = key.split("_", 1)[0]
                if q_name not in quiz_names:
                    quiz_names.append(q_name)
                    
        # 過去問の学校名リスト（※とりあえず固定でいくつか用意。後で設定シート等から取得可能にできます）
        school_names = [
            "田端中学校", "東十条中学校", "北中学校", "南中学校", "第一中学校", "第二中学校", "その他"
        ]

    st.divider()

    # ==========================================
    # 🌟 閲覧・ダウンロードエリア（全講師が利用可能）
    # ==========================================
    tab_quiz, tab_exam = st.tabs([f"📝 {CAT_QUIZ}", f"🏫 {CAT_EXAM}"])
    
    # --- タブ1: 小テスト・確認テスト ---
    with tab_quiz:
        st.subheader("📝 小テスト・確認テストを探す")
        if not quiz_names:
            st.warning("設定シートから小テスト名が取得できません。")
        else:
            selected_quiz = st.selectbox("📚 テキスト・テスト名を選択してください", ["-- 選択してください --"] + quiz_names)
            
            if selected_quiz != "-- 選択してください --":
                with st.spinner("書庫からPDFを探しています...🔍"):
                    # Driveからファイル一覧を取得
                    files = robust_api_call(list_library_files, CAT_QUIZ, selected_quiz, fallback_value=[])
                
                if files:
                    st.success(f"📂 **{selected_quiz}** のプリントが {len(files)} 件見つかりました！")
                    for file in files:
                        with st.container(border=True):
                            c1, c2 = st.columns([8, 2])
                            c1.markdown(f"📄 **{file.get('name')}**")
                            
                            # Driveのプレビュー/ダウンロードURL
                            link = file.get('webViewLink')
                            if link:
                                c2.link_button("👁️ 開く・印刷", link, use_container_width=True)
                else:
                    st.info(f"📂 **{selected_quiz}** のプリントはまだ書庫に登録されていません。")

    # --- タブ2: 定期テスト過去問 ---
    with tab_exam:
        st.subheader("🏫 定期テストの過去問を探す")
        selected_school = st.selectbox("🏫 学校名を選択してください", ["-- 選択してください --"] + school_names)
        
        if selected_school != "-- 選択してください --":
            with st.spinner("書庫からPDFを探しています...🔍"):
                files = robust_api_call(list_library_files, CAT_EXAM, selected_school, fallback_value=[])
            
            if files:
                st.success(f"📂 **{selected_school}** の過去問が {len(files)} 件見つかりました！")
                for file in files:
                    with st.container(border=True):
                        c1, c2 = st.columns([8, 2])
                        c1.markdown(f"📄 **{file.get('name')}**")
                        
                        link = file.get('webViewLink')
                        if link:
                            c2.link_button("👁️ 開く・印刷", link, use_container_width=True)
            else:
                st.info(f"📂 **{selected_school}** の過去問はまだ書庫に登録されていません。")

    # ==========================================
    # 📤 アップロードエリア（管理者専用！）
    # ==========================================
    if is_admin:
        st.divider()
        st.markdown("### 🔐 【管理者専用】新しい教材を登録する")
        st.caption("ここでアップロードしたファイルは、公式プリントとして全講師が検索・印刷できるようになります。")
        
        with st.expander("➕ 教材をクラウド書庫にアップロード", expanded=False):
            with st.form("upload_library_form"):
                u_cat = st.selectbox("📂 登録するカテゴリー", [CAT_QUIZ, CAT_EXAM])
                
                # 選んだカテゴリーによって、小カテゴリーのプルダウンを切り替える
                u_sub_cat = st.text_input("🏷️ サブカテゴリー（テキスト名または学校名を入力）", placeholder="例：英単語ターゲット1200 / 田端中学校")
                
                st.info("※テキスト名や学校名は、検索時のプルダウンの文字と完全に一致するように入力してください。")
                
                uploaded_file = st.file_uploader("📄 アップロードするPDF（または画像）", type=["pdf", "png", "jpg", "jpeg"])
                
                u_filename = st.text_input("📝 保存する時のファイル名（※空欄の場合は元のファイル名になります）", placeholder="例：中2_1学期中間テスト_数学問題.pdf")
                
                submit_upload = st.form_submit_button("🚀 この教材を書庫に登録する", type="primary")
                
                if submit_upload:
                    if not u_sub_cat:
                        st.error("⚠️ サブカテゴリー（テキスト名または学校名）を入力してください。")
                    elif not uploaded_file:
                        st.error("⚠️ ファイルが選択されていません。")
                    else:
                        with st.spinner("クラウド書庫にアップロード中...☁️"):
                            file_bytes = uploaded_file.getvalue()
                            final_filename = u_filename if u_filename else uploaded_file.name
                            mime_type = uploaded_file.type
                            
                            # 🌟 PythonからDriveへ直接保存！
                            success, result = robust_api_call(
                                upload_library_file,
                                u_cat,
                                u_sub_cat,
                                final_filename,
                                file_bytes,
                                mime_type,
                                fallback_value=(False, "APIエラー")
                            )
                            
                            if success:
                                st.success(f"🎉 **{final_filename}** を書庫に登録しました！")
                                time.sleep(1.5)
                                st.rerun()
                            else:
                                st.error(f"アップロードに失敗しました: {result}")