import streamlit as st
import io
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# 🌟 ステップ1でメモした「塾アプリ生徒画像フォルダ」のIDをここに貼り付けてください！
MAIN_FOLDER_ID = "1PptAgfwzUT-wR5bPyYHaCO_olsEzi8FS" 

# Google Drive APIを使うためのスコープ（権限範囲）
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service():
    """Google Drive APIに接続する"""
    creds_dict = dict(st.secrets["gcp_service_account_json"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    service = build('drive', 'v3', credentials=creds)
    return service

def get_or_create_student_folder(student_id, student_name):
    """生徒専用のフォルダを探す。無ければ自動で作る"""
    service = get_drive_service()
    folder_name = f"{student_id}_{student_name}"
    
    # 大元フォルダの中にある、この生徒のフォルダを検索
    query = f"'{MAIN_FOLDER_ID}' in parents and name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])
    
    if not items:
        # フォルダが存在しない場合は新しく作成する
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [MAIN_FOLDER_ID]
        }
        folder = service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')
    else:
        # 存在する場合はそのフォルダIDを返す
        return items[0]['id']

def upload_image_to_drive(student_id, student_name, file_name, file_bytes, mime_type):
    """生徒のフォルダに画像をアップロードする"""
    try:
        service = get_drive_service()
        
        # 生徒のフォルダIDを取得（無ければ作る）
        student_folder_id = get_or_create_student_folder(student_id, student_name)
        
        # 画像データをアップロード準備
        file_metadata = {
            'name': file_name,
            'parents': [student_folder_id]
        }
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
        
        # アップロード実行
        file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
        
        return True, file.get('webViewLink')
    except Exception as e:
        print(f"Driveアップロードエラー: {e}")
        return False, str(e)

def list_student_images(student_id, student_name):
    """生徒のフォルダ内の画像一覧を取得する"""
    try:
        service = get_drive_service()
        student_folder_id = get_or_create_student_folder(student_id, student_name)
        
        # フォルダ内のファイルを取得（作成日時の降順＝新しい順）
        query = f"'{student_folder_id}' in parents and trashed=false"
        results = service.files().list(
            q=query, 
            spaces='drive', 
            fields='files(id, name, webViewLink, createdTime, thumbnailLink)',
            orderBy='createdTime desc'
        ).execute()
        
        return results.get('files', [])
    except Exception as e:
        print(f"画像リスト取得エラー: {e}")
        return []