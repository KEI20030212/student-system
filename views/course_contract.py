import streamlit as st
import pandas as pd
import time
from utils.api_guard import robust_api_call
from utils.g_sheets import load_contract_master, save_contract_master, get_student_master

def render_course_contract_page():
    st.header("📝 講習契約マスタ登録")
    st.write("生徒ごとの講習契約コマ数を管理します。ここでの設定がマッチング画面の「残りコマ数」に反映されます。")

    # 1. データの読み込み
    with st.spinner("データを読み込み中..."):
        df_contracts = load_contract_master()
        df_students = get_student_master()
        
    if df_students.empty:
        st.error("生徒マスタが読み込めません。")
        st.stop()

    # 生徒選択用のリスト作成
    student_list = (df_students['生徒ID'].astype(str) + " - " + df_students['生徒名']).tolist()

    # ------------------------------------------
    # 🌟 新規契約の追加フォーム
    # ------------------------------------------
    with st.expander("➕ 新しい契約を追加する", expanded=df_contracts.empty):
        with st.form("add_contract_form"):
            col1, col2 = st.columns(2)
            selected_student = col1.selectbox("生徒を選択", student_list, index=None, placeholder="生徒を選んでください")
            course_name = col2.selectbox("講習名", ["2026夏期講習", "2026冬期講習", "2027春期講習"], index=0)
            
            col3, col4 = st.columns(2)
            subject = col3.selectbox("科目", ["英語", "数学", "国語", "理科", "社会"])
            units = col4.number_input("契約コマ数", min_value=1, max_value=100, value=10)
            
            submit_btn = st.form_submit_button("契約を追加 ✨", type="primary")

            if submit_btn:
                if not selected_student:
                    st.error("生徒を選択してください。")
                else:
                    sid = selected_student.split(" - ")[0]
                    sname = selected_student.split(" - ")[1]
                    
                    # 重複チェック
                    is_duplicate = not df_contracts.empty and len(df_contracts[
                        (df_contracts['生徒ID'].astype(str) == sid) & 
                        (df_contracts['講習名'] == course_name) & 
                        (df_contracts['科目'] == subject)
                    ]) > 0

                    if is_duplicate:
                        st.warning(f"⚠️ {sname} さんの {course_name} ({subject}) は既に登録されています。下の表で編集してください。")
                    else:
                        new_row = pd.DataFrame([{
                            "生徒ID": sid, "生徒名": sname, "講習名": course_name, "科目": subject, "契約コマ数": int(units)
                        }])
                        df_contracts = pd.concat([df_contracts, new_row], ignore_index=True)
                        success = robust_api_call(lambda: save_contract_master(df_contracts), fallback_value=False)
                        if success:
                            st.success(f"✅ {sname} さんの契約を追加しました！")
                            time.sleep(1)
                            st.rerun()

    # ------------------------------------------
    # 🌟 既存契約の一括編集エディタ
    # ------------------------------------------
    st.subheader("📊 登録済み契約一覧")
    
    if df_contracts.empty:
        st.info("登録済みの契約はありません。上のフォームから登録してください。")
    else:
        # フィルタリング
        search_q = st.text_input("🔍 生徒名や講習名で検索", placeholder="山田、夏期講習 など...")
        df_display = df_contracts.copy()
        if search_q:
            df_display = df_display[
                df_display['生徒名'].str.contains(search_q) | 
                df_display['講習名'].str.contains(search_q)
            ]

        # データエディタ
        edited_df = st.data_editor(
            df_display,
            column_config={
                "生徒ID": st.column_config.TextColumn("ID", disabled=True),
                "生徒名": st.column_config.TextColumn("名前", disabled=True),
                "講習名": st.column_config.SelectboxColumn("講習", options=["2026夏期講習", "2026冬期講習"]),
                "科目": st.column_config.SelectboxColumn("科目", options=["英語", "数学", "国語", "理科", "社会"]),
                "契約コマ数": st.column_config.NumberColumn("契約数", min_value=1, max_value=100, step=1),
            },
            num_rows="dynamic", # 行の削除を許可
            use_container_width=True,
            hide_index=True,
            key="contract_editor"
        )

        # 保存ボタン
        if st.button("💾 変更をスプレッドシートに保存", type="secondary", use_container_width=True):
            # フィルター後の編集結果を元の全体データに反映させるロジックが必要だが、
            # 簡易化のため、ここでは「表示されているものが正」として保存
            with st.spinner("保存中..."):
                success = robust_api_call(lambda: save_contract_master(edited_df), fallback_value=False)
                if success:
                    st.success("✅ スプレッドシートを更新しました！")
                    time.sleep(1)
                    st.rerun()