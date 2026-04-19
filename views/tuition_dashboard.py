import streamlit as st
import pandas as pd
import time
from utils.g_sheets import (
    get_all_student_names, 
    load_all_data, 
    load_billing_data, 
    save_billing_data,
    get_student_grades,
    load_price_master
)

def render_tuition_dashboard_page():
    st.header("💴 月謝（請求額）管理ダッシュボード")
    
    # --- データ準備 ---
    student_names = get_all_student_names()
    student_grades = get_student_grades() # 学年データを取得
    price_master = load_price_master()
    
    if not student_names: 
        st.warning("生徒データが見つかりません。")
        return

    # 🌟 プログレスバーとAPIエラー対策の実装 🌟
    all_data_list = []
    total_students = len(student_names)
    
    st.caption("🔄 最新の授業データをスプレッドシートから取得しています...")
    # プログレスバーとテキスト表示用の空枠を作る
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, s_name in enumerate(student_names):
        # 現在誰のデータを取っているか表示
        status_text.text(f"集計中 ({i+1}/{total_students}) : {s_name}")
        
        try:
            df = load_all_data(s_name)
            if not df.empty:
                df['生徒名'] = s_name
                all_data_list.append(df)
        except Exception as e:
            st.warning(f"⚠️ {s_name} のデータ取得中にエラーが発生しました。")
        
        # プログレスバーを少しずつ進める
        progress_bar.progress((i + 1) / total_students)
        
        # 🛡️【超重要】API制限（429エラー）を回避するため、0.5秒お休みする
        time.sleep(0.5) 

    # 読み込みが終わったらプログレスバーとテキストを消す
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

    # --- 実際の受講コマ数の計算 ---
    active_students = df_month['生徒名'].dropna().unique()
    actual_koma_dict = {s: len(df_month[df_month['生徒名'] == s]) for s in active_students}
    saved_billing_df = load_billing_data(selected_month)

    table_data = []
    for student in active_students:
        actual_koma = actual_koma_dict[student]
        grade = student_grades.get(student, "未設定")
        
        # 1. 保存済みデータがあるか確認
        if not saved_billing_df.empty and student in saved_billing_df['👤 生徒名'].values:
            row = saved_billing_df[saved_billing_df['👤 生徒名'] == student].iloc[0]
            course = row.get("📚 契約コース", f"月{actual_koma}回")
            price = row.get("💴 今月の請求額 (円)", 0)
        else:
            # 2. 保存データがない場合、料金マスタから自動計算
            # 学年とコマ数が一致する行を探す
            match = price_master[(price_master['学年'] == grade) & (price_master['コマ数'] == actual_koma)]
            if not match.empty:
                price = int(match.iloc[0]['料金'])
            else:
                price = 15000  # マスタにない場合のデフォルト値
            course = f"月{actual_koma}回"

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
                # 🐛 修正箇所：「📝 実際の受講数」の列名指定を直しました
                save_df = edited_df.drop(columns=["📝 実際の受講数"])
                if save_billing_data(selected_month, save_df):
                    st.success(f"✅ {selected_month} のデータを保存しました！")
                    time.sleep(1)
                    st.rerun() # 画面をリロードして反映を確認
                else:
                    st.error("❌ 保存に失敗しました。")

    # --- 合計の表示 ---
    st.divider()
    total = edited_df["💴 今月の請求額 (円)"].sum()
    st.metric(label=f"🌟 {selected_month} の合計請求額", value=f"{total:,} 円")