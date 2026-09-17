import streamlit as st
import pandas as pd
import datetime

# 🌟 必要な関数をインポート
from utils.g_sheets import (
    get_student_master,
    load_self_study_data,
    load_quiz_records,
    get_quiz_master_dict
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

# --- メイン描画関数 ---
def render_monthly_visual_report_tab():
    st.write("保護者のLINEへ送付する「月間学習レポート（テキスト版）」を自動生成します。")
    st.caption("※対象の月を選ぶだけで、全員分のレポート文章が瞬時に作成されます。コピーしてLINEに貼り付けてください。")
    
    # 🌟 UI: 月の選択（デフォルトは今月）
    today = datetime.date.today()
    month_options = [(today.replace(day=1) - pd.DateOffset(months=i)).strftime('%Y年%m月') for i in range(6)]
    selected_month = st.selectbox("📅 出力する月を選択", month_options, index=0)
    
    st.divider()
    
    with st.spinner("データを集計中..."):
        df_students = cached_get_student_master()
        df_ss = cached_load_self_study()
        df_quiz = cached_load_quiz_records()
        quiz_master = cached_get_quiz_master()

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

    # --- 生徒の振り分け（校舎ごと） ---
    id_col = '生徒ID' if '生徒ID' in df_students.columns else None
    name_col = '生徒名' if '生徒名' in df_students.columns else '名前'
    
    target_students = df_students.to_dict('records')
    data_buckets = {"田端新町校": [], "東十条駅前校": [], "体験授業": [], "その他": []}
    
    for s in target_students:
        s_id = str(s.get(id_col, "")).lower()
        # 退塾などのステータスがあればここで弾く処理を入れてもOKです
        if s_id == "trial": data_buckets["体験授業"].append(s)
        elif s_id.startswith('t'): data_buckets["田端新町校"].append(s)
        elif s_id.startswith('h'): data_buckets["東十条駅前校"].append(s)
        else: data_buckets["その他"].append(s)

    # 空のタブは表示しない
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

                # ==========================================
                # ① 自習時間の計算
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
                # ② 小テスト結果のリスト化（満点も計算）
                # ==========================================
                quiz_lines = []
                if not df_quiz_month.empty:
                    s_quiz = df_quiz_month[df_quiz_month['名前'] == student_name]
                    for _, row in s_quiz.iterrows():
                        t_name_raw = row.get('テキスト', '不明')
                        chap_raw = row.get('単元', '不明')
                        score = row.get('点数', '不明')
                        
                        t_name = str(t_name_raw).strip()
                        
                        # 単元名のクリーニング
                        try:
                            chap = str(int(float(chap_raw)))
                        except Exception:
                            chap = str(chap_raw).strip()
                            if chap.endswith('.0'):
                                chap = chap[:-2]
                        
                        # マスターから満点を探す（部分一致）
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
                # ③ LINEメッセージの組み立て
                # ==========================================
                message = f"""保護者様

いつもお世話になっております。
【{selected_month}】の {student_name} さんの学習状況をご報告いたします。

⏱️ 【今月の自習時間（授業外）】
合計： {ss_text}

💯 【今月の小テスト結果】
{quiz_result_text}

🗣️ 【教室長より】
（※ここに今月の頑張りに対するコメントを添えてください）

来月も引き続き、目標に向けてしっかりサポートしてまいります。
よろしくお願いいたします。
槌屋"""

                # ==========================================
                # ④ 画面への出力（アコーディオン）
                # ==========================================
                with st.expander(f"👤 {student_name}", expanded=False):
                    st.code(message, language="text")
                    st.caption("👆 右上のコピーボタンからコピーしてLINEに貼り付けてください")