# utils/migration_helper.py
import pandas as pd
import streamlit as st
from supabase import create_client

SUPABASE_URL = st.secrets.get("SUPABASE_URL", "https://vxotfwlxkpouumviqxbe.supabase.co")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "sb_publishable_EoMQzOR1nA4YlxcNpg88Ug_mRBVsK4m")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ★ 1行目の引数末尾に clear_existing: bool = True を追加
def execute_migration(df: pd.DataFrame, table_name: str, column_mapping: dict, clear_existing: bool = True):
    """スプレッドシートのデータを整形してSupabaseへ流し込む共通関数"""
    
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        st.error("❌ 移行するデータが取得できませんでした。シート名（タブ名）や g_sheets.py の設定をご確認ください。")
        return

    st.write(f"📊 取得件数: {len(df)} 件")

    # 1. 移行前にSupabase側の既存データを全削除して上書き準備
    if clear_existing:
        try:
            # id が -1 以外の全レコードを削除（実質全削除）
            supabase.table(table_name).delete().neq("id", -1).execute()
            st.info("🗑️ 既存のデータをクリアしました（上書きモード）")
        except Exception as e:
            st.warning(f"⚠️ 既存データのクリア時に通知がありました（データが空の可能性など）: {e}")

    # 2. 列名の変換と絞り込み
    df_mapped = df.rename(columns=column_mapping)
    valid_columns = [col for col in column_mapping.values() if col in df_mapped.columns]
    df_final = df_mapped[valid_columns].copy()

    # 数値（整数）として扱うべきカラム一覧
    integer_columns = {
        "start_page", "end_page", "progress_pages", "homework_page", 
        "homework_finish_page", "next_homework_pages", "late_time", 
        "study_minutes", "break_minutes", "points", "student_id"
    }

    # 無視・NULL（None）変換対象の記号・文字列一覧
    null_values = {"", "-", "‐", "―", "ー", "None", "none", "null", "NULL", "N/A", "NA", "なし"}

    records = df_final.to_dict(orient="records")
    clean_records = []

    for record in records:
        clean_record = {}
        for k, v in record.items():
            # NaN やハイフンなどの無効記号・文字列は None (NULL) に変換
            if pd.isna(v) or str(v).strip() in null_values:
                clean_record[k] = None
            else:
                val_str = str(v).strip()
                
                # 数値型カラムの場合は安全に int 変換（失敗時は None）
                if k in integer_columns:
                    try:
                        clean_record[k] = int(float(val_str))
                    except (ValueError, TypeError):
                        clean_record[k] = None
                else:
                    if isinstance(v, float) and v.is_integer():
                        clean_record[k] = int(v)
                    else:
                        clean_record[k] = val_str

        clean_records.append(clean_record)

    # 3. Supabaseへバッチ挿入
    batch_size = 100
    progress_bar = st.progress(0)
    status_text = st.empty()
    has_error = False

    for i in range(0, len(clean_records), batch_size):
        batch = clean_records[i : i + batch_size]
        try:
            supabase.table(table_name).insert(batch).execute()
            current_count = min(i + batch_size, len(clean_records))
            status_text.text(f"✅ {current_count} / {len(clean_records)} 件を移行完了")
            progress_bar.progress(current_count / len(clean_records))
        except Exception as batch_error:
            st.error(f"❌ エラー発生 ({i + 1}件目付近): {batch_error}")
            has_error = True
            break

    if not has_error:
        st.success(f"🎉 {table_name} への移行（上書き更新）が完了しました！")