import streamlit as st
import datetime
import pandas as pd

# ==========================================
# 🌟 utils/g_sheets.py から必要な関数を呼び出し
# ==========================================
from utils.g_sheets import (
    get_all_student_names,
    load_quiz_data_from_dedicated_sheet,
    load_daily_class_record  # ⚠️ 新しく追加が必要な関数（指定日の授業記録を読み込む）
)

def render_line_report_page():
    st.header("📱 LINE用 授業報告レポート生成")
    st.write("生徒と日付を選択するだけで、LINE送信用のレポートを自動生成します✨")

    # ==========================================
    # 1. 生徒と日付の選択エリア
    # ==========================================
    col1, col2 = st.columns(2)
    student_names = get_all_student_names()
    selected_student = col1.selectbox("👤 生徒を選択", ["-- 選択 --"] + student_names)
    
    # 日付選択（デフォルトは今日）
    selected_date = col2.date_input("📅 授業日を選択", datetime.date.today())

    if selected_student == "-- 選択 --":
        st.info("👆 レポートを作成する生徒と日付を選択してください。")
        st.stop()

    st.divider()

    with st.spinner("スプレッドシートからデータを取得中..."):
        date_str = selected_date.strftime("%Y/%m/%d")

        # ==========================================
        # 📊 ① 授業記録の自動取得（生徒別シートから）
        # ==========================================
        class_record = load_daily_class_record(selected_student, date_str)
        
        if not class_record:
            st.warning(f"⚠️ {date_str} の {selected_student} さんの授業記録が見つかりません。")
            subject = "（未入力）"
            period = "（未入力）"
            progress = "（未入力）"
            attitude = "（未入力）"
            advice = "（未入力）"
            parent_msg = "（未入力）"
        else:
            # 💡 スプレッドシートの列名からデータを取得
            subject = class_record.get("科目", "（未入力）")
            period = class_record.get("授業コマ", "（未入力）")
            
            # テキスト・単元・終了ページを合体させて、綺麗な「進捗」の文章にする
            text_name = class_record.get("テキスト", "")
            unit = class_record.get("単元", "")
            end_page = class_record.get("終了ページ", "")
            progress = f"{text_name} {unit}（〜{end_page}ページまで）" if text_name else "（未入力）"
            
            # 集中力と反応を合体させる
            concentration = class_record.get("集中力", "")
            reaction = class_record.get("反応", "")
            attitude = f"集中力: {concentration} / 反応: {reaction}" if concentration or reaction else "（未入力）"
            
            advice = class_record.get("アドバイス", "（特になし）")
            parent_msg = class_record.get("保護者への連絡", "（特になし）")

        # ==========================================
        # 📝 ② 小テスト結果の自動取得と判定
        # ==========================================
        df_quiz = load_quiz_data_from_dedicated_sheet(selected_student)
        quiz_text = "小テストは実施していません" # デフォルト値

        if not df_quiz.empty:
            # 日時列を日付型に変換して比較する
            df_quiz['日時'] = pd.to_datetime(df_quiz['日時'], format='mixed', errors='coerce')
            target_date = pd.to_datetime(selected_date).date()
            
            # 選択した日付と完全に一致する小テストデータを抽出
            daily_quiz = df_quiz[df_quiz['日時'].dt.date == target_date]
            
            if not daily_quiz.empty:
                quiz_results = []
                for _, row in daily_quiz.iterrows():
                    # 💡 もし「授業内でやったものだけ」に絞りたい場合は
                    # if row.get("実施形態") == "授業内": などで分岐させます
                    text_name = row.get('テキスト', '不明')
                    chap_name = row.get('単元', '不明') # 既存のquiz_dashboardに合わせて'単元'としています
                    score = row.get('点数', '不明')
                    miss_nums = row.get('ミス問題番号', '')
                    
                    miss_text = f"（ミス: {miss_nums}）" if miss_nums else "（ミスなし💮）"
                    quiz_results.append(f"【{text_name} {chap_name}】: {score}点 {miss_text}")
                
                # 複数のテストがあった場合にも対応できるように改行でつなぐ
                if quiz_results:
                    quiz_text = "\n・".join(quiz_results)

        # ==========================================
        # 📱 LINEメッセージの自動出力
        # ==========================================
        st.subheader("📋 完成したLINEメッセージ")
        
        line_message = f"""保護者様

お世話になっております。本日の {selected_student} さんの授業報告をいたします。

📅 【授業内容】（{date_str} {period}）
・科目：{subject}
・進捗：{progress}
・様子：{attitude}

💯 【小テスト結果】
・{quiz_text}

🗣️ 【担当講師より（アドバイス等）】
{advice}

📢 【ご連絡事項】
{parent_msg}

ご不明な点がございましたら、お気軽にご連絡ください。
引き続きよろしくお願いいたします。"""

        # そのままコピーできるようにコードブロックで表示
        st.code(line_message, language="text")
        st.caption("👆 右上のコピーボタンを押して、そのままLINEに貼り付けて送信できます！")