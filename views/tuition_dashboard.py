def render_tuition_dashboard_page():
    st.header("💴 月謝（請求額）管理ダッシュボード")
    student_names = get_all_student_names()
    if not student_names: return

    all_data_list = []
    with st.spinner('集計中...'):
        for s_name in student_names:
            df = load_all_data(s_name)
            if not df.empty:
                df['生徒名'] = s_name
                all_data_list.append(df)
    
    if not all_data_list: return
    df_all = pd.concat(all_data_list, ignore_index=True)
    if '授業形態' not in df_all.columns: return

    df_all['日時'] = pd.to_datetime(df_all['日時'], format='mixed', errors='coerce')
    df_all = df_all.dropna(subset=['日時'])
    df_all['年月'] = df_all['日時'].dt.strftime("%Y年%m月")

    month_options = sorted(df_all['年月'].unique().tolist(), reverse=True)
    selected_month = st.selectbox("📅 請求月を選択", month_options)
    df_month = df_all[df_all['年月'] == selected_month]

    st.divider()
    st.subheader("👤 生徒ごとの「契約月謝」設定・確認")
    active_students = df_month['生徒名'].dropna().unique()

    actual_koma_dict = {}
    for student in active_students:
        actual_koma_dict[student] = len(df_month[df_month['生徒名'] == student])

    student_prices_df = pd.DataFrame({
        "👤 生徒名": active_students,
        "📚 契約コース (例: 月4回)": ["月4回"] * len(active_students),
        "💴 今月の請求額 (円)": [15000] * len(active_students),
        "📝 (参考) 実際の受講数": [actual_koma_dict[s] for s in active_students]
    })

    edited_prices = st.data_editor(student_prices_df, hide_index=True, use_container_width=True, disabled=["👤 生徒名", "📝 (参考) 実際の受講数"])

    st.divider()
    total_revenue = edited_prices["💴 今月の請求額 (円)"].sum()
    st.metric(label=f"🌟 {selected_month} の売上（請求）合計", value=f"{total_revenue:,} 円")
