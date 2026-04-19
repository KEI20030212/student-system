import streamlit as st
import pandas as pd
import time
import re
from utils.g_sheets import (
    get_all_student_names, 
    load_all_data, 
    load_billing_data, 
    save_billing_data,
    get_student_master_data, # 名前を変更
    load_price_master
)

def render_tuition_dashboard_page():
    st.header("💴 月謝（請求額）管理ダッシュボード")
    
    # --- データ準備 ---
    student_names = get_all_student_names()
    student_master = get_student_master_data() # 名簿マスター（学年・コース）を取得
    price_master = load_price_master()
    
    if not student_names: 
        st.warning("生徒データが見つかりません。")
        return

    # プログレスバー
    all_data_list = []
    total_students = len(student_names)
    st.caption("🔄 最新の授業データを取得中...")
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, s_name in enumerate(student_names):
        status_text.text(f"集計中 ({i+1}/{total_students}) : {s_name}")
        try:
            df = load_all_data(s_name)
            if not df.empty:
                df['生徒名'] = s_name
                all_data_list.append(df)
        except:
            pass
        progress_bar.progress((i + 1) / total_students)
        time.sleep(0.3) # API負荷軽減

    progress_bar.empty()
    status_text.empty()
    
    if not all_data_list: 
        st.info("集計できる授業記録がありません。")
        return
        
    df_all = pd.concat(all_data_list, ignore_index=True)
    df_all['日時'] = pd.to_datetime(df_all['日時'], format='mixed', errors='coerce')
    df_all = df_all.dropna(subset=['日時'])
    df_all['年月'] = df_all['日時'].dt.strftime("%Y年%m月")

    month_options = sorted(df_all['年月'].unique().tolist(), reverse=True)
    selected_month = st.selectbox("📅 請求月を選択", month_options)
    df_month = df_all[df_all['年月'] == selected_month]

    st.divider()
    st.subheader(f"👤 {selected_month} の請求設定")

    # 実受講数のカウント
    active_students = df_month['生徒名'].dropna().unique()
    actual_koma_dict = {s: len(df_month[df_month['生徒名'] == s]) for s in active_students}
    
    # 既存の保存済みデータ
    saved_billing_df = load_billing_data(selected_month)

    table_data = []
    for student in active_students:
        actual_koma = actual_koma_dict[student]
        
        # 名簿（マスター）から情報を取得
        m_info = student_master.get(student, {"学年": "未設定", "契約コース": "未設定"})
        grade = m_info["学年"]
        master_course = m_info["契約コース"]
        
        # --- 表示データの決定 ---
        # 1. 保存済みデータがある場合（編集・確定済み）はそれを優先
        if not saved_billing_df.empty and student in saved_billing_df['👤 生徒名'].values:
            row = saved_billing_df[saved_billing_df['👤 生徒名'] == student].iloc[0]
            # コース列を探す
            course = next((row[c] for c in saved_billing_df.columns if "契約コース" in c), master_course)
            # 金額列を探す
            price = next((row[c] for c in saved_billing_df.columns if "請求額" in c), 0)
        
        # 2. 保存データがない場合は名簿からデフォルト作成
        else:
            course = master_course
            # 「月8回」などの文字列から数字の「8」を取り出す
            try:
                koma_num = int(re.sub(r'\D', '', str(course)))
            except:
                koma_num = actual_koma # 数字が取れなければ実受講数
            
            # 料金マスタから検索
            match = price_master[(price_master['学年'] == grade) & (price_master['コマ数'] == koma_num)]
            if not match.empty:
                price = int(match.iloc[0]['料金'])
            else:
                price = 15000 # デフォルト
        
        table_data.append({
            "👤 生徒名": student,
            "🎓 学年": grade,
            "📚 契約コース": course,
            "💴 今月の請求額 (円)": int(price),
            "📝 実際の受講数": actual_koma
        })
    
    display_df = pd.DataFrame(table_data)

    with st.form("billing_form"):
        edited_df = st.data_editor(
            display_df,
            hide_index=True,
            use_container_width=True,
            disabled=["👤 生徒名", "🎓 学年", "📝 実際の受講数"]
        )
        submitted = st.form_submit_button("💾 確定して保存", use_container_width=True)
                
        if submitted:
            with st.spinner("スプレッドシートに保存中..."):
                save_df = edited_df.drop(columns=["📝 実際の受講数"])
                if save_billing_data(selected_month, save_df):
                    st.success(f"✅ {selected_month} のデータを保存しました！")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ 保存に失敗しました。")

    st.divider()
    total = edited_df["💴 今月の請求額 (円)"].sum()
    st.metric(label=f"🌟 {selected_month} の合計請求額", value=f"{total:,} 円")