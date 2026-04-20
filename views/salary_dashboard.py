import streamlit as st
import pandas as pd
import math
import time
import zipfile
import io
import unicodedata

from utils.g_sheets import get_all_student_names, load_all_data, load_instructor_master, update_instructor_master
from utils.pdf_generator import generate_payslip_pdf
from utils.g_sheets import publish_salary_data

# 🌟【追加】絶対に失敗させないための「自動リトライ」関数
def robust_api_call(func, *args, retries=3, fallback_value=None, **kwargs):
    """
    Googleスプレッドシートの通信エラーを自動で再試行するラッパー関数
    失敗するたびに 1秒 → 2秒 → 4秒 と待機時間を延ばして再アタックします。
    """
    for attempt in range(retries):
        try:
            result = func(*args, **kwargs)
            # 関数が戻り値を持たない(None)場合は、成功の証としてTrueを返す
            return True if result is None else result 
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # 指数的バックオフ
            else:
                st.toast(f"⚠️ 通信に失敗しました。再読み込みをお試しください。")
                return fallback_value

def render_salary_dashboard_page():
    st.header("💰 給与・交通費ダッシュボード")
    
    if st.button("🔄 最新の授業データを読み込み直す"):
        if 'salary_df_all' in st.session_state:
            del st.session_state['salary_df_all']
        st.cache_data.clear() 
        st.rerun()

    # --- 1. マスタ読み込み（自動リトライ＆KeyError 完全防御版） ---
    df_instructors = robust_api_call(load_instructor_master, fallback_value=pd.DataFrame())
    
    # 🌟 エラーの元凶対策：シートが完全に空だったり、カラム名がおかしい場合は強制的に枠組みを作る
    if type(df_instructors) != pd.DataFrame or df_instructors.empty or "講師名" not in df_instructors.columns:
        df_instructors = pd.DataFrame(columns=["講師名", "1:1単価", "1:2単価", "1:3単価", "交通費", "役職手当"])

    with st.expander("🏢 新規講師用の「基本」コマ単価設定", expanded=False):
        c1, c2, c3 = st.columns(3)
        base_price_1on1 = c1.number_input("1:1 基本単価 (円)", value=1500, step=100)
        base_price_1on2 = c2.number_input("1:2 基本単価 (円)", value=1800, step=100)
        base_price_1on3 = c3.number_input("1:3 基本単価 (円)", value=2000, step=100)

    # --- 2. 授業データ読み込みと先生の抽出 ---
    # 読み込みに失敗してもエディタは表示させるために、一旦変数を初期化しておく
    df_month_exploded = None
    valid_teachers = []
    selected_month = None

    # 🌟 自動リトライで生徒名を取得
    student_names = robust_api_call(get_all_student_names, fallback_value=[])
    if not student_names:
        st.warning("⚠️ 生徒データの取得で一時的なエラーが発生しました。時間を置いて再読み込みしてください。")

    if student_names:
        if 'salary_df_all' not in st.session_state:
            all_data_list = []
            st.subheader("☁️ データ集計状況")
            p_bar = st.progress(0)
            t_status = st.empty()
            
            for i, s_name in enumerate(student_names):
                t_status.text(f"📥 {s_name} さんのデータを読み込み中... ({i+1}/{len(student_names)})")
                
                # 🌟 各生徒のデータ取得も自動リトライで保護
                df = robust_api_call(load_all_data, s_name, fallback_value=pd.DataFrame())
                
                if not df.empty:
                    df['生徒名'] = s_name
                    all_data_list.append(df)
                    
                p_bar.progress((i + 1) / len(student_names))
                time.sleep(0.1) # API制限を避けるための微小な待機
            
            t_status.empty()
            p_bar.empty()
            
            if all_data_list:
                st.session_state['salary_df_all'] = pd.concat(all_data_list, ignore_index=True)

        if 'salary_df_all' in st.session_state:
            df_all = st.session_state['salary_df_all']
            if '日時' in df_all.columns and '担当講師' in df_all.columns:
                df_all['日時'] = pd.to_datetime(df_all['日時'], format='mixed', errors='coerce')
                df_all = df_all.dropna(subset=['日時'])
                df_all['年月'] = df_all['日時'].dt.strftime("%Y年%m月")

                month_options = sorted(df_all['年月'].unique().tolist(), reverse=True)
                if month_options:
                    selected_month = st.selectbox("📅 集計する月を選択", month_options)
                    df_month = df_all[df_all['年月'] == selected_month].copy()

                    # 表記ゆれ・改行対策
                    df_month['担当講師'] = df_month['担当講師'].astype(str)
                    df_month_exploded = df_month.assign(担当講師=df_month['担当講師'].str.split(r'[\n,、]')).explode('担当講師')
                    df_month_exploded['担当講師'] = df_month_exploded['担当講師'].str.strip()
                    
                    if '授業形態' in df_month_exploded.columns:
                        df_month_exploded['授業形態'] = df_month_exploded['授業形態'].astype(str).apply(
                            lambda x: unicodedata.normalize('NFKC', x).replace(' ', '')
                        )

                    valid_teachers = [t for t in df_month_exploded['担当講師'].unique() if t not in ["未入力", "", "nan", "None"]]

                    # 新しい先生をマスタに自動追加する処理
                    master_teacher_names = df_instructors['講師名'].astype(str).tolist() if not df_instructors.empty else []
                    new_rows = []
                    for t in valid_teachers:
                        if t not in master_teacher_names:
                            new_rows.append({
                                "講師名": t, "1:1単価": base_price_1on1, "1:2単価": base_price_1on2, 
                                "1:3単価": base_price_1on3, "交通費": 0, "役職手当": 0
                            })
                    if new_rows:
                        df_instructors = pd.concat([df_instructors, pd.DataFrame(new_rows)], ignore_index=True)

    st.divider()

    # --- 3. 👨‍🏫 講師ごとの単価・設定（データが無くてもここは必ず表示！） ---
    st.subheader("👨‍🏫 講師ごとの単価・設定")
    with st.form("master_edit_form"):
        st.info("💡 単価を変更した後は、必ず下の「保存する」ボタンを押してください。")
        current_editor_df = st.data_editor(
            df_instructors, 
            hide_index=True, 
            use_container_width=True, 
            num_rows="dynamic",
            key="master_editor_key"
        )
        submit_btn = st.form_submit_button("💾 変更をスプレッドシート（マスタ）に保存する", type="primary")

    if submit_btn:
        with st.spinner("☁️ スプレッドシートに保存中...（通信状況により数秒かかります）"):
            # 🌟 保存処理も自動リトライで保護
            success = robust_api_call(update_instructor_master, current_editor_df, fallback_value=False)
            
            if success is not False:
                st.cache_data.clear() 
                time.sleep(1)
                st.success("✅ スプレッドシートを更新しました！")
                st.rerun() 
            else:
                st.error("⚠️ 通信エラーにより保存に失敗しました。時間をおいて再度お試しください。")

    st.divider()

    # --- 4. 給与計算と表示（データが準備できた場合のみ実行） ---
    if df_month_exploded is not None and not df_month_exploded.empty and selected_month:
        summary_list = []
        for teacher in valid_teachers:
            df_teacher = df_month_exploded[df_month_exploded['担当講師'] == teacher].copy()
            df_teacher['日付'] = df_teacher['日時'].dt.date
            
            # 重複排除（同じ生徒・同じ日・同じコマ）
            if '生徒名' in df_teacher.columns:
                df_teacher = df_teacher.drop_duplicates(subset=['生徒名', '日付', '授業コマ'])

            t_row_df = df_instructors[df_instructors["講師名"] == teacher]
            if t_row_df.empty: continue
            t_row = t_row_df.iloc[0]

            def safe_int(val, default=0):
                try: return int(float(val)) if not pd.isna(val) and val != "" else default
                except: return default

            p11 = safe_int(t_row.get('1:1単価', 1500), 1500)
            p12 = safe_int(t_row.get('1:2単価', 1800), 1800)
            p13 = safe_int(t_row.get('1:3単価', 2000), 2000)
            trans = safe_int(t_row.get('交通費', 0), 0)
            allowance = safe_int(t_row.get('役職手当', 0), 0)

            koma_11, koma_12, koma_13 = 0, 0, 0
            for _, group in df_teacher.groupby(['日付', '授業コマ']):
                koma_11 += math.ceil(len(group[group['授業形態'] == '1:1']) / 1)
                koma_12 += math.ceil(len(group[group['授業形態'] == '1:2']) / 2)
                koma_13 += math.ceil(len(group[group['授業形態'] == '1:3']) / 3)

            total_koma = koma_11 + koma_12 + koma_13
            koma_salary = (koma_11 * p11) + (koma_12 * p12) + (koma_13 * p13)
            working_days = df_teacher['日付'].nunique()
            transport_total = working_days * trans
            final_salary = koma_salary + transport_total + allowance

            summary_list.append({
                "👨‍🏫 担当講師": teacher, "合計コマ数": total_koma, "授業給 (円)": int(koma_salary),
                "役職手当 (円)": int(allowance), "出勤日数": working_days, 
                "交通費合計 (円)": int(transport_total), "💰 最終支給額 (円)": int(final_salary)
            })

        if summary_list:
            df_summary = pd.DataFrame(summary_list)
            st.subheader(f"📊 {selected_month} の稼働・給与一覧")
            st.dataframe(df_summary, hide_index=True, use_container_width=True)

            st.divider()
            st.subheader("📄 給与明細PDFの一括作成")
            if st.button(f"📦 全員分の明細をZIPで作成する", use_container_width=True):
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    p_bar_zip = st.progress(0)
                    for j, row_data in enumerate(summary_list):
                        pdf_bytes = generate_payslip_pdf(row_data, selected_month)
                        file_name = f"給与明細_{selected_month}_{row_data['👨‍🏫 担当講師']}.pdf"
                        zip_file.writestr(file_name, pdf_bytes)
                        p_bar_zip.progress((j + 1) / len(summary_list))
                    p_bar_zip.empty()
                
                st.download_button(
                    label="📥 ZIPファイルをダウンロード",
                    data=zip_buffer.getvalue(),
                    file_name=f"{selected_month}_給与明細一括.zip",
                    mime="application/zip",
                    type="primary",
                    use_container_width=True
                )

            st.divider()
            st.subheader("📢 先生のページへ給与データを公開")
            if st.button(f"🚀 {selected_month} の給与を確定して公開する", use_container_width=True):
                with st.spinner("☁️ データを送信中...（通信状況により数秒かかります）"):
                    # 🌟 公開処理も自動リトライで保護
                    success = robust_api_call(publish_salary_data, selected_month, df_summary, fallback_value=False)
                    
                    if success is not False:
                        time.sleep(1)
                        st.success(f"✅ {selected_month} のデータを公開しました！")
                    else:
                        st.error("⚠️ 通信エラーにより公開に失敗しました。時間をおいて再度お試しください。")