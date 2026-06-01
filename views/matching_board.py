import streamlit as st
import pandas as pd
import time
import datetime

# ==========================================
# 🌟 モックデータ＆ヘルパー関数（本来はg_sheets.pyから取得）
# ==========================================
def get_mock_student_shifts(student_name):
    """生徒の1週間分の希望シフト（〇・×）"""
    return pd.DataFrame([
        {"日付": "2026/08/03", "曜日": "月", "Aコマ": "〇", "Bコマ": "×", "0コマ": "〇", "1コマ": "〇", "2コマ": "×", "3コマ": "×", "4コマ": "×"},
        {"日付": "2026/08/04", "曜日": "火", "Aコマ": "×", "Bコマ": "×", "0コマ": "〇", "1コマ": "〇", "2コマ": "〇", "3コマ": "×", "4コマ": "×"},
        # ... 他の曜日（省略）
    ])

def get_mock_available_teachers(date, slot):
    """その日・そのコマに出勤しており、かつ1:3の枠がまだ埋まっていない講師のリスト"""
    # 実際はここで「講師シフト表」と「確定済み授業予定表」を突き合わせて算出します
    return ["鈴木先生", "佐藤先生", "田中先生"]

# ==========================================
# 🌟 マッチング画面のメインロジック
# ==========================================
def render_matching_page():
    st.header("🧩 スマート・コマ組みマッチング")
    st.write("生徒を選ぶと、空いているコマとマッチング可能な講師が自動提案されます。")

    col_target, col_week = st.columns(2)
    selected_student = col_target.selectbox("👤 対象の生徒を選択", ["-- 選択 --", "山田太郎", "佐藤花子"])
    selected_week = col_week.selectbox("📅 コマ組みする週を選択", ["2026/08/03 (月) 〜 2026/08/09 (日)"])

    if selected_student == "-- 選択 --":
        st.info("生徒を選択すると、マッチングボードが起動します。")
        st.stop()

    # ------------------------------------------
    # 1. 契約コマ数の進捗ダッシュボード
    # ------------------------------------------
    st.divider()
    st.subheader(f"📊 {selected_student} さんの受講状況（夏期講習）")
    
    # 💡 実際は「講習契約マスタ」と「授業予定表」から計算します
    total_units = 12
    scheduled_units = 8
    remaining_units = total_units - scheduled_units
    progress_pct = int((scheduled_units / total_units) * 100)

    met1, met2, met3 = st.columns(3)
    met1.metric("契約コマ数（英語）", f"{total_units} コマ")
    met2.metric("スケジュール確定済", f"{scheduled_units} コマ")
    met3.metric("未手配（残り）", f"{remaining_units} コマ", delta=f"-{remaining_units} 消化が必要", delta_color="inverse")

    st.progress(progress_pct / 100, text=f"スケジュール進捗: {progress_pct}%")

    # ------------------------------------------
    # 2. マッチング・マトリクス（心臓部）
    # ------------------------------------------
    st.divider()
    st.subheader("🗓️ マッチング・ボード")
    st.caption("生徒が「〇」を出しているコマにのみ、アサイン可能な講師のリストが表示されます。")

    df_student_shift = get_mock_student_shifts(selected_student)
    
    # 編集用データフレームの構築
    df_matching = df_student_shift.copy()
    
    # Streamlitのdata_editorの仕様上、列全体に同じ選択肢を設定する必要があります。
    # そこで、「その週に出勤している全講師」をドロップダウンの選択肢としてセットします。
    available_teachers = ["", "鈴木先生", "佐藤先生", "田中先生", "高橋先生", "伊藤先生"]

    # カラム設定を動的に生成
    column_config = {
        "日付": st.column_config.TextColumn("📅 日付", disabled=True),
        "曜日": st.column_config.TextColumn("📆 曜日", disabled=True),
    }

    slots = ["Aコマ", "Bコマ", "0コマ", "1コマ", "2コマ", "3コマ", "4コマ"]
    
    for slot in slots:
        # 生徒が「×」の箇所はエディタ上で入力できないようにマスクするなどの処理が本来は必要ですが、
        # ここではシンプルにSelectboxとして提供し、値がセットされたらマッチング成立とみなします。
        column_config[slot] = st.column_config.SelectboxColumn(
            slot,
            options=available_teachers,
            help="担当講師を選択してください",
            width="medium"
        )
        
        # 生徒が「×」を出しているセルは、初期値を "生徒NG" などの文字列にして視覚的に弾く
        df_matching.loc[df_matching[slot] == "×", slot] = "⛔ 生徒NG"
        df_matching.loc[df_matching[slot] == "〇", slot] = "" # 空欄（講師未定）にする

    # エクセルライクなUIの描画
    edited_df = st.data_editor(
        df_matching,
        column_config=column_config,
        use_container_width=True,
        hide_index=True
    )

    # ------------------------------------------
    # 3. マッチングの検証と保存
    # ------------------------------------------
    if st.button("💾 このスケジュールで確定して保存", type="primary", use_container_width=True):
        with st.spinner("講師の空き枠（1:3）や重複を検証中..."):
            time.sleep(1.5)
            
            # 【バリデーションのロジックイメージ】
            # 1. 選択された講師が、本当にその日そのコマに「〇」を出しているか？
            # 2. その講師の同コマの担当生徒数が「3人（1:3）」を超えていないか？
            # 3. 生徒の残りコマ数を超過して割り当てていないか？
            
            st.success("🎉 バリデーション完了！スケジュールが正常に保存されました。")
