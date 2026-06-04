import streamlit as st
import datetime
import pandas as pd
import time

from utils.g_sheets import (
    get_all_logs,
    load_quiz_records, 
    load_school_homework_data,
    get_sent_list,      # 🌟 追加
    update_sent_flag    # 🌟 追加
)
# 🌟 追加：URL生成のために裏側のフォルダ取得関数をインポート
from utils.g_drive import get_or_create_student_folder
from utils.api_guard import robust_api_call

# 🌟 全データを一括取得するキャッシュ関数群
@st.cache_data(ttl=60, show_spinner=False)
def cached_get_all_logs():
    return robust_api_call(get_all_logs, fallback_value=pd.DataFrame())

@st.cache_data(ttl=60, show_spinner=False)
def cached_load_quiz_records():
    return robust_api_call(load_quiz_records, fallback_value=pd.DataFrame())

@st.cache_data(ttl=60, show_spinner=False)
def cached_load_hw_records():
    return robust_api_call(load_school_homework_data, fallback_value=pd.DataFrame())

def translate_to_chinese(text):
    """塾の報告書でよく使うキーワードや状態ラベルを丁寧な中国語に変換するヘルパー関数"""
    if not isinstance(text, str):
        return text
    
    mapping = {
        "（未入力）": "（未填写）",
        "集中力:": "专注力:",
        "ミスへの反応:": "对错题的反应:",
        "・進捗：": "・课堂进度：",
        "・様子：": "・课堂表现：",
        "・宿題状況：未達成": "・作业完成情况：未完成",
        "（理由:": "（原因:",
        " ➡ 対策: ": " ➡ 改善对策: ",
        "不明": "未知",
        "点": "分",
        "小テストは実施していません": "今日未安排小测验",
        "英語": "英语",
        "数学": "数学",
        "国語": "国语(日语)",
        "理科": "理科/科学",
        "社会": "社会/文科",
        "その他": "其他"
    }
    for k, v in mapping.items():
        text = text.replace(k, v)
    return text

def render_line_report_page():
    st.header("📱 LINE用 授業報告レポート一括生成")
    st.write("授業日を選択するだけで、**校舎ごと**に全生徒のレポートを自動生成します✨")

    selected_date = st.date_input("📅 授業日を選択", datetime.date.today())
    date_str = selected_date.strftime("%Y/%m/%d")

    # 🌟 送信済みリストを読み込み
    sent_id_list = robust_api_call(get_sent_list, date_str, fallback_value=[])

    st.divider()

    with st.spinner(f"{date_str} の全レポートを作成中..."):
        df_all_logs = cached_get_all_logs()
        df_all_quizzes = cached_load_quiz_records()
        df_hw = cached_load_hw_records()

        if df_all_logs.empty or "APIエラー発生" in df_all_logs.columns:
            st.error("授業記録データの取得に失敗しました。")
            st.stop()

        df_all_logs['日時'] = pd.to_datetime(df_all_logs['日時'], format='mixed', errors='coerce')
        daily_logs = df_all_logs[df_all_logs['日時'].dt.date == selected_date]

        if daily_logs.empty:
            st.info(f"📅 {date_str} の授業記録はまだありません。")
            st.stop()

        id_col = '生徒ID' if '生徒ID' in daily_logs.columns else None
        name_col = '名前' if '名前' in daily_logs.columns else '生徒名'

        # 生徒リストを抽出
        target_students = daily_logs[[id_col, name_col]].drop_duplicates().to_dict('records')

        # 🌟 校舎・種別ごとに振り分け
        # t: 田端新町校, h: 東十条駅前校, TRIAL: 体験, その他
        data_buckets = {
            "田端新町校": [],
            "東十条駅前校": [],
            "体験授業": [],
            "その他": []
        }

        for s in target_students:
            s_id = str(s.get(id_col, "")).lower()
            if s_id == "trial":
                data_buckets["体験授業"].append(s)
            elif s_id.startswith('t'):
                data_buckets["田端新町校"].append(s)
            elif s_id.startswith('h'):
                data_buckets["東十条駅前校"].append(s)
            else:
                data_buckets["その他"].append(s)

        # 🌟 表示するバケット（校舎）だけを先に抽出する
        display_buckets = {k: v for k, v in data_buckets.items() if len(v) > 0 or k != "その他"}

        # 🌟 表示する校舎の分だけタブを作成
        tabs = st.tabs([f"🏫 {k} ({len(v)}名)" for k, v in display_buckets.items()])

        # 抽出したバケットでループを回す
        for t_idx, (bucket_name, students) in enumerate(display_buckets.items()):
            with tabs[t_idx]:
                if not students:
                    st.caption("対象の生徒はいません。")
                    continue

                for s_idx, student_info in enumerate(students):
                    student_id = student_info.get(id_col, "未設定")
                    student_name = student_info.get(name_col, "不明")

                    # --- 個別レポート生成ロジック ---
                    student_classes = daily_logs[daily_logs[id_col].astype(str) == str(student_id)]
                    
                    class_sections = []
                    advice_sections = []
                    parent_msg_sections = []
                    bring_sections = []
                    hw_sections = []

                    for _, row in student_classes.iterrows():
                        teacher = row.get("担当講師", "（未入力）")
                        subject = row.get("科目", "（未入力）")
                        period = row.get("授業コマ", "（未入力）")
                        
                        text_name = str(row.get("テキスト", "")).strip()
                        if text_name == "nan": text_name = ""
                        end_page = str(row.get("終了ページ", "")).strip()
                        if end_page == "nan": end_page = ""
                        
                        if end_page:
                            progress = "\n　" + end_page.replace("\n", "\n　") if "\n" in end_page else end_page
                        elif text_name:
                            progress = f"{text_name}"
                        else:
                            progress = "（未入力）"
                        
                        concentration = row.get("集中力", "")
                        reaction = row.get("ミスへの反応", "")
                        attitude = f"集中力: {concentration} / ミスへの反応: {reaction}" if concentration or reaction else "（未入力）"

                        hw_reason = str(row.get("未達成の理由", "")).strip()
                        hw_fix = str(row.get("本日の修正策", "")).strip()
                        hw_status_line = f"\n・宿題状況：未達成（理由: {hw_reason.replace('その他: ','')} ➡ 対策: {hw_fix.replace('その他: ','')}）" if (hw_reason and hw_reason != "nan") or (hw_fix and hw_fix != "nan") else ""
                        
                        advice = str(row.get("授業アドバイス", row.get("アドバイス", ""))).strip()
                        parent_msg = str(row.get("保護者への連絡", "")).strip()
                        
                        bring = str(row.get("次回の持ち物", "")).strip()
                        if bring and bring != "nan":
                            bring_sections.append(f"・{bring}（{subject}）")

                        next_hw_pages = str(row.get("次回の宿題ページ数", "")).strip()
                        if next_hw_pages == "nan" or next_hw_pages == "-": next_hw_pages = ""

                        hw_content = ""
                        if next_hw_pages:
                            hw_content = f"{next_hw_pages}"

                        prefix = "🎨 【体験内容】" if bucket_name == "体験授業" else "📅 【授業内容】"
                        class_text = f"{prefix}（{period} / {subject} / 担当：{teacher}）\n・進捗：{progress}\n・様子：{attitude}{hw_status_line}"
                        class_sections.append(class_text)

                        if advice and advice != "nan":
                            advice_sections.append(f"《{subject if bucket_name != '体験授業' else ''} {teacher}先生より》\n{advice}")
                        if parent_msg and parent_msg != "nan":
                            parent_msg_sections.append(f"《{subject if bucket_name != '体験授業' else ''} {teacher}先生より》\n{parent_msg}")
                        if hw_content:
                            hw_sections.append(f"《{subject if bucket_name != '体験授業' else ''} {teacher}先生より》\n{hw_content}")

                    classes_text = "\n\n".join(class_sections)
                    bring_text = f"🎒 【次回の持ち物】\n" + "\n".join(bring_sections) + "\n\n" if bring_sections else ""
                    hw_text = f"📘 【次回の宿題】\n" + "\n\n".join(hw_sections) + "\n\n" if hw_sections else ""

                    # 小テスト & Drive
                    quiz_text = "小テストは実施していません"
                    drive_url_line = ""
                    if not df_all_quizzes.empty:
                        df_all_quizzes['日時'] = pd.to_datetime(df_all_quizzes['日時'], format='mixed', errors='coerce')
                        student_quizzes = df_all_quizzes[(df_all_quizzes['名前'] == student_name) & (df_all_quizzes['日時'].dt.date == selected_date)]
                        if not student_quizzes.empty:
                            quiz_results = [f"【{row.get('テキスト', '不明')} {row.get('単元', '不明')}】: {row.get('点数', '不明')}点" for _, row in student_quizzes.iterrows()]
                            quiz_text = "\n・".join(quiz_results)
                            folder_id = robust_api_call(get_or_create_student_folder, student_id, student_name, fallback_value=None)
                            if folder_id:
                                drive_url_line = f"📂 【本日の答案確認URL】\nhttps://drive.google.com/drive/folders/{folder_id}\n\n"

                    # 🌟 日本語ベースの各メッセージブロックの組み立て
                    if bucket_name == "体験授業":
                        advices_block = f"🗣️ 【本日の輝いていた点】\n" + "\n\n".join(advice_sections) + "\n\n" if advice_sections else ""
                        msgs_block = f"📢 【今後の課題・ご提案】\n" + "\n\n".join(parent_msg_sections) + "\n\n" if parent_msg_sections else ""
                        
                        line_message_jp = (
                            f"保護者様\n\n"
                            f"本日は {student_name} さんの「体験授業」にお越しいただき、ありがとうございました！\n\n"
                            f"{classes_text}\n\n"
                            f"💯 【小テスト結果】\n・{quiz_text}\n\n"
                            f"{drive_url_line}"
                            f"{bring_text}"
                            f"{advices_block}"
                            f"{msgs_block}"
                            f"引き続きよろしくお願いいたします。\n"
                            f"槌屋"
                        )
                    else:
                        advices_block = f"🗣️ 【アドバイス(褒めた点など)】\n" + "\n\n".join(advice_sections) + "\n\n" if advice_sections else ""
                        msgs_block = f"📢 【ご連絡事項】\n" + "\n\n".join(parent_msg_sections) + "\n\n" if parent_msg_sections else ""
                        
                        line_message_jp = (
                            f"保護者様\n\n"
                            f"お世話になっております。本日の {student_name} さんの授業報告です。\n\n"
                            f"{classes_text}\n\n"
                            f"💯 【小テスト結果】\n・{quiz_text}\n\n"
                            f"{drive_url_line}"
                            f"{bring_text}"
                            f"{hw_text}"
                            f"{advices_block}"
                            f"{msgs_block}"
                            f"よろしくお願いいたします。\n"
                            f"槌屋"
                        )

                    # 🌟 【新機能】中国語選択時のトランスレート処理
                    classes_text_cn = translate_to_chinese(classes_text).replace("📅 【授業内容】", "📅 【课堂内容】").replace("🎨 【体験内容】", "🎨 【试听内容】").replace("担当：", "授课老师：")
                    quiz_text_cn = translate_to_chinese(quiz_text)
                    drive_url_line_cn = drive_url_line.replace("📂 【本日の答案確認URL】", "📂 【今日试卷查看链接】") if drive_url_line else ""
                    bring_text_cn = bring_text.replace("🎒 【次回の持ち物】", "🎒 【下次需带物品】") if bring_text else ""
                    hw_text_cn = hw_text.replace("📘 【次回の宿題】", "📘 【下次作业】") if hw_text else ""

                    if bucket_name == "体験授業":
                        advices_block_cn = advices_block.replace("🗣️ 【本日の輝いていた点】", "🗣️ 【今日表现优秀闪光点】") if advices_block else ""
                        msgs_block_cn = msgs_block.replace("📢 【今後の課題・ご提案】", "📢 【今后学习方向与入校建议】") if msgs_block else ""
                        
                        line_message_cn = (
                            f"家长您好：\n\n"
                            f"非常感谢您今天带 {student_name} 同学来参加我们的「试听体验课」！\n\n"
                            f"{classes_text_cn}\n\n"
                            f"💯 【小测验结果】\n・{quiz_text_cn}\n\n"
                            f"{drive_url_line_cn}"
                            f"{bring_text_cn}"
                            f"{advices_block_cn}"
                            f"{msgs_block_cn}"
                            f"非常感谢您的配合，祝您生活愉快。\n"
                            f"槌屋"
                        )
                    else:
                        advices_block_cn = advices_block.replace("🗣️ 【アドバイス(褒めた点など)】", "🗣️ 【老师评语(表现与建议)】").replace("先生より》", "老师》") if advices_block else ""
                        msgs_block_cn = msgs_block.replace("📢 【ご連絡事項】", "📢 【通知事项】").replace("先生より》", "老师》") if parent_msg_sections else ""
                        
                        line_message_cn = (
                            f"家长您好：\n\n"
                            f"非常感谢您一直以来的支持与配合。以下是 {student_name} 同学今天的课堂报告：\n\n"
                            f"{classes_text_cn}\n\n"
                            f"💯 【小测验结果】\n・{quiz_text_cn}\n\n"
                            f"{drive_url_line_cn}"
                            f"{bring_text_cn}"
                            f"{hw_text_cn}"
                            f"{advices_block_cn}"
                            f"{msgs_block_cn}"
                            f"祝您生活愉快，谢谢！\n"
                            f"槌屋"
                        )

                    # 🌟 チェックボックスの状態管理
                    checkbox_key = f"sent_{date_str}_{student_id}"
                    is_already_sent = str(student_id) in sent_id_list
                    
                    c_check, c_exp = st.columns([1, 9])
                    
                    check_val = c_check.checkbox("送済", value=is_already_sent, key=checkbox_key)
                    if check_val != is_already_sent:
                        robust_api_call(update_sent_flag, date_str, student_id, check_val)
                        st.rerun()

                    label_suffix = " ［✅ 送信完了］" if check_val else ""
                    with c_exp:
                        with st.expander(f"👤 {student_name} {label_suffix}", expanded=False):
                            
                            # 🌟 アコーディオンの中に言語切り替えスイッチを設置！
                            lang_choice = st.radio(
                                "🌐 レポート言語を選択してください / 请选择报告语言", 
                                ["日本語", "中国語 (简体中文)"], 
                                key=f"lang_{date_str}_{student_id}",
                                horizontal=True
                            )
                            
                            # 選択された言語のメッセージをセット
                            final_message = line_message_cn if lang_choice == "中国語 (简体中文)" else line_message_jp
                            
                            st.code(final_message, language="text")
                            st.caption("👆 コピーしてLINEへペースト！")