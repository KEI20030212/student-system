import streamlit as st
import pandas as pd
import time
import datetime
import re # 🌟 追加：文字の抽出に使うため追加

from utils.g_sheets import (
    load_board_message,
    save_board_message,
    get_all_logs,      
    load_quiz_records,
    load_transfer_requests 
)
from utils.api_guard import robust_api_call

def safe_get_all_logs():
    df = robust_api_call(get_all_logs, fallback_value=pd.DataFrame())
    return df.copy() if not df.empty else df

def safe_load_quiz_records():
    df = robust_api_call(load_quiz_records, fallback_value=pd.DataFrame())
    return df.copy() if not df.empty else df

def safe_load_transfer_requests():
    df = robust_api_call(load_transfer_requests, fallback_value=pd.DataFrame())
    return df.copy() if not df.empty else df


def render_home_page():
    st.header("📢 連絡掲示板")
    
    user_role = st.session_state.get('role', '')

    # ==========================================
    # 🌟 管理者専用：自動検知アラートエリア
    # ==========================================
    if user_role in ['admin', 'owner', 'head_teacher', 'am']:
        
        # 🛎️ 1. 新機能：振替申請アラート
        df_transfers = safe_load_transfer_requests()
        if not df_transfers.empty:
            # 🌟 【重要な修正1】Googleフォーム特有の「見えない空白」や「改行」を除去
            df_transfers.columns = df_transfers.columns.str.strip().str.replace('\n', '')
            
            # 🌟 【重要な修正2】'nan' という文字が表示されないように、空のセルを空文字に置き換え
            df_transfers = df_transfers.fillna("")
            
            if 'タイムスタンプ' in df_transfers.columns:
                # タイムスタンプ列は日付計算のために一度日付型に直す（別列として扱う）
                df_transfers['タイムスタンプ_dt'] = pd.to_datetime(df_transfers['タイムスタンプ'], format='mixed', errors='coerce')
                
                seven_days_ago = pd.Timestamp.now() - pd.Timedelta(days=7)
                recent_transfers = df_transfers[df_transfers['タイムスタンプ_dt'] >= seven_days_ago].sort_values('タイムスタンプ_dt', ascending=False)
                
                if not recent_transfers.empty:
                    st.warning(f"🔔 **【新着のお振替申請】** 直近7日以内に **{len(recent_transfers)}件** の申請が届いています！")
                    
                    for _, row in recent_transfers.iterrows():
                        # 日付フォーマット
                        dt_val = row['タイムスタンプ_dt']
                        ts = dt_val.strftime('%m/%d %H:%M') if pd.notna(dt_val) else "不明"
                        
                        student = str(row.get('生徒氏名', '不明')).strip()
                        
                        # 欠席予定日（綺麗に掃除してあるので一発で取得可能！）
                        absent_date_raw = str(row.get('欠席予定の授業日', '不明')).strip()
                        absent_date = absent_date_raw.split(' ')[0] if absent_date_raw else "不明"
                        absent_time = str(row.get('欠席予定の授業時間', '')).strip()
                        
                        with st.expander(f"👤 {student} 様 （送信: {ts} / 欠席予定: {absent_date}）"):
                            st.markdown(f"**■ 欠席予定:** {absent_date} {absent_time}")
                            st.markdown(f"**■ 理由:** {row.get('お振替の理由', '')}")
                            
                            # 🌟 【重要な修正3】「[月曜日]」などの曜日が含まれる列を自動検知して抽出
                            hope_days = []
                            for col in df_transfers.columns:
                                if "曜日" in col and "[" in col and "]" in col:
                                    val = str(row.get(col, '')).strip()
                                    if val: # 空欄でなければ追加
                                        # "お振替希望日 [月曜日]" -> "月曜日" だけを綺麗に取り出す
                                        day_match = re.search(r'\[(.*?)\]', col)
                                        day_name = day_match.group(1) if day_match else col
                                        hope_days.append(f"{day_name}: {val}")
                            
                            if hope_days:
                                st.markdown(f"**■ 振替希望:**\n" + " \n".join([f"- {h}" for h in hope_days]))
                                
                            st.markdown(f"**■ 希望時間:** {row.get('お振替希望授業時間', '')}")
                            st.markdown(f"**■ 備考:** {row.get('備考欄', '')}")
                            st.markdown(f"[🔗 スプレッドシートで全回答を確認する](https://docs.google.com/spreadsheets/d/1j93KTSKjywAQoslEPt-osRMzOMSiheb8GrT77gLgPko/edit)")

        # 🛎️ 2. 既存：URL抜け（小テスト未実施）の自動検知アラート
        df_logs = safe_get_all_logs() 
        df_quizzes = safe_load_quiz_records() 
        today = datetime.date.today()
        
        if not df_logs.empty and "APIエラー発生" not in df_logs.columns:
            df_logs['日時'] = pd.to_datetime(df_logs['日時'], format='mixed', errors='coerce')
            today_logs = df_logs[df_logs['日時'].dt.date == today]
            
            if not today_logs.empty:
                name_col = '名前' if '名前' in today_logs.columns else '生徒名'
                today_students = today_logs[name_col].drop_duplicates().tolist()
                
                missing_url_students = []
                for student in today_students:
                    has_quiz = False
                    if not df_quizzes.empty and "APIエラー発生" not in df_quizzes.columns:
                        df_quizzes['日時'] = pd.to_datetime(df_quizzes['日時'], format='mixed', errors='coerce')
                        student_quizzes = df_quizzes[(df_quizzes['名前'] == student) & (df_quizzes['日時'].dt.date == today)]
                        if not student_quizzes.empty:
                            has_quiz = True
                            
                    if not has_quiz:
                        missing_url_students.append(student)
                        
                if missing_url_students:
                    st.error(f"🚨 **【答案確認URL 未添付アラート】**\n\n本日授業記録がある以下の生徒は、小テスト結果が未登録のためLINE報告書にDriveのURLが添付されていません。画像アップロードと小テスト結果の登録漏れがないか確認してください。\n\n**{', '.join(missing_url_students)}**")

    st.divider()
    
    # ==========================================
    # 🌟 掲示板エリア
    # ==========================================
    st.subheader("📌 講師向け 連絡事項")
    
    board_data = robust_api_call(load_board_message, fallback_value={"message": "", "updated_at": "---"})
    current_message = board_data.get("message", "本日の連絡事項はありません。")
    updated_at = board_data.get("updated_at", "---")
    
    if updated_at and updated_at != "---":
        st.caption(f"🕒 最終更新日時: {updated_at}")
    
    st.info(current_message.replace('\n', '  \n'))
    
    if user_role in ['admin', 'owner', 'am']:
        with st.expander("✏️ 掲示板を編集"):
            new_msg = st.text_area("内容を入力", value=current_message, height=100)
            if st.button("💾 掲示板を更新"):
                with st.spinner("更新中..."):
                    success = robust_api_call(lambda: save_board_message(new_msg), fallback_value=False)
                    if success is not False:
                        load_board_message.clear()
                        st.success("更新しました！")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("通信エラーにより更新できませんでした。")