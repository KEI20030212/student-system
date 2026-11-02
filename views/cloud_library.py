# views/cloud_library.py

import streamlit as st
import pandas as pd
import time
import os
import requests
import base64
from utils.g_sheets import (
    get_quiz_master_dict,
    add_quiz_maker_sheet  
)
from utils.g_drive import (
    upload_library_file, 
    list_library_files,
    list_library_folders,
    delete_library_file  
)
from utils.api_guard import robust_api_call

CAT_QUIZ = "小テスト・確認テスト"
CAT_EXAM = "定期テスト過去問"

@st.cache_data(ttl=300, show_spinner=False)
def cached_get_quiz_master():
    return robust_api_call(get_quiz_master_dict, fallback_value={})

@st.cache_data(ttl=300, show_spinner=False)
def cached_list_library_folders(cat, sub_cat=None):
    # sub_catがNoneの場合は、そのカテゴリー直下のフォルダ一覧（テキスト名一覧）を取得する
    return robust_api_call(list_library_folders, cat, sub_cat, fallback_value=[])

@st.cache_data(ttl=300, show_spinner=False)
def cached_list_library_files(cat, sub_cat, chap):
    return robust_api_call(list_library_files, cat, sub_cat, chap, fallback_value=[])

def download_gdrive_file_safely(file_id):
    url = "https://drive.google.com/uc?export=download"
    session = requests.Session()
    res = session.get(url, params={'id': file_id}, stream=True)
    
    token = None
    for key, value in res.cookies.items():
        if key.startswith('download_warning'):
            token = value
            break
    
    if token:
        res = session.get(url, params={'id': file_id, 'confirm': token}, stream=True)
        
    return res.content

def render_cloud_library_page():
    st.header("📚 教材クラウド書庫")
    st.write("塾の公式プリント（小テスト、過去問など）を検索・閲覧・保存できる共有書庫です。")
    
    st.info("💡 **【スマホ・PC共通のご利用方法】**\n"
            "「📖 プレビューを開く」で内容を確認できます。\n"
            "保存・印刷する場合は、必ずファイルの横にある **「📥 取得する」 ➡ 「💾 本体に保存する」** ボタンを使用してください。（※Googleにログインしていなくても保存できます！）")
    
    user_role = str(st.session_state.get('role', st.session_state.get('user_role', 'guest'))).lower()
    is_admin = user_role in ['admin', 'owner', 'am']
    
    if 'lib_upload_key' not in st.session_state:
        st.session_state.lib_upload_key = 0
        
    if 'prepared_files' not in st.session_state:
        st.session_state.prepared_files = {}
    
    with st.spinner("書庫のインデックスを読み込み中..."):
        # 🌟 NEW: スプレッドシートからではなく、Driveから直接「存在するフォルダ名（テキスト名）」を取得
        quiz_names = cached_list_library_folders(CAT_QUIZ, None)
        school_names = cached_list_library_folders(CAT_EXAM, None)
        
        # もしDriveにフォルダが一つもない場合のフォールバック（保険）
        if not school_names:
            school_names = [
                "田端中学校", "東十条中学校", "北中学校", "南中学校", "第一中学校", "第二中学校", "その他"
            ]

    st.divider()

    def display_safe_download_link(pdf_bytes, filename, color="#FF4B4B"):
        b64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
        html_button = f'''
        <a href="data:application/octet-stream;base64,{b64_pdf}" download="{filename}" 
           style="display: block; text-align: center; padding: 8px 12px; background-color: {color}; 
                  color: white; text-decoration: none; border-radius: 8px; font-weight: bold; 
                  font-family: sans-serif; font-size: 14px; margin-top: 5px; transition: 0.3s;
                  border: 1px solid #ff3333;">
            💾 本体に保存する
        </a>
        '''
        st.markdown(html_button, unsafe_allow_html=True)

    def display_files(files_list):
        if not files_list:
            st.info("📂 この場所にプリントはまだ登録されていません。")
            return
            
        st.success(f"📂 プリントが {len(files_list)} 件見つかりました！")
        
        for file in files_list:
            file_id = file.get('id')
            file_name = file.get('name', '無題のファイル')
            
            with st.container(border=True):
                if is_admin:
                    c1, c2, c3 = st.columns([5, 3, 2])
                else:
                    c1, c2 = st.columns([7, 3])
                
                c1.markdown(f"📄 **{file_name}**")
                
                if file_id:
                    with st.expander("📖 プレビューを開く"):
                        embed_url = f"https://drive.google.com/file/d/{file_id}/preview"
                        st.markdown(
                            f'<iframe src="{embed_url}" width="100%" height="400" style="border: none; border-radius: 8px;"></iframe>',
                            unsafe_allow_html=True
                        )
                        st.caption("⚠️ プレビュー画面内のダウンロードボタンは、ログインしていないと白紙になります。保存は下の赤いボタンから行ってください。")
                    
                    if file_id in st.session_state.prepared_files:
                        file_bytes = st.session_state.prepared_files[file_id]
                        
                        ext = os.path.splitext(file_name)[1].lower()
                        safe_file_name = file_name + ".pdf" if not ext else file_name
                        
                        with c2:
                            display_safe_download_link(file_bytes, safe_file_name)
                    else:
                        if c2.button("📥 取得する", key=f"prep_{file_id}", use_container_width=True):
                            with st.spinner("システム経由でファイルを抽出中..."):
                                try:
                                    file_bytes = download_gdrive_file_safely(file_id)
                                    
                                    if not file_bytes.startswith(b'<!DOCTYPE html>') and not file_bytes.startswith(b'<html'):
                                        st.session_state.prepared_files[file_id] = file_bytes
                                        st.rerun() 
                                    else:
                                        st.error("⚠️ 権限エラー：Googleドライブの共有設定が「リンクを知っている全員（閲覧者）」になっていない可能性があります。")
                                except Exception as e:
                                    st.error(f"取得エラー: {e}")
                else:
                    c2.caption("⚠️ リンク無効")
                
                if is_admin:
                    if c3.button("🗑️ 削除", key=f"del_{file_id}", type="secondary", use_container_width=True):
                        with st.spinner(f"「{file_name}」を削除中..."):
                            success, msg = robust_api_call(delete_library_file, file_id, fallback_value=(False, "エラー"))
                            if success:
                                st.success("✅ 削除しました。")
                                st.cache_data.clear() 
                                time.sleep(1)
                                st.rerun() 
                            else:
                                st.error(f"削除に失敗しました: {msg}")

    tab_quiz, tab_exam = st.tabs([f"📝 {CAT_QUIZ}", f"🏫 {CAT_EXAM}"])
    
    with tab_quiz:
        st.subheader("📝 小テスト・確認テストを探す")
        if not quiz_names:
            st.warning("クラウド書庫(Googleドライブ)に登録されているテキストがありません。")
        else:
            selected_quiz = st.selectbox("📚 テキスト・テスト名を選択", ["-- 選択してください --"] + quiz_names, key="sel_q_txt")
            if selected_quiz != "-- 選択してください --":
                chapter_folders = cached_list_library_folders(CAT_QUIZ, selected_quiz)
                selected_chapter = None
                if chapter_folders:
                    selected_chapter = st.selectbox("📖 単元・章を選択", ["-- 選択してください --", "-- 直下のファイル --"] + chapter_folders, key="sel_q_chap")
                if not chapter_folders or (chapter_folders and selected_chapter and selected_chapter != "-- 選択してください --"):
                    files = cached_list_library_files(CAT_QUIZ, selected_quiz, selected_chapter)
                    display_files(files) 

    with tab_exam:
        st.subheader("🏫 定期テストの過去問を探す")
        if not school_names:
             st.warning("クラウド書庫(Googleドライブ)に登録されている学校がありません。")
        else:
            selected_school = st.selectbox("🏫 学校名を選択", ["-- 選択してください --"] + school_names, key="sel_e_sch")
            if selected_school != "-- 選択してください --":
                exam_folders = cached_list_library_folders(CAT_EXAM, selected_school)
                selected_exam_chap = None
                if exam_folders:
                    selected_exam_chap = st.selectbox("📅 年度・テスト時期を選択", ["-- 選択してください --", "-- 直下のファイル --"] + exam_folders, key="sel_e_chap")
                if not exam_folders or (exam_folders and selected_exam_chap and selected_exam_chap != "-- 選択してください --"):
                    files = cached_list_library_files(CAT_EXAM, selected_school, selected_exam_chap)
                    display_files(files) 

    if is_admin:
        st.divider()
        st.markdown("### 🔐 【管理者専用】新しい教材を登録する")
        
        with st.expander("➕ 新しい小テストをリストに登録する"):
            st.write("新しい小テストの情報をシステムに保存します！")
            st.write("スプレッドシートのリンクを登録すると「単語テスト作成」から小テストを作成することができます！")
            
            with st.form("add_quiz_form_cloud"):
                new_name = st.text_input("📝 テストの名前 (例: 中2 数学 計算ドリル)")
                new_id = st.text_input("🔑 スプレッドシートのID (後から設定する場合は空欄でOK)", placeholder="1A2B3C4D5E6F7G...")
                
                col_m, col_s = st.columns(2)
                with col_m:
                    new_full_marks = st.number_input("💯 満点", min_value=1, value=100)
                with col_s:
                    new_paper_size = st.selectbox("🖨️ 印刷サイズ", ["A4", "B4", "A3", "B5"])

                submit_new = st.form_submit_button("リストに登録する ✨")
                
                if submit_new:
                    if new_name:
                        save_id = new_id.strip() if new_id else ""
                        success = robust_api_call(add_quiz_maker_sheet, new_name, save_id, new_full_marks, new_paper_size, fallback_value=False)
                        if success:
                            st.success(f"「{new_name}」({new_paper_size}サイズ) をリストに登録しました！")
                            st.cache_data.clear() 
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("登録に失敗しました。")
                    else:
                        st.warning("⚠️ テストの名前は必ず入力してください。")

        with st.expander("➕ 教材(PDF)をクラウド書庫にアップロード", expanded=False):
            st.write("PDFをアップロードすることで誰でもPDFをダウンロード、印刷することができます！")
            
            reset_k = st.session_state.lib_upload_key
            
            # 🌟 NEW: アップロード時もDriveに存在するフォルダ名を選択肢にする（+直接入力も可）
            u_cat = st.selectbox("📂 登録するカテゴリー", [CAT_QUIZ, CAT_EXAM], key=f"u_cat_{reset_k}")
            
            # 選択されたカテゴリーに応じて、Drive上の既存フォルダ名を取得
            existing_sub_cats = quiz_names if u_cat == CAT_QUIZ else school_names
            
            # 既存のものを選択するか、新しい名前を入力するか選べるようにする
            u_sub_cat_selection = st.selectbox("🏷 既存のテキスト/学校名から選択", ["-- 新規入力する --"] + existing_sub_cats, key=f"u_sub_cat_sel_{reset_k}")
            
            if u_sub_cat_selection == "-- 新規入力する --":
                u_sub_cat = st.text_input("📝 新しいテキスト名 または 学校名を入力", placeholder="例：ターゲット1200 / 田端中学校", key=f"u_sub_cat_new_{reset_k}")
            else:
                u_sub_cat = u_sub_cat_selection
                
            uploaded_files = st.file_uploader("📄 アップロードするPDF（複数選択可）", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True, key=f"u_files_{reset_k}")
            if uploaded_files:
                st.markdown("#### ⚙️ 各ファイルの設定")
                file_settings = []
                for i, file_obj in enumerate(uploaded_files):
                    with st.container(border=True):
                        st.markdown(f"**📄 {file_obj.name}**")
                        c_chap, c_name = st.columns(2)
                        default_chap = os.path.splitext(file_obj.name)[0]
                        chap_val = c_chap.text_input("📖 単元・章（フォルダ名）", value=default_chap, key=f"chap_{reset_k}_{i}")
                        name_val = c_name.text_input("📝 保存するファイル名", value=file_obj.name, key=f"name_{reset_k}_{i}")
                        file_settings.append({"obj": file_obj, "chap": chap_val, "name": name_val})
                
                if st.button("🚀 この設定で教材を一括登録する", type="primary", use_container_width=True):
                    if not u_sub_cat:
                        st.error("⚠️ テキスト名 または 学校名 を入力してください。")
                    else:
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        success_count = 0
                        error_messages = []
                        for i, setting in enumerate(file_settings):
                            status_text.text(f"アップロード中... ({i+1}/{len(file_settings)}): {setting['name']}")
                            success, result = robust_api_call(upload_library_file, u_cat, u_sub_cat, setting["chap"], setting["name"], setting["obj"].getvalue(), setting["obj"].type, fallback_value=(False, "APIエラー"))
                            if success: success_count += 1
                            else: error_messages.append(f"{setting['name']}: {result}")
                            progress_bar.progress((i + 1) / len(file_settings))
                        
                        status_text.empty()
                        if success_count == len(file_settings):
                            st.success(f"🎉 【{u_sub_cat}】に {success_count}件 登録しました！")
                            st.cache_data.clear() 
                            time.sleep(2)
                            st.session_state.lib_upload_key += 1 
                            st.rerun()
                        elif success_count > 0:
                            st.warning(f"⚠️ {success_count}件 登録完了（一部失敗）")
                            for err in error_messages: st.error(err)
                        else:
                            st.error("アップロード失敗")
                            for err in error_messages: st.error(err)