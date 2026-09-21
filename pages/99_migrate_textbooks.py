import streamlit as st
from utils.g_sheets import get_textbook_master
from utils.migration_helper import execute_migration

st.title("📦 テキスト情報 ➔ Supabase 移行")

if st.button("🚀 テキスト情報の移行を開始", type="primary"):
    st.info("📥 データを取得中...")
    df = get_textbook_master()
    mapping = {
        "テキスト": "textbook_name",
        "章": "chapter", "単元名": "unit_name",
        "開始ページ": "start_page", "終了ページ": "end_page",
    }
    execute_migration(df, "textbook_contents", mapping)