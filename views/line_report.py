import streamlit as st
import datetime
import pandas as pd

# 既存のutilsから必要な関数をインポート（環境に合わせて調整してください）
from utils.g_sheets import (
    get_all_student_names,
    load_self_study_data,
    load_quiz_data_from_dedicated_sheet,
    get_textbook_master
)

def render_line_report_page():
    st.header("📱 LINE用 学習レポート生成")
    st.write("各ダッシュボードのデータを集約して、保護者へ送るLINEメッセージを自動作成します✨")

    # 1. 生徒の選択
    student_names = get_all_student_names()
    selected_student = st.selectbox("👤 レポートを作成する生徒を選択", ["-- 選択 --"] + student_names)

    if selected_student == "-- 選択 --":
        st.stop()

    st.divider()

    with st.spinner("データを集約中..."):
        # ==========================================
        # 📊 データの取得ロジック
        # ==========================================
        
        # ① 小テストデータの取得（quiz_dashboardのロジックを応用）
        df_quiz = load_quiz_data_from_dedicated_sheet(selected_student)
        latest_quiz_text = "最近の小テスト記録はありません。"
        if not df_quiz.empty:
            df_quiz['日時'] = pd.to_datetime(df_quiz['日時'], format='mixed', errors='coerce')
            latest_quiz = df_quiz.loc[df_quiz['日時'].idxmax()]
            latest_quiz_text = f"【{latest_quiz['テキスト']} {latest_quiz['単元']}】: {latest_quiz['点数']}点 💮"

        # ② 学習時間の取得（self_study_dashboardのロジックを応用）
        df_self_study = load_self_study_data()
        study_time_text = "今月の自習記録はまだありません。"
        if not df_self_study.empty:
            df_self_study['日付'] = pd.to_datetime(df_self_study['日付'], errors='coerce')
            current_month = datetime.date.today().strftime('%Y年%m月')
            df_ss_filtered = df_self_study[(df_self_study['生徒名'] == selected_student) & 
                                           (df_self_study['日付'].dt.strftime('%Y年%m月') == current_month)]
            
            if not df_ss_filtered.empty:
                df_ss_filtered['自習時間(分)'] = pd.to_numeric(df_ss_filtered['自習時間(分)'], errors='coerce').fillna(0)
                total_minutes = df_ss_filtered['自習時間(分)'].sum()
                hours = total_minutes // 60
                mins = total_minutes % 60
                study_time_text = f"今月の自習時間: 合計 {int(hours)}時間{int(mins)}分 ⏱️"

        # ==========================================
        # 📝 先生の手動入力エリア（今日の特記事項）
        # ==========================================
        st.subheader("✍️ 今日の授業ハイライト")
        c1, c2 = st.columns(2)
        progress = c1.text_input("📚 本日の進捗 (例: 英語 P.10~15)", value="")
        attitude = c2.selectbox("🧠 授業中の様子", ["非常に集中していた", "少し疲れが見えた", "質問が多く積極的だった", "ミスに悔しがり改善しようとしていた"], index=0)
        teacher_comment = st.text_area("🗣️ 先生からのコメント (褒めポイントやアドバイス)", height=100)

        st.divider()

        # ==========================================
        # 📱 LINEメッセージの自動生成
        # ==========================================
        st.subheader("📋 生成されたLINEメッセージ")
        
        # 今日の日付
        today_str = datetime.date.today().strftime("%m月%d日")

        line_message = f"""保護者様

お世話になっております。本日の {selected_student} さんの学習状況をご報告いたします。

📅 【本日の授業内容】
・進捗：{progress if progress else "（未入力）"}
・様子：{attitude}

💯 【直近の小テスト結果】
・{latest_quiz_text}

📈 【自習の頑張り】
・{study_time_text}

🗣️ 【担当講師より】
{teacher_comment if teacher_comment else "本日はよく頑張りました！引き続きよろしくお願いいたします。"}

ご不明な点がございましたら、お気軽にご連絡ください。"""

        # st.codeを使うと、右上に自動的に「コピー」ボタンが表示されるのでLINEに貼り付けやすいです
        st.code(line_message, language="text")
        st.caption("👆 右上のコピーボタンを押して、そのままLINEに貼り付けてください。")