import streamlit as st
import pandas as pd
import datetime

# 🌟 必要な関数をインポート
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
        df_logs = cached_get_all_logs() 

    if df_students.empty:
        st.warning("生徒データが読み込めません。")
        return

    # --- データの事前処理（選択された月で絞り込み） ---
    if not df_ss.empty and "APIエラー発生" not in df_ss.columns:
        df_ss['日付'] = pd.to_datetime(df_ss['日付'], errors='coerce')
        df_ss['年月'] = df_ss['日付'].dt.strftime('%Y年%m月')
        df_ss_month = df_ss[df_ss['年月'] == selected_month].copy()
    else:
        df_ss_month = pd.DataFrame()

    if not df_quiz.empty and "APIエラー発生" not in df_quiz.columns:
        df_quiz['日時'] = pd.to_datetime(df_quiz['日時'], format='mixed', errors='coerce')
        df_quiz['年月'] = df_quiz['日時'].dt.strftime('%Y年%m月')
        df_quiz_month = df_quiz[df_quiz['年月'] == selected_month].copy()
    else:
        df_quiz_month = pd.DataFrame()

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

                s_logs = pd.DataFrame()
                if not df_logs_month.empty:
                    log_name_col = '生徒名' if '生徒名' in df_logs_month.columns else '名前'
                    s_logs = df_logs_month[df_logs_month[log_name_col] == student_name]

                # ==========================================
                # ① 授業コマ数の計算（1:1(Q)を分離）
                # ==========================================
                q_count = 0
                normal_count = 0
                if not s_logs.empty:
                    for _, r in s_logs.iterrows():
                        row_str = str(r.to_dict().values()).replace(" ", "").replace(" ", "")
                        if "1:1(Q)" in row_str or "1:1(Ｑ)" in row_str:
                            q_count += 1
                        else:
                            normal_count += 1
                
                if q_count > 0:
                    class_text = f"・通常コース： {normal_count} コマ\n・クオリティコース(1:1Q)： {q_count} コマ"
                else:
                    class_text = f"合計： {normal_count} コマ"

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
                # ③ 宿題達成率の計算（🌟 記録なしなら非表示）
                # ==========================================
                assigned = 0
                done = 0
                hw_rate = -1
                if not s_logs.empty and '出した宿題P' in s_logs.columns and 'やった宿題P' in s_logs.columns:
                    assigned = pd.to_numeric(s_logs['出した宿題P'], errors='coerce').fillna(0).sum()
                    done = pd.to_numeric(s_logs['やった宿題P'], errors='coerce').fillna(0).sum()
                
                if assigned > 0:
                    hw_rate = min(int((done / assigned) * 100), 100)
                    hw_block = f"📝 【今月の宿題達成率】\n合計： {hw_rate} %\n\n"
                else:
                    # 🌟 宿題を出していない（記録がない）場合はブロックごと消す
                    hw_block = ""

                # ==========================================
                # ④ 小テスト結果のリスト化
                # ==========================================
                quiz_lines = []
                if not df_quiz_month.empty:
                    s_quiz = df_quiz_month[df_quiz_month['名前'] == student_name].copy()
                    
                    if not s_quiz.empty:
                        s_quiz['単元_ソート用'] = s_quiz['単元'].astype(str).str.extract(r'(\d+)')[0]
                        s_quiz['単元_ソート用'] = pd.to_numeric(s_quiz['単元_ソート用'], errors='coerce').fillna(9999)
                        s_quiz = s_quiz.sort_values(by=['テキスト', '単元_ソート用', '日時'], ascending=[True, True, True])

                    for _, row in s_quiz.iterrows():
                        t_name_raw = row.get('テキスト', '不明')
                        chap_raw = row.get('単元', '不明')
                        score = row.get('点数', '不明')
                        
                        t_name = str(t_name_raw).strip()
                        try:
                            chap = str(int(float(chap_raw)))
                        except Exception:
                            chap = str(chap_raw).strip()
                            if chap.endswith('.0'): chap = chap[:-2]
                        
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
                # ⑤ 自動褒め言葉（ルールベース）の生成
                # ==========================================
                dynamic_praise = ""
                if hw_rate >= 90:
                    dynamic_praise = "毎回の宿題も非常に高い達成率でこなせており、素晴らしい学習習慣が身についています！"
                elif total_ss_minutes >= 600:
                    dynamic_praise = "今月は自習にも積極的に取り組むことができ、素晴らしい努力の成果が出ています！"
                elif quiz_lines:
                    dynamic_praise = "小テストにもコツコツと取り組み、着実に基礎力を固めることができました！"
                else:
                    dynamic_praise = "日々の授業に真剣に取り組み、一歩ずつ着実に前進しています！"

                # ==========================================
                # ⑥ メッセージ文面の組み立て
                # ==========================================
                # 🌟 {hw_block} を配置（空文字なら何も表示されない）
                message = f"""保護者様

いつもお世話になっております。
【{selected_month}】の {student_name} さんの学習状況をご報告いたします。

🏫 【今月の授業受講数】
{class_text}

⏱️ 【今月の自習時間（授業外）】
合計： {ss_text}

{hw_block}💯 【今月の小テスト結果】
{quiz_result_text}

🗣️ 【教室長より】
今月も塾での学習、大変お疲れ様でした！
{dynamic_praise}
引き続きスタッフ一同、全力でサポートしてまいります。
ご自宅でもぜひ、今月の頑張りを褒めてあげてください！

よろしくお願いいたします。
槌屋"""

                # ==========================================
                # ⑦ 画面への出力（アコーディオン）
                # ==========================================
                with st.expander(f"👤 {student_name}", expanded=False):
                    st.code(message, language="text")
                    st.caption("👆 右上のコピーボタンからコピーしてLINEに貼り付けてください")