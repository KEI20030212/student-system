import streamlit as st
import pandas as pd
from utils.g_sheets import get_all_student_names, load_all_data

def render_analytics_dashboard_page():
    st.header("📊 講師パフォーマンス分析ダッシュボード")
    st.write("講師の「稼働状況」「指導の熱量」「宿題管理の質」を可視化します。")

    # 1. 全生徒のデータを集めて1つの大きなデータにする
    student_names = get_all_student_names()
    if not student_names:
        st.warning("生徒データが見つかりません。")
        return

    all_data_list = []
    with st.spinner('全データを解析中... 先生たちの頑張りを集計しています！'):
        for s_name in student_names:
            df = load_all_data(s_name)
            if not df.empty:
                df['生徒名'] = s_name
                all_data_list.append(df)
    
    if not all_data_list: return
    df_all = pd.concat(all_data_list, ignore_index=True)

    # 日付データの整理
    df_all['日時'] = pd.to_datetime(df_all['日時'], format='mixed', errors='coerce')
    df_all = df_all.dropna(subset=['日時'])
    df_all['年月'] = df_all['日時'].dt.strftime("%Y年%m月")

    # --- 🌟 神機能：宿題を出した「前回」の先生を特定する魔法 ---
    # ※列名は先生の実際のシートに合わせて変更してください（例：'科目', '担当講師'）
    if '科目' in df_all.columns and '担当講師' in df_all.columns:
        # 生徒ごと、科目ごと、日付順に並び替える
        df_all = df_all.sort_values(by=['生徒名', '科目', '日時'])
        # 「前回の授業」の担当講師をズラして取得（これが宿題を出した先生！）
        df_all['宿題を出した先生'] = df_all.groupby(['生徒名', '科目'])['担当講師'].shift(1)

    # --- 🌟 神機能：指導報告書の「熱量（文字数）」を計算 ---
    # ※列名は実際のシートに合わせてください（例：'指導内容', 'コメント' など）
    report_col = '指導内容' if '指導内容' in df_all.columns else None
    if report_col:
        df_all['報告文字数'] = df_all[report_col].astype(str).apply(lambda x: len(x) if x != 'nan' else 0)

    # 月の選択
    st.divider()
    month_options = sorted(df_all['年月'].unique().tolist(), reverse=True)
    selected_month = st.selectbox("📅 分析する月を選択", month_options)
    df_month = df_all[df_all['年月'] == selected_month]

    if df_month.empty:
        st.warning("この月のデータはありません。")
        return

    # 分析対象の先生リスト
    teachers = [t for t in df_month['担当講師'].dropna().unique() if t not in ["未入力", ""]]
    selected_teacher = st.selectbox("👨‍🏫 分析する講師を選択", ["全員まとめて比較"] + teachers)

    st.divider()

    # ==========================================
    # 📊 ここからダッシュボードの描画！
    # ==========================================

    if selected_teacher == "全員まとめて比較":
        st.subheader(f"🏆 {selected_month} の全体ランキング")
        
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("**📈 コマ数ランキング**")
            # コマ数集計
            koma_counts = df_month['担当講師'].value_counts().reset_index()
            koma_counts.columns = ['講師名', 'コマ数']
            koma_counts = koma_counts[koma_counts['講師名'].isin(teachers)]
            st.bar_chart(koma_counts.set_index('講師名'))

        with c2:
            if report_col:
                st.markdown(f"**🔥 指導報告の熱量（平均文字数）ランキング**")
                # 文字数集計
                avg_chars = df_month.groupby('担当講師')['報告文字数'].mean().reset_index()
                avg_chars = avg_chars[avg_chars['担当講師'].isin(teachers)]
                st.bar_chart(avg_chars.set_index('担当講師'))

    else:
        st.subheader(f"👩‍🏫 {selected_teacher} 先生の分析レポート ({selected_month})")
        df_t = df_month[df_month['担当講師'] == selected_teacher]

        # 指導科目のバランス（円グラフ）
        if '科目' in df_t.columns:
            st.markdown("**🍕 指導科目のバランス**")
            subject_counts = df_t['科目'].value_counts()
            st.bar_chart(subject_counts) # Streamlit標準だと円グラフが少し複雑なので、まずは美しい横棒グラフで！

        st.divider()

        # 宿題の履行率（前回の先生としての評価！）
        st.markdown("**📝 宿題管理の質（出した宿題がどれだけやられているか）**")
        # df_allの中から、「前回の先生」がこの先生だった時の、「今回の宿題の出来」を集計する
        if '宿題を出した先生' in df_all.columns:
            # 自分が宿題を出した授業（今月チェックされたもの）
            df_hw = df_month[df_month['宿題を出した先生'] == selected_teacher]
            
            # ※「宿題の出来」の列名は実際のシートに合わせてください
            hw_col = '宿題' if '宿題' in df_month.columns else None
            
            if hw_col and not df_hw.empty:
                hw_counts = df_hw[hw_col].value_counts()
                st.write(f"あなたが前回の授業で出した宿題の、今月の完了状況です（サンプル数: {len(df_hw)}件）")
                st.bar_chart(hw_counts)
            else:
                st.info("今月、あなたが宿題を出した（前回担当した）授業のデータがまだありません。")

        # 定期テストの成績アップ（追加案B）は、少し複雑なのでフェーズ2の後半で実装します！
        st.caption("※定期テストの成績アップ貢献度は、次のステップで『成績_定期テスト』シートと連動させます！")