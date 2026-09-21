import streamlit as st
from utils.g_sheets import get_all_logs
from utils.migration_helper import execute_migration

st.title("📦 授業記録 ➔ Supabase 移行")

if st.button("🚀 授業記録の移行を開始", type="primary"):
    st.info("📥 データを取得中...")
    df = get_all_logs()
    mapping = {
        "日時": "date", "生徒ID": "student_id", "名前": "student_name",
        "科目": "subject", "テキスト": "textbook_used", "終了ページ": "progress_pages",
        "担当講師": "teacher_name", "授業形態": "class_type", "出欠": "attendance",
        "授業コマ": "class_slot", "アドバイス": "advice", "保護者への連絡": "parent_message",
        "次回への引継ぎ": "handover", "出した宿題P": "homework_page",
        "やった宿題P": "homework_finish_page", "やる気ランク": "attitude_rank",
        "未達成の理由": "reason_unachieved", "本日の修正策": "fix_action",
        "次回の宿題テキスト": "next_homework_textbook", "次回の宿題ページ数": "next_homework_pages",
        "遅刻時間": "late_time", "集中力": "concentration",
        "ミスへの反応": "reaction_to_error", "次回の持ち物": "next_belongings",
        "AIフィードバック": "AI_feedback", "AIスコア": "AI_score",
    }
    execute_migration(df, "lesson_logs", mapping)