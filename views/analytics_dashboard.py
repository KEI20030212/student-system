import streamlit as st
import pandas as pd
from utils.g_sheets import get_all_student_names, load_all_data

def render_analytics_dashboard_page():
    st.header("📊 講師パフォーマンス分析ダッシュボード")
    st.write("講師の「稼働状況」「指導の熱量」「宿題管理の質」を可視化します。")

    # --- 列名の設定（ここを実際のシートに合わせます） ---
    report_col = 'アドバイス'  # 指導報告の列名
    hw_content_col = '次回の宿題ページ'  # 宿題を出した内容の列名
    hw_status_col = '宿題'  # 🌟重要：宿題の「結果(A,B,Cなど)」を入れている列名

    # 月の選択肢準備
    today = pd.Timestamp.now()
    default_months = [(today - pd.DateOffset(months=i)).strftime("%Y年%m月") for i in range(12)]
    df_all = pd.DataFrame()

    # 1. データ読み込み
    student_names = get_all_student_names()
    if not student_names:
        st.info("💡 生徒データが登録されていません。")
    else:
        all_data_list = []
        with st.spinner('全データを解析中...'):
            for s_name in student_names:
                df = load_all_data(s_name)
                if not df.empty:
                    df['生徒名'] = s_name
                    all_data_list.append(df)
        
        if all_data_list:
            df_all = pd.concat(all_data_list, ignore_index=True)
            df_all['日時'] = pd.to_datetime(df_all['日時'], format='mixed', errors='coerce')
            df_all = df_all.dropna(subset=['日時'])
            df_all['年月'] = df_all['日時'].dt.strftime("%Y年%m月")

            # --- 🌟 指導報告の「熱量（文字数）」を計算 ---
            if report_col in df_all.columns:
                # どんなデータが来ても安全に文字数を数える無敵の関数
                def count_chars(text):
                    if pd.isna(text): return 0
                    text_str = str(text).strip()
                    if text_str.lower() in ['nan', 'none', '<na>', '']: return 0
                    return len(text_str)
                
                df_all['報告文字数'] = df_all[report_col].apply(count_chars)
            # --- 🌟 宿題履行率の追跡ロジック ---
            if '科目' in df_all.columns and '担当講師' in df_all.columns:
                df_all = df_all.sort_values(by=['生徒名', '科目', '日時'])
                # 「前回」の担当講師と「前回」出された宿題内容を、現在の行に持ってくる
                df_all['宿題を出した先生'] = df_all.groupby(['生徒名', '科目'])['担当講師'].shift(1)
                df_all['前回出された宿題内容'] = df_all.groupby(['生徒名', '科目'])[hw_content_col].shift(1)

    # 画面表示
    month_options = sorted(list(set(default_months + (df_all['年月'].unique().tolist() if not df_all.empty else []))), reverse=True)
    st.divider()
    selected_month = st.selectbox("📅 分析する月を選択", month_options)

    if df_all.empty or selected_month not in df_all['年月'].values:
        st.info(f"💡 {selected_month} の授業データはまだありません。")
        return

    df_month = df_all[df_all['年月'] == selected_month]
    teachers = [t for t in df_month['担当講師'].dropna().unique() if t not in ["未入力", ""]]
    
    selected_teacher = st.selectbox("👨‍🏫 分析する講師を選択", ["全員まとめて比較"] + teachers)
    st.divider()

    if selected_teacher == "全員まとめて比較":
        st.subheader(f"🏆 {selected_month} の全体ランキング")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**📈 コマ数（授業回数）**")
            koma = df_month['担当講師'].value_counts().reset_index()
            koma.columns = ['講師名', 'コマ数']
            st.bar_chart(koma.set_index('講師名'))
        with c2:
            if '報告文字数' in df_month.columns:
                st.markdown("**🔥 指導報告（アドバイス）の平均文字数**")
                avg_chars = df_month.groupby('担当講師')['報告文字数'].mean().reset_index()
                st.bar_chart(avg_chars.set_index('担当講師'))
    else:
        # 個別分析
        st.subheader(f"👩‍🏫 {selected_teacher} 先生の分析レポート")
        df_t = df_month[df_month['担当講師'] == selected_teacher]

        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("今月の担当コマ数", f"{len(df_t)} コマ")
        with col_b:
            if '報告文字数' in df_t.columns:
                st.metric("アドバイス平均文字数", f"{int(df_t['報告文字数'].mean())} 文字")

        st.divider()
        
        # 宿題履行率グラフ
        st.markdown(f"**📝 {selected_teacher} 先生が出した宿題の達成状況**")
        st.caption("※前回この先生が宿題を出し、今回チェックされた結果を集計しています。")
        
        # 「宿題を出した先生」が選択中の先生で、かつ「前回宿題が空欄でない」データを抽出
        df_hw_eval = df_month[
            (df_month['宿題を出した先生'] == selected_teacher) & 
            (df_month['前回出された宿題内容'].notna()) & 
            (df_month['前回出された宿題内容'] != "")
        ]

        if hw_status_col in df_hw_eval.columns and not df_hw_eval.empty:
            hw_results = df_hw_eval[hw_status_col].value_counts()
            st.bar_chart(hw_results)
        else:
            st.info("宿題の達成状況データがまだありません。（「宿題」列に評価が入ると表示されます）")