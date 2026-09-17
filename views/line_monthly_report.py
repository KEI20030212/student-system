import streamlit as st
import pandas as pd
import datetime

# 🌟 必要な関数をインポート（get_all_logs を追加！）
from utils.g_sheets import (
    get_student_master,
    load_self_study_data,
    load_quiz_records,
    get_quiz_master_dict,
    get_all_logs
)
from utils.api_guard import robust_api_call

# --- キャッシュ関数群 ---
def cached_get_student_master():
    return robust_api_call(get_student_master, fallback_value=pd.DataFrame())

def cached_load_self_study():
    return robust_api_call(load_self_study_data, fallback_value=pd.DataFrame())

def cached_load_quiz_records():
    return robust_api_call(load_quiz_records, fallback_value=pd.DataFrame())

def cached_get_quiz_master():
    return robust_api_call(get_quiz_master_dict, fallback_value={})

def cached_get_all_logs():
    return robust_api_call(get_all_logs, fallback_value=pd.DataFrame())

# --- メイン描画関数 ---
def render_monthly_visual_report_tab():
    st.write("保護者のLINEへ送付する「月間学習レポート（テキスト版）」を自動生成します。")
    st.caption("※対象の月を選ぶだけで、全員分のレポート文章が瞬時に作成されます。コピーしてLINEに貼り付けてください。")
    
    # UI: 月の選択（デフォルトは今月）
    today = datetime.date.today()
    month_options = [(today.replace(day=1) - pd.DateOffset(months=i)).strftime('%Y年%m月') for i in range(6)]
    selected_month = st.selectbox("📅 出力する月を選択", month_options, index=0)
    
    st.divider()
    
    with st.spinner("データを集計中..."):
        df_students = cached_get_student_master()
        df_ss = cached_load_self_study()
        df_quiz = cached_load_quiz_records()
        quiz_master = cached_get_quiz_master()
        df_logs = cached_get_all_logs() # 🌟 追加: 授業コマ数を数えるために取得

    if df_students.empty:
        st.warning("生徒データが読み込めません。")
        return

    # --- データの事前処理（選択された月で絞り込み） ---
    # 自習データ
    if not df_ss.empty and "APIエラー発生" not in df_ss.columns:
        df_ss['日付'] = pd.to_datetime(df_ss['日付'], errors='coerce')
        df_ss['年月'] = df_ss['日付'].dt.strftime('%Y年%m月')
        df_ss_month = df_ss[df_ss['年月'] == selected_month].copy()
    else:
        df_ss_month = pd.DataFrame()

    # 小テストデータ
    if not df_quiz.empty and "APIエラー発生" not in df_quiz.columns:
        df_quiz['日時'] = pd.to_datetime(df_quiz['日時'], format='mixed', errors='coerce')
        df_quiz['年月'] = df_quiz['日時'].dt.strftime('%Y年%m月')
        df_quiz_month = df_quiz[df_quiz['年月'] == selected_month].copy()
    else:
        df_quiz_month = pd.DataFrame()

    # 授業記録データ（NEW!）
    if not df_logs.empty and "APIエラー発生" not in df_logs.columns:
        df_logs['日時'] = pd.to_datetime(df_logs['日時'], format='mixed', errors='coerce')
        df_logs['年月'] = df_logs['日時'].dt.strftime('%Y年%m月')
        df_logs_month = df_logs[df_logs['年月'] == selected_month].copy()
    else:
        df_logs_month = pd.DataFrame()

    # --- 生徒の振り分け（校舎ごと） ---
    id_col = '生徒ID' if '生徒ID' in df_students.columns else None
    name_col = '生徒名' if '生徒名' in df_students.columns else '名前'
    
    target_students = df_students.to_dict('records')
    data_buckets = {"田端新町校": [], "東十条駅前校": [], "体験授業": [], "その他": []}
    
    for s in target_students:
        s_id = str(s.get(id_col, "")).lower()
        if s_id == "trial": data_buckets["体験授業"].append(s)
        elif s_id.startswith('t'): data_buckets["田端新町校"].append(s)
        elif s_id.startswith('h'): data_buckets["東十条駅前校"].append(s)
        else: data_buckets["その他"].append(s)

    display_buckets = {k: v for k, v in data_buckets.items() if len(v) > 0 or k != "その他"}
    tabs = st.tabs([f"🏫 {k} ({len(v)}名)" for k, v in display_buckets.items()])

    # --- タブごとの描画 ---
    for t_idx, (bucket_name, students) in enumerate(display_buckets.items()):
        with tabs[t_idx]:
            if not students:
                st.caption("対象の生徒はいません。")
                continue

            for student_info in students:
                student_id = student_info.get(id_col, "未設定")
                student_name = student_info.get(name_col, "不明")

                # 目標・志望校の抽出（NEW!）
                target_goal = ""
                for key, value in student_info.items():
                    if "志望校" in str(key) or "目的" in str(key) or "目標" in str(key):
                        val_str = str(value).strip()
                        if val_str and val_str.lower() != "nan":
                            target_goal = val_str
                            break

                # ==========================================
                # ① 授業コマ数の計算（NEW!）
                # ==========================================
                class_count = 0
                if not df_logs_month.empty:
                    log_name_col = '生徒名' if '生徒名' in df_logs_month.columns else '名前'
                    s_logs = df_logs_month[df_logs_month[log_name_col] == student_name]
                    class_count = len(s_logs)

                # ==========================================
                # ② 自習時間の計算
                # ==========================================
                total_ss_minutes = 0
                if not df_ss_month.empty:
                    s_ss = df_ss_month[df_ss_month['名前'] == student_name]
                    total_ss_minutes = pd.to_numeric(s_ss['自習時間(分)'], errors='coerce').sum()
                
                hours = int(total_ss_minutes // 60)
                minutes = int(total_ss_minutes % 60)
                ss_text = f"{hours}時間 {minutes}分" if hours > 0 else f"{minutes}分"
                if total_ss_minutes == 0:
                    ss_text = "0分"

                # ==========================================
                # ③ 小テスト結果のリスト化（順番整理版！）
                # ==========================================
                quiz_lines = []
                if not df_quiz_month.empty:
                    s_quiz = df_quiz_month[df_quiz_month['名前'] == student_name].copy()
                    
                    # 🌟 順番整理：テキスト名で並び替える（同じテキストが連続するようになります）
                    if not s_quiz.empty:
                        s_quiz = s_quiz.sort_values(by=['テキスト', '日時'], ascending=[True, True])

                    for _, row in s_quiz.iterrows():
                        t_name_raw = row.get('テキスト', '不明')
                        chap_raw = row.get('単元', '不明')
                        score = row.get('点数', '不明')
                        
                        t_name = str(t_name_raw).strip()
                        
                        try:
                            chap = str(int(float(chap_raw)))
                        except Exception:
                            chap = str(chap_raw).strip()
                            if chap.endswith('.0'):
                                chap = chap[:-2]
                        
                        full_marks = 100 
                        for key_in_dict, data_in_dict in quiz_master.items():
                            if t_name in key_in_dict:
                                full_marks = data_in_dict.get("full_marks", 100)
                                break 
                        
                        if isinstance(full_marks, float) and full_marks.is_integer():
                            full_marks = int(full_marks)
                            
                        quiz_lines.append(f"・【{t_name} {chap}】: {score}/{full_marks}点")
                
                quiz_result_text = "\n".join(quiz_lines) if quiz_lines else "今月の小テスト実施記録はありません。"

                # ==========================================
                # ④ メッセージ文面の組み立て（固定・自動化）
                # ==========================================
                # 目標がある場合とない場合で、文言を少し変える
                target_msg = f"「{target_goal}」の目標達成に向けて、" if target_goal else "目標達成に向けて、"

                message = f"""保護者様

いつもお世話になっております。
【{selected_month}】の {student_name} さんの学習状況をご報告いたします。

🏫 【今月の授業受講数】
合計： {class_count} コマ

⏱️ 【今月の自習時間（授業外）】
合計： {ss_text}

💯 【今月の小テスト結果】
{quiz_result_text}

🗣️ 【教室長より】
今月も塾での学習、大変お疲れ様でした！
{target_msg}引き続きスタッフ一同、全力でサポートしてまいります。
ご自宅でもぜひ、今月の頑張りを褒めてあげてください！

よろしくお願いいたします。
槌屋"""

                # ==========================================
                # ⑤ 画面への出力（アコーディオン）
                # ==========================================
                with st.expander(f"👤 {student_name}", expanded=False):
                    st.code(message, language="text")
                    st.caption("👆 右上のコピーボタンからコピーしてLINEに貼り付けてください")