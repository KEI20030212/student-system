# migrate_data.py
import pandas as pd
from supabase import create_client
import streamlit as st
from utils.g_sheets import get_all_logs

SUPABASE_URL = "https://vxotfwlxkpouumviqxbe.supabase.co"  # ご自身のURL
SUPABASE_KEY = "sb_publishable_EoMQzOR1nA4YlxcNpg88Ug_mRBVsK4m"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.title("📦 スプレッドシート ➔ Supabase データ移行ツール")

if st.button("🚀 データ移行を開始する", type="primary"):
    st.info("📥 スプレッドシートからデータを取得中...")
    df = get_all_logs()

    if df.empty:
        st.error("❌ 移行するデータがありませんでした。")
    else:
        st.write(f"📊 取得件数: {len(df)} 件")

        # スプレッドシートの日本語列名をSupabaseのカラム名（英語）に変換
        column_mapping = {
            "日時": "date",
            "生徒ID": "student_id",
            "名前": "student_name",
            "科目": "subject",
            "テキスト": "textbook_used",
            "終了ページ": "progress_pages",
            "担当講師": "teacher_name",
            "授業形態": "class_type",
            "出欠": "attendance",
            "授業コマ": "class_slot",
            "アドバイス": "advice",
            "保護者への連絡": "parent_message",
            "次回への引継ぎ": "handover",
            "出した宿題P": "homework_page",
            "やった宿題P": "homework_finish_page",
            "やる気ランク": "attitude_rank",
            "未達成の理由": "reason_unachieved",
            "本日の修正策": "fix_action",
            "次回の宿題テキスト": "next_homework_textbook",
            "次回の宿題ページ数": "next_homework_pages",
            "遅刻時間": "late_time",  # Supabase側が late_minutes の場合は変更してください
            "集中力": "concentration",
            "ミスへの反応": "reaction_to_error",
            "次回の持ち物": "next_belongings",
            "AIフィードバック": "AI_feedback",
            "AIスコア": "AI_score",
        }

        # 存在する列だけ変換
        df_mapped = df.rename(columns=column_mapping)

        # Supabase側で定義したカラムだけに絞り込み
        valid_columns = [
            col for col in column_mapping.values() if col in df_mapped.columns
        ]
        df_final = df_mapped[valid_columns]

        # Pandasの NaN（空データ）を None (NULL) に置き換え
        df_final = df_final.where(pd.notnull(df_final), None)

        # dictのリストに変換
        records = df_final.to_dict(orient="records")

        # データ件数が多い場合を考慮し、100件ずつ分割して流し込み
        batch_size = 100
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            try:
                supabase.table("lesson_logs").insert(batch).execute()
                current_count = min(i + batch_size, len(records))
                status_text.text(
                    f"✅ {current_count} / {len(records)} 件を移行完了"
                )
                progress_bar.progress(current_count / len(records))
            except Exception as e:
                st.error(f"❌ エラー発生 ({i + 1}件目付近): {e}")
                break

        st.success("🎉 移行処理が完了しました！")