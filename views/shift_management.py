import streamlit as st
import pandas as pd
import datetime
import time

from utils.api_guard import robust_api_call
# 🚨 コメントアウトを解除し、本物の関数を読み込みます！
from utils.g_sheets import save_shift_records, load_shift_records

# ==========================================
# 🌟 ダミーデータ・モックアップ用の設定
# (本来は生徒マスタや講師マスタから取得します)
# ==========================================
def get_mock_members(target_type):
    if target_type == "講師":
        return ["鈴木先生", "佐藤先生", "田中先生", "高橋先生"]
    else:
        return ["山田太郎", "佐藤花子", "鈴木一郎", "対馬次郎"]

# ==========================================

def render_shift_management_page():
    st.header("📅 講習シフト一括入力フォーム")
    st.write("講師と生徒の講習シフトを、1週間単位でエクセルのようにスマートに一括登録・更新できます🚀")

    # ------------------------------------------
    # 1. 対象（講師 or 生徒）とメンバーの選択
    # ------------------------------------------
    st.subheader("👤 1. 入力対象を選択")
    target_type = st.radio("入力を開始する対象を選んでください", ["講師", "生徒"], horizontal=True)
    
    col1, col2 = st.columns(2)
    
    # メンバー選択（マスタ連携想定）
    member_options = get_mock_members(target_type)
    selected_member = col1.selectbox(
        f"👨‍🏫 担当の{target_type}名を選択", 
        ["-- 選択してください --"] + member_options
    )
    
    if selected_member == "-- 選択してください --":
        st.info("対象のメンバーを選択すると、シフト入力表が表示されます。")
        st.stop()

    # ------------------------------------------
    # 2. 対象の「週」を選択（月曜日を基準にする）
    # ------------------------------------------
    today = datetime.date.today()
    start_of_week = today - datetime.timedelta(days=today.weekday()) 
    
    week_options = []
    for i in range(-1, 6): # 先週 〜 5週間先まで
        w_start = start_of_week + datetime.timedelta(weeks=i)
        w_end = w_start + datetime.timedelta(days=6)
        label = f"{w_start.strftime('%m/%d')} (月) 〜 {w_end.strftime('%m/%d')} (日)"
        week_options.append((w_start, label))
        
    selected_week_idx = col2.selectbox(
        "📅 対象の週を選択", 
        range(len(week_options)), 
        index=1, # デフォルトは「今週」
        format_func=lambda x: week_options[x][1]
    )
    target_start_date = week_options[selected_week_idx][0]

    st.divider()

    # ------------------------------------------
    # 3. 1週間分のシフト編集テーブル（心臓部）
    # ------------------------------------------
    st.subheader(f"📝 {selected_member} さんのシフト編集")
    st.caption("各コマのセルをクリックして「〇」または「×」を選択してください。空欄は未提出（×扱い）となります。")
    
    # 曜日定義
    days_of_week = ["月", "火", "水", "木", "金", "土", "日"]
    columns = ["日付", "曜日", "Aコマ", "Bコマ", "0コマ", "1コマ", "2コマ", "3コマ", "4コマ"]
    
    # 🚨 【本物のロジックを有効化】既存データをスプレッドシートから安全にロード
    with st.spinner("既存のシフトデータを読み込み中..."):
        df_existing = robust_api_call(
            lambda: load_shift_records(target_type, selected_member, target_start_date),
            fallback_value=pd.DataFrame()
        )
    
    # スプレッドシートにデータがまだ無い場合は、すべて空欄の7日分の初期データを作成
    if df_existing.empty:
        init_data = []
        for i in range(7):
            current_date = target_start_date + datetime.timedelta(days=i)
            init_data.append({
                "日付": current_date.strftime("%Y/%m/%d"),
                "曜日": days_of_week[i],
                "Aコマ": "", "Bコマ": "", "0コマ": "", "1コマ": "", "2コマ": "", "3コマ": "", "4コマ": ""
            })
        df_shift_base = pd.DataFrame(init_data)
    else:
        # 既存データがある場合は、表示に必要な列だけを順番通りに並び替える
        df_shift_base = df_existing[columns].copy()

    # UIのカラム設定
    status_options = ["", "〇", "×"]
    column_config = {
        "日付": st.column_config.TextColumn("📅 日付", disabled=True, width="medium"),
        "曜日": st.column_config.TextColumn("📆 曜日", disabled=True, width="small"),
        "Aコマ": st.column_config.SelectboxColumn("Aコマ", options=status_options, help="9:30 ~ 11:00", width="small"),
        "Bコマ": st.column_config.SelectboxColumn("Bコマ", options=status_options, help="11:10 ~ 12:40", width="small"),
        "0コマ": st.column_config.SelectboxColumn("0コマ", options=status_options, help="13:10 ~ 14:40", width="small"),
        "1コマ": st.column_config.SelectboxColumn("1コマ", options=status_options, help="14:50 ~ 16:20", width="small"),
        "2コマ": st.column_config.SelectboxColumn("2コマ", options=status_options, help="16:40 ~ 18:10", width="small"),
        "3コマ": st.column_config.SelectboxColumn("3コマ", options=status_options, help="18:20 ~ 19:50", width="small"),
        "4コマ": st.column_config.SelectboxColumn("4コマ", options=status_options, help="20:00 ~ 21:30", width="small"),
    }

    # データエディタのレンダリング
    edited_df = st.data_editor(
        df_shift_base,
        column_config=column_config,
        use_container_width=True,
        hide_index=True
    )

    # ------------------------------------------
    # 4. 保存処理
    # ------------------------------------------
    col_btn, _ = st.columns([1, 3])
    submit_btn = col_btn.button(f"💾 {selected_member} さんのシフトを保存", type="primary", use_container_width=True)
    
    if submit_btn:
        with st.spinner("スプレッドシートにシフトデータを書き込み中..."):
            
            # 🚨 【本物のロジックを有効化】編集されたデータを関数に渡して保存！
            success = robust_api_call(
                lambda: save_shift_records(target_type, selected_member, edited_df),
                fallback_value=False
            )
            
            if success:
                st.success(f"🎉 {selected_member} さんのシフト（{week_options[selected_week_idx][1]}）を正常に保存しました！")
                
                # 🚨 キャッシュをクリアして、次回開いたときに確実に最新データが読み込まれるようにする
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()  # 画面を再読み込みして保存結果を反映
            else:
                st.error("スプレッドシートへの保存に失敗しました。ネットワーク状況やシートの列名を確認してください。")