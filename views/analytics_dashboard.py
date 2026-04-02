import streamlit as st
import pandas as pd
from utils.g_sheets import get_all_student_names, load_all_data

def render_analytics_dashboard_page():
    st.header("📊 講師パフォーマンス分析ダッシュボード")
    st.write("講師の「稼働状況」「指導の熱量」「宿題管理の質」を可視化します。")

    # --- 🌟 月の選択肢を「一番最初」に作っておく ---
    today = pd.Timestamp.now()
    default_months = [(today - pd.DateOffset(months=i)).strftime("%Y年%m月") for i in range(12)]
    data_months = []
    df_all = pd.DataFrame() # 空箱を用意

    # 1. 全生徒のデータを集める
    student_names = get_all_student_names()
    
    if not student_names:
        # ⚠️ ここで return せず、優しくお知らせするだけに留める！
        st.info("💡 まだ生徒データが登録されていません。（下の月の選択などは可能です！）")
    else:
        all_data_list = []
        with st.spinner('全データを解析中... 先生たちの頑張りを集計しています！'):
            for s_name in student_names:
                df = load_all_data(s_name)
                if not df.empty:
                    df['生徒名'] = s_name
                    all_data_list.append(df)
        
        # データがある場合のみ集計処理
        if all_data_list:
            df_all = pd.concat(all_data_list, ignore_index=True)
            df_all['日時'] = pd.to_datetime(df_all['日時'], format='mixed', errors='coerce')
            df_all = df_all.dropna(subset=['日時'])
            df_all['年月'] = df_all['日時'].dt.strftime("%Y年%m月")
            data_months = df_all['年月'].dropna().unique().tolist()
            
            # 宿題を出した「前回」の先生を特定
            if '科目' in df_all.columns and '担当講師' in df_all.columns:
                df_all = df_all.sort_values(by=['生徒名', '科目', '日時'])
                df_all['宿題を出した先生'] = df_all.groupby(['生徒名', '科目'])['担当講師'].shift(1)

            # 指導報告書の「熱量（文字数）」を計算
            report_col = '指導内容' if '指導内容' in df_all.columns else None
            if report_col:
                df_all['報告文字数'] = df_all[report_col].astype(str).apply(lambda x: len(x) if x != 'nan' else 0)

    # --- 🌟 ここから下の「月の選択肢」が絶対に表示されるようになります！ ---
    month_options = sorted(list(set(default_months + data_months)), reverse=True)

    st.divider()
    selected_month = st.selectbox("📅 分析する月を選択", month_options)

    # 選んだ月のデータがない場合はここでストップ
    if df_all.empty or selected_month not in df_all['年月'].values:
        st.info(f"💡 {selected_month} の授業データはまだありません。記録が追加されるとここにグラフが表示されます！")
        return

    df_month = df_all[df_all['年月'] == selected_month]

    # 分析対象の先生リスト
    teachers = [t for t in df_month['担当講師'].dropna().unique() if t not in ["未入力", ""]]
    if not teachers:
        st.info(f"{selected_month} に授業を行った講師のデータがありません。")
        return
        
    selected_teacher = st.selectbox("👨‍🏫 分析する講師を選択", ["全員まとめて比較"] + teachers)

    st.divider()

    # ==========================================
    # 📊 ここからダッシュボードの描画
    # ==========================================
    if selected_teacher == "全員まとめて比較":
        st.subheader(f"🏆 {selected_month} の全体ランキング")
        
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("**📈 コマ数ランキング**")
            koma_counts = df_month['担当講師'].value_counts().reset_index()
            koma_counts.columns = ['講師名', 'コマ数']
            koma_counts = koma_counts[koma_counts['講師名'].isin(teachers)]
            st.bar_chart(koma_counts.set_index('講師名'))

        with c2:
            report_col = '指導内容' if '指導内容' in df_month.columns else None
            if report_col and '報告文字数' in df_month.columns:
                st.markdown(f"**🔥 指導報告の熱量（平均文字数）ランキング**")
                avg_chars = df_month.groupby('担当講師')['報告文字数'].mean().reset_index()
                avg_chars = avg_chars[avg_chars['担当講師'].isin(teachers)]
                st.bar_chart(avg_chars.set_index('担当講師'))

    else:
        st.subheader(f"👩‍🏫 {selected_teacher} 先生の分析レポート ({selected_month})")
        df_t = df_month[df_month['担当講師'] == selected_teacher]

        if '科目' in df_t.columns:
            st.markdown("**🍕 指導科目のバランス**")
            subject_counts = df_t['科目'].value_counts()
            st.bar_chart(subject_counts)

        st.divider()

        st.markdown("**📝 宿題管理の質（出した宿題がどれだけやられているか）**")
        if '宿題を出した先生' in df_all.columns:
            df_hw = df_month[df_month['宿題を出した先生'] == selected_teacher]
            hw_col = '宿題' if '宿題' in df_month.columns else None
            
            if hw_col and not df_hw.empty:
                hw_counts = df_hw[hw_col].value_counts()
                st.write(f"あなたが前回の授業で出した宿題の、今月の完了状況です（サンプル数: {len(df_hw)}件）")
                st.bar_chart(hw_counts)
            else:
                st.info("今月、あなたが宿題を出した（前回担当した）授業のデータがまだありません。")

        st.caption("※定期テストの成績アップ貢献度は、次のステップで『成績_定期テスト』シートと連動させます！")