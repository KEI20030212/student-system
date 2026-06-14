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
        st.error("生徒マスタが読み込めません。スプレッドシートの生徒マスタにデータがあるか確認してください。")
        st.stop()

    # 🚨 【安全装置】スプレッドシートの列名が正しいかチェック
    if not df_contracts.empty:
        required_cols = ["講習名", "生徒ID", "生徒名", "科目", "契約コマ数"]
        missing_cols = [c for c in required_cols if c not in df_contracts.columns]
        
        if missing_cols:
            st.error(f"❌ 『設定_講習契約マスタ』シートに必要な列が足りません。")
            st.warning(f"不足している列: {missing_cols}")
            st.info("シートの1行目を「講習名, 生徒ID, 生徒名, 科目, 契約コマ数」の順に設定してください。")
            st.stop()
    else:
        # データが空の場合は初期カラムを持つ空のDataFrameを作成
        df_contracts = pd.DataFrame(columns=["講習名", "生徒ID", "生徒名", "科目", "契約コマ数"])

    # 生徒選択用のリスト作成
    student_list = (df_students['生徒ID'].astype(str) + " - " + df_students['生徒名']).tolist()

    # ------------------------------------------
    # 🌟 新規契約の追加フォーム
    # ------------------------------------------
    with st.expander("➕ 新しい契約を追加する", expanded=df_contracts.empty):
        with st.form("add_contract_form"):
            col1, col2 = st.columns(2)
            selected_student = col1.selectbox("生徒を選択", student_list, index=None, placeholder="生徒を選んでください")
            
            # 実運用向けに現在の年を自動取得して講習名を動的生成
            current_year = pd.Timestamp.now().year
            course_options = [f"{current_year}夏期講習", f"{current_year}冬期講習", f"{current_year+1}春期講習"]
            course_name = col2.selectbox("講習名", course_options, index=0)
            
            st.markdown("##### 📚 科目ごとの契約コマ数（※0コマの科目は登録されません）")
            # 5科目分の入力欄を横並びに配置
            sub_cols = st.columns(5)
            subjects = ["英語", "数学", "国語", "理科", "社会"]
            units_dict = {}
            
            for i, sub in enumerate(subjects):
                # 初期値を0に設定し、1以上の入力があった科目だけを登録対象にする
                units_dict[sub] = sub_cols[i].number_input(sub, min_value=0, max_value=100, value=0, step=1)
            
            submit_btn = st.form_submit_button("契約を一括追加 ✨", type="primary")

            if submit_btn:
                if not selected_student:
                    st.error("生徒を選択してください。")
                else:
                    sid = selected_student.split(" - ")[0]
                    sname = selected_student.split(" - ")[1]
                    
                    new_rows = []
                    skipped_subjects = []
                    
                    for sub, num in units_dict.items():
                        if num > 0:
                            # 既存の契約があるか重複チェック
                            is_duplicate = len(df_contracts[
                                (df_contracts['生徒ID'].astype(str) == sid) & 
                                (df_contracts['講習名'] == course_name) & 
                                (df_contracts['科目'] == sub)
                            ]) > 0

                            if is_duplicate:
                                skipped_subjects.append(sub)
                            else:
                                new_rows.append({
                                    "講習名": course_name, "生徒ID": sid, "生徒名": sname, "科目": sub, "契約コマ数": int(num)
                                })
                                
                    if skipped_subjects:
                        st.warning(f"⚠️ {sname}さんの {course_name} のうち、【 {', '.join(skipped_subjects)} 】は既に登録されているためスキップしました。（下の表から直接編集してください）")
                        
                    if new_rows:
                        # 複数科目分を一気にデータフレームに追加
                        df_contracts = pd.concat([df_contracts, pd.DataFrame(new_rows)], ignore_index=True)
                        success = robust_api_call(lambda: save_contract_master(df_contracts), fallback_value=False)
                        
                        if success:
                            st.success(f"✅ {sname} さんの契約（{len(new_rows)}科目）を追加しました！")
                            time.sleep(1.5)
                            st.rerun()
                    elif not skipped_subjects:
                        st.warning("⚠️ 追加する科目には1以上のコマ数を入力してください。")

    # ------------------------------------------
    # 🌟 既存契約の一括編集エディタ
    # ------------------------------------------
    st.subheader("📊 登録済み契約一覧")
    
    if df_contracts.empty:
        st.info("登録済みの契約はありません。上のフォームから登録してください。")
    else:
        search_q = st.text_input("🔍 生徒名や講習名で検索", placeholder="山田、夏期講習 など...")
        df_display = df_contracts.copy()
        if search_q:
            df_display = df_display[
                df_display['生徒名'].str.contains(search_q, na=False) | 
                df_display['講習名'].str.contains(search_q, na=False)
            ]

        edited_df = st.data_editor(
            df_display,
            column_config={
                "生徒ID": st.column_config.TextColumn("ID", disabled=True),
                "生徒名": st.column_config.TextColumn("名前", disabled=True),
                "講習名": st.column_config.SelectboxColumn("講習", options=course_options),
                "科目": st.column_config.SelectboxColumn("科目", options=["英語", "数学", "国語", "理科", "社会"]),
                "契約コマ数": st.column_config.NumberColumn("契約数", min_value=1, max_value=100, step=1),
            },
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key="contract_editor"
        )

        if st.button("💾 変更をスプレッドシートに保存", type="secondary", use_container_width=True):
            with st.spinner("保存中..."):
                success = robust_api_call(lambda: save_contract_master(edited_df), fallback_value=False)
                if success:
                    st.success("✅ スプレッドシートを更新しました！")
                    time.sleep(1)
                    st.rerun()