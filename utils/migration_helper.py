# utils/migration_helper.py
import pandas as pd
import streamlit as st
from supabase import create_client

SUPABASE_URL = st.secrets.get("SUPABASE_URL", "https://vxotfwlxkpouumviqxbe.supabase.co")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "sb_publishable_EoMQzOR1nA4YlxcNpg88Ug_mRBVsK4m")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def execute_migration(df: pd.DataFrame, table_name: str, column_mapping: dict):
    """スプレッドシートのデータを整形してSupabaseへ流し込む共通関数"""
    if df.empty:
        st.error("❌ 移行するデータがありませんでした。シート名等をご確認ください。")
        return

    st.write(f"📊 取得件数: {len(df)} 件")

    # 列名の変換と絞り込み
    df_mapped = df.rename(columns=column_mapping)
    valid_columns = [col for col in column_mapping.values() if col in df_mapped.columns]
    df_final = df_mapped[valid_columns].copy()

    # データクレンジング (NaN / 空文字 -> None, float -> int)
    records = df_final.to_dict(orient="records")
    clean_records = []
    for record in records:
        clean_record = {}
        for k, v in record.items():
            if pd.isna(v) or v == "" or v == "None":
                clean_record[k] = None
            else:
                if isinstance(v, float) and v.is_integer():
                    clean_record[k] = int(v)
                else:
                    clean_record[k] = v
        clean_records.append(clean_record)

    # Supabaseへバッチ挿入
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
        st.success(f"🎉 {table_name} への移行処理が完了しました！")