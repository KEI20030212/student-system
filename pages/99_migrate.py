# pages/99_migrate.py
import pandas as pd
from supabase import create_client
import streamlit as st
from utils.g_sheets import get_all_logs  # 必要に応じて自習用関数もインポート

SUPABASE_URL = st.secrets.get("SUPABASE_URL", "https://vxotfwlxkpouumviqxbe.supabase.co")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "sb_publishable_EoMQzOR1nA4YlxcNpg88Ug_mRBVsK4m")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.title("📦 スプレッドシート ➔ Supabase データ移行ツール")

# 1. 移行対象データの選択機能
target_data = st.radio(
    "移行するデータを選択してください",
    ["授業記録 (lesson_logs)", "自習記録 (study_logs)"],
    horizontal=True
)

if st.button("🚀 データ移行を開始する", type="primary"):
    try:
        # 2. 選択されたデータに応じた処理の分岐
        if target_data == "授業記録 (lesson_logs)":
            st.info("📥 授業記録データを取得中...")
            df = get_all_logs()
            table_name = "lesson_logs"
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
                "遅刻時間": "late_time",
                "集中力": "concentration",
                "ミスへの反応": "reaction_to_error",
                "次回の持ち物": "next_belongings",
                "AIフィードバック": "AI_feedback",
                "AIスコア": "AI_score",
            }
        else:
            st.info("📥 自習記録データを取得中...")
            # 自習記録用シートを取得する関数を呼び出します
            # （g_sheets.py側で自習シート取得用関数名が異なる場合は置き換えてください）
            df = load_self_study_data()  
            table_name = "study_logs"
            column_mapping = {
                "日付": "date",
                "日時": "date",
                "生徒ID": "student_id",
                "名前": "student_name",
                "教科": "subject",
                "自習時間(分)": "study_minutes",
                "自習時間": "study_minutes",
                "開始時間": "start_time",
                "終了時間": "end_time",
                "休憩時間": "break_minutes",
                "休憩時間(分)": "break_minutes",
                "内容": "content",
                "獲得ポイント": "points",
            }

        if df.empty:
            st.error("❌ 移行するデータがありませんでした。")
        else:
            st.write(f"📊 取得件数: {len(df)} 件")

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

            batch_size = 100
            progress_bar = st.progress(0)
            status_text = st.empty()
            has_error = False

            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]
                try:
                    supabase.table(table_name).insert(batch).execute()
                    current_count = min(i + batch_size, len(records))
                    status_text.text(
                        f"✅ {current_count} / {len(records)} 件を移行完了"
                    )
                    progress_bar.progress(current_count / len(records))
                except Exception as batch_error:
                    st.error(f"❌ エラー発生 ({i + 1}件目付近): {batch_error}")
                    has_error = True
                    break

            if not has_error:
                st.success(f"🎉 {target_data} の移行処理が完了しました！")

    except Exception as e:
        st.error(f"❌ 移行エラーが発生しました: {e}")