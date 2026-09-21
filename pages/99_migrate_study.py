import streamlit as st
from utils.g_sheets import load_self_study_data
from utils.migration_helper import execute_migration

st.title("📦 自習記録 ➔ Supabase 移行")

if st.button("🚀 自習記録の移行を開始", type="primary"):
    st.info("📥 データを取得中...")
    df = load_self_study_data()
    mapping = {
        "日付": "date", "日時": "date", "生徒ID": "student_id",
        "名前": "student_name", "教科": "subject", "自習時間(分)": "study_minutes",
        "自習時間": "study_minutes", "開始時間": "start_time", "終了時間": "end_time",
        "休憩時間": "break_minutes", "休憩時間(分)": "break_minutes",
        "内容": "content", "獲得ポイント": "points",
    }
    execute_migration(df, "self_study_logs", mapping)