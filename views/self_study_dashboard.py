import streamlit as st
import pandas as pd
import altair as alt
import streamlit.components.v1 as components
from utils.g_sheets import load_self_study_data, load_entire_log_data, get_gc_client, SPREADSHEET_ID

@st.cache_data(ttl=600)
def get_all_student_grades():
    """生徒情報から学年データを取得する魔法"""
    try:
        gc = get_gc_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet("設定_生徒情報")
        return pd.DataFrame(ws.get_all_records())
    except:
        return pd.DataFrame()

def render_self_study_dashboard():
    # --- 🖨️ 印刷用の魔法（青いバーと無駄な余白を徹底的に排除！） ---
    st.markdown("""
        <style>
        @media print {
            /* 1. 【原因撃破】青いバー（st.infoなどのアラート箱）をブロックごと完全消去！ */
            [data-testid="stAlert"] {
                display: none !important;
            }
            
            /* 万が一カスタムHTMLで作られた背景だった場合のための保険 */
            * {
                background-color: transparent !important;
            }

            /* 2. ページ上部の大きな余白を完全にゼロにして、上に詰める！ */
            .main .block-container {
                padding-top: 0 !important;
                margin-top: 0 !important;
                gap: 0 !important; /* Streamlit特有の要素間の隙間を消す */
                max-width: 100% !important;
            }

            /* 3. Streamlitの標準ヘッダー、サイドバーを消去 */
            header, [data-testid="stHeader"], [data-testid="stSidebar"], footer {
                display: none !important;
            }

            /* 4. コントローラー類、表、不要なコンテナを「スペースごと」消去 */
            .stButton, [data-testid="stSelectbox"], [data-testid="stMultiSelect"], 
            [data-testid="stRadio"], [data-testid="stDataFrame"], [data-testid="stSpinner"], hr {
                display: none !important;
            }

            /* 5. 既存の見出し（H1〜H6）や説明文（p）を「スペースごと」完全消去 */
            h1, h2, h3, h4, h5, h6, p, [data-testid="stMarkdownContainer"] p {
                display: none !important;
                margin: 0 !important;
                padding: 0 !important;
            }

            /* 6. 特注タイトルの設定（極限まで上に配置！） */
            .print-title { 
                display: block !important; 
                text-align: center !important;
                color: black !important;
                font-size: 26px !important;
                font-weight: bold !important;
                margin-top: 0px !important; /* 上の無駄な空間をゼロに */
                margin-bottom: 10px !important; /* グラフとの隙間も詰める */
                padding: 0 !important;
            }

            /* 7. Altairグラフのコンテナ設定 */
            [data-testid="stArrowVegaLiteChart"] {
                display: block !important;
                width: 100% !important;
                margin: 0 auto !important;
                padding: 0 !important;
            }
        }
        </style>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([4, 1])
    with col1:
        st.header("📊 学習時間ダッシュボード")
    with col2:
        if st.button("🖨️ グラフを印刷"):
            components.html("<script>window.parent.print();</script>", height=0)

    st.write("自習時間と授業時間を合算したり、学年ごとに絞り込んだりできる究極のグラフです🔥")

    with st.spinner("あらゆる学習データをかき集めています..."):
        # ==========================================
        # 1. データの読み込み
        # ==========================================
        df_self_study = load_self_study_data()
        if not df_self_study.empty:
            df_self_study['日付'] = pd.to_datetime(df_self_study['日付'], errors='coerce')
            df_self_study = df_self_study.dropna(subset=['日付'])
            df_self_study['年月'] = df_self_study['日付'].dt.strftime('%Y年%m月')
            df_self_study['自習時間(分)'] = pd.to_numeric(df_self_study['自習時間(分)'], errors='coerce').fillna(0)
        
        df_classes = load_entire_log_data()
        if not df_classes.empty and '日時' in df_classes.columns:
            df_classes['日時'] = pd.to_datetime(df_classes['日時'], format='mixed', errors='coerce')
            df_classes = df_classes.dropna(subset=['日時'])
            df_classes['年月'] = df_classes['日時'].dt.strftime('%Y年%m月')

        df_grades = get_all_student_grades()

        if df_self_study.empty and df_classes.empty:
            st.info("学習記録がまだありません。")
            return

        # ==========================================
        # 2. UI（コントローラー）の作成
        # ==========================================
        st.markdown("### 🎛️ 表示設定")
        c1, c2, c3 = st.columns(3)
        
        months_ss = df_self_study['年月'].unique().tolist() if not df_self_study.empty else []
        months_cl = df_classes['年月'].unique().tolist() if not df_classes.empty else []
        month_list = sorted(list(set(months_ss + months_cl)), reverse=True)
        
        with c1:
            selected_month = st.selectbox("📅 月を選択", ["すべての期間（累計）"] + month_list)
        
        with c2:
            mode = st.radio("⏱️ 表示モード", ["自習時間のみ", "自習時間 ＋ 授業時間"])
            
        with c3:
            valid_grades = []
            if not df_grades.empty and '学年' in df_grades.columns:
                valid_grades = sorted([g for g in df_grades['学年'].unique() if str(g).strip() != ""])
            
            selected_grades = st.multiselect("🎓 学年で絞り込み (複数選択可)", options=valid_grades, default=valid_grades)

        # ==========================================
        # 3. データの絞り込みと合算
        # ==========================================
        if not df_self_study.empty:
            df_ss_filtered = df_self_study.copy()
            if selected_month != "すべての期間（累計）":
                df_ss_filtered = df_ss_filtered[df_ss_filtered['年月'] == selected_month]
            ss_grouped = df_ss_filtered.groupby('生徒名')['自習時間(分)'].sum().reset_index()
        else:
            ss_grouped = pd.DataFrame(columns=['生徒名', '自習時間(分)'])

        if mode == "自習時間 ＋ 授業時間" and not df_classes.empty:
            df_cl_filtered = df_classes.copy()
            if selected_month != "すべての期間（累計）":
                df_cl_filtered = df_cl_filtered[df_cl_filtered['年月'] == selected_month]
            
            cl_grouped = df_cl_filtered.groupby('生徒名').size().reset_index(name='コマ数')
            cl_grouped['授業時間(分)'] = cl_grouped['コマ数'] * 90
            
            merged = pd.merge(ss_grouped, cl_grouped[['生徒名', '授業時間(分)']], on='生徒名', how='outer').fillna(0)
            merged['合計時間(分)'] = merged['自習時間(分)'] + merged['授業時間(分)']
        else:
            merged = ss_grouped.copy()
            merged['授業時間(分)'] = 0
            merged['合計時間(分)'] = merged['自習時間(分)']

        if not df_grades.empty and '生徒名' in df_grades.columns and '学年' in df_grades.columns:
            merged = pd.merge(merged, df_grades[['生徒名', '学年']], on='生徒名', how='left')
            merged['学年'] = merged['学年'].fillna('不明')
        else:
            merged['学年'] = '不明'

        if selected_grades:
            merged = merged[merged['学年'].isin(selected_grades)]
        else:
            st.warning("学年が1つも選択されていません。表示したい学年を選んでください！")
            return

        # ==========================================
        # 4. グラフの描画（✨テキスト付き✨）
        # ==========================================
        if merged.empty or merged['合計時間(分)'].sum() == 0:
            st.info("指定された条件のデータがありませんでした。")
            return

        # 👑 特注タイトルの作成！ 
        grade_display = " / ".join(selected_grades) if len(selected_grades) <= 4 else "全学年"
        title_html = f"""
        <div class='print-title'>
            🏆 勉強時間ランキング ({grade_display}) - {selected_month}
        </div>
        """
        st.markdown(title_html, unsafe_allow_html=True)

        chart_height = max(300, len(merged) * 45)
        
        # グラフのY軸（生徒名の並び順）の設定
        y_encoding = alt.Y('生徒名:N', sort=alt.EncodingSortField(field="合計時間(分)", op="sum", order="descending"), title='生徒名', axis=alt.Axis(labelFontSize=14))

        if mode == "自習時間 ＋ 授業時間":
            plot_df = pd.melt(merged, id_vars=['生徒名', '合計時間(分)'], value_vars=['自習時間(分)', '授業時間(分)'], var_name='時間の種類', value_name='時間')
            
            bars = alt.Chart(plot_df).mark_bar(cornerRadiusEnd=4, height=25).encode(
                x=alt.X('時間:Q', title='学習時間 (分)'),
                y=y_encoding,
                color=alt.Color('時間の種類:N', scale=alt.Scale(domain=['自習時間(分)', '授業時間(分)'], range=['#ff7f0e', '#1f77b4']), legend=alt.Legend(title="学習の種類", orient="top")),
                tooltip=['生徒名', '時間の種類', '時間', '合計時間(分)']
            )
            
            text = alt.Chart(merged).mark_text(align='left', baseline='middle', dx=5, fontSize=14, fontWeight='bold', color='#333').encode(
                x='合計時間(分):Q',
                y=y_encoding,
                text=alt.Text('合計時間(分):Q', format='d')
            )
            
            chart = alt.layer(bars, text).properties(height=chart_height)
            
        else:
            bars = alt.Chart(merged).mark_bar(cornerRadiusEnd=4, height=25).encode(
                x=alt.X('合計時間(分):Q', title='自習時間 (分)'),
                y=y_encoding,
                color=alt.Color('合計時間(分):Q', scale=alt.Scale(scheme='blues'), legend=None),
                tooltip=['生徒名', '合計時間(分)']
            )
            
            text = alt.Chart(merged).mark_text(align='left', baseline='middle', dx=5, fontSize=14, fontWeight='bold', color='#333').encode(
                x='合計時間(分):Q',
                y=y_encoding,
                text=alt.Text('合計時間(分):Q', format='d')
            )
            
            chart = alt.layer(bars, text).properties(height=chart_height)

        st.altair_chart(chart, use_container_width=True)

        # ==========================================
        # 5. 詳細データ表の表示
        # ==========================================
        st.markdown("### 📋 詳細データ") # これも印刷時には消えます！
        display_df = merged.sort_values(by='合計時間(分)', ascending=False).reset_index(drop=True)
        display_df.index = display_df.index + 1
        
        if mode == "自習時間 ＋ 授業時間":
            cols_to_show = ['生徒名', '学年', '合計時間(分)', '自習時間(分)', '授業時間(分)']
        else:
            cols_to_show = ['生徒名', '学年', '自習時間(分)']
            
        st.dataframe(display_df[cols_to_show], use_container_width=True)