#改良前
@st.cache_data(ttl=60)
def get_all_student_names():
    gc = get_gc_client()
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        ensure_global_sheets(sh)
        exclude = ["自習記録", "テキスト情報一覧", "設定_掲示板", "成績_定期テスト", "設定_小テスト一覧", "設定_生徒情報", "設定_座席表", "講師マスタ", "設定_アカウント", "給与公開用データ", "連絡_メッセージ", "小テスト記録", "学校課題管理", "請求管理", "料金マスタ", "固定費設定", "授業ログ統合"]
        return [ws.title for ws in sh.worksheets() if ws.title not in exclude]
    except:
        return []

def load_all_data(student_name):
    df = load_raw_data(student_name)
    if not df.empty and '終了ページ' in df.columns:
        df['ページ数'] = df['終了ページ'].astype(str).str.extract(r'(\d+)').astype(float)
    return df

@st.cache_data(ttl=3600)
def load_raw_data(student_name):
    gc = get_gc_client()
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        return pd.DataFrame(sh.worksheet(student_name).get_all_records())
    except:
        return pd.DataFrame()

@st.cache_data(ttl=600)
def get_all_student_grades():
    """生徒情報から学年データを取得する"""
    gc = get_gc_client()
    for attempt in range(5):
        try:
            sh = gc.open_by_key(SPREADSHEET_ID)
            ws = sh.worksheet("設定_生徒情報")
            df = pd.DataFrame(ws.get_all_records())
            return df
        except Exception:
            time.sleep(2)
    return pd.DataFrame()

def add_school_homework(student_name, subject, content, deadline, memo):
    """新しい課題を登録（APIエラー対策版）"""
    gc = get_gc_client()
    max_retries = 3
    new_row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        student_name,
        subject,
        content,
        deadline.strftime("%Y-%m-%d"),
        "未着手",
        memo
    ]

    for attempt in range(max_retries):
        try:
            sh = gc.open_by_key(SPREADSHEET_ID)
            ws = sh.worksheet("学校課題管理")
            ws.append_row(new_row)
            return True
        except Exception:
            time.sleep(2)
    return False

@st.cache_data(ttl=600)
def load_textbook_master():
    gc = get_gc_client()
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.worksheet("テキスト情報一覧")
        all_data = worksheet.get_all_values()
        master = {}
        for row in all_data[1:]:
            if len(row) >= 4:
                text_name = row[0]
                chap_match = re.search(r'\d+', row[1])
                if not chap_match: continue
                chap = int(chap_match.group())
                master.setdefault(text_name, {})[chap] = {"start": int(row[2]), "end": int(row[3])}
        return master
    except Exception as e:
        return {}

@st.cache_data(ttl=600)
def get_all_student_info_dict():
    """
    全員分の生徒情報を「1回のAPI通信」で一括取得し、
    {'生徒A': {データ}, '生徒B': {データ}} の辞書にする神関数
    """
    # ▼▼ ここは g_sheets.py の他の関数に合わせて接続コードを書いてください ▼▼
    gc = get_gc_client() 
    sh = gc.open_by_key(SPREADSHEET_ID) # ← ご自身の環境の変数名に合わせてください
    # ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲
    
    ws = sh.worksheet("設定_生徒情報")
    
    # 🌟 ここで全員分のデータを一括取得！（通信はここで1回だけ）
    records = ws.get_all_records() 
    
    info_dict = {}
    for row in records:
        # スプレッドシートの列名（生徒名/氏名/名前など）に対応
        name = row.get('生徒名') or row.get('氏名') or row.get('名前')
        if name:
            info_dict[name] = row
            
    return info_dict  

@st.cache_data(ttl=3600)
def load_entire_log_data():
    student_names = get_all_student_names()
    all_data_list = []
    
    for s_name in student_names:
        df = load_raw_data(s_name) 
        if not df.empty:
            if '生徒名' not in df.columns:
                df.insert(0, '生徒名', s_name)
            all_data_list.append(df)
            
    if all_data_list:
        return pd.concat(all_data_list, ignore_index=True)
    return pd.DataFrame()

def load_daily_class_record(student_name, target_date_str):
    """
    生徒個別のシートから、指定された日付の授業記録を1行分（辞書型）で返す関数。
    target_date_str は "YYYY/MM/DD" の形式を想定。
    """
    try:
        gc = get_gc_client() 
        sh = gc.open_by_key(SPREADSHEET_ID)
        
        df = pd.DataFrame(sh.worksheet(student_name).get_all_records())
        
        if df.empty:
            return {}

        # 「日時」列を比較しやすいように "YYYY/MM/DD" フォーマットに変換
        # （時間にばらつきがあっても日付だけでマッチングできるようにします）
        df['日時_Date'] = pd.to_datetime(df['日時'], errors='coerce').dt.strftime("%Y/%m/%d")
        
        # ターゲット日付も同じ形式に揃える
        target_formatted = pd.to_datetime(target_date_str).strftime("%Y/%m/%d")
        
        # 日付が一致する行を抽出
        daily_data = df[df['日時_Date'] == target_formatted]
        
        if not daily_data.empty:
            # 同じ日に複数コマあった場合、最新のもの（一番下の行）を取得する
            return daily_data.iloc[-1].to_dict()
        else:
            return {}
            
    except Exception as e:
        print(f"授業記録の取得エラー: {e}")
        return {}

def overwrite_spreadsheet(name, edited_df):
    st.toast("💾 スプレッドシートを更新中...")
    try:
        gc = get_gc_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.worksheet(name)
        worksheet.clear()
        edited_df = edited_df.fillna("")
        data_to_save = [edited_df.columns.tolist()] + edited_df.values.tolist()
        worksheet.update(data_to_save)
        st.success("✅ 保存しました！")
    except Exception as e:
        st.error(f"❌ 保存失敗: {e}")

#views/multi_input.py
# ==========================================
    # 📝 自習記録の入力画面（複数日・休憩・ポイント計算対応＆絶対エラー防護版）
    # ==========================================
    elif record_type == "📝 自習":
        with st.container(border=True):
            st.write("📚 **自習記録の入力（一括登録モード）**")
            
            ss_options = ["🆕 新規登録"] + student_options
            ss_name = st.selectbox("👤 生徒を選択", ss_options, index=None, placeholder="生徒を選択", key="ss_name")
            
            if ss_name == "🆕 新規登録": 
                ss_name = st.text_input("新しい生徒の名前", key="ss_new_name")
            
            if ss_name:
                num_days = st.number_input("🗓️ 登録する日数", min_value=1, max_value=14, value=1, key="ss_num_days")
                st.divider()
                
                ss_records = []
                total_earned_points = 0
                
                for d in range(int(num_days)):
                    st.write(f"**【 {d+1}日目の記録 】**")
                    col_d, col_s, col_e, col_b = st.columns([1.5, 1.2, 1.2, 1])
                    
                    default_date = datetime.date.today() - datetime.timedelta(days=d)
                    ss_date = col_d.date_input("📅 日付", default_date, key=f"d_{d}")
                    
                    s_time = col_s.time_input("🛫 開始", datetime.time(17, 0), key=f"s_{d}")
                    e_time = col_e.time_input("🛬 終了", datetime.time(19, 0), key=f"e_{d}")
                    b_min = col_b.number_input("☕ 休憩(分)", min_value=0, value=0, step=5, key=f"b_{d}")
                    
                    # 時間計算ロジック
                    start_dt = datetime.datetime.combine(ss_date, s_time)
                    end_dt = datetime.datetime.combine(ss_date, e_time)
                    diff_min = (end_dt - start_dt).seconds // 60
                    if end_dt < start_dt: # 日を跨ぐ場合（念のため）
                        diff_min = 0
                        
                    actual_min = max(0, diff_min - b_min)
                    pts = int(actual_min // 30) # 30分につき1pt
                    total_earned_points += pts
                    
                    st.caption(f"⏱️ 滞在: {diff_min}分 ／ 🔥 実質勉強時間: **{actual_min}分** （獲得: {pts}pt）")
                    ss_memo = st.text_area("📖 学習内容（テキスト名など）", height=70, key=f"m_{d}")
                    
                    ss_records.append({
                        "date": ss_date, "start": s_time, "end": e_time, 
                        "break": b_min, "actual": actual_min, "content": ss_memo, "pts": pts
                    })
                    st.divider()
                
                if st.button(f"💾 {num_days}日分のデータを安全に保存する", type="primary", use_container_width=True):
                    with st.status("Googleスプレッドシートに送信中...", expanded=True) as status:
                        success_count = 0
                        for idx, rec in enumerate(ss_records):
                            # 🛡️ 堅牢化: APIエラー対策のラッパーを使用
                            ok, msg = robust_api_call(
                                save_self_study_record,
                                rec["date"], ss_name, rec["start"], rec["end"], 
                                rec["break"], rec["actual"], rec["content"], rec["pts"]
                            )
                            if ok:
                                success_count += 1
                                # 🛡️ APIエラー対策: 1件ごとに2秒待機してGoogleを怒らせないようにする
                                if idx < len(ss_records) - 1:
                                    time.sleep(2)
                            else:
                                st.error(f"❌ {idx+1}件目でエラー: {msg}")
                                break # 1つ失敗したら止める
                                
                        if success_count == len(ss_records):
                            status.update(label="すべて正常に保存されました！", state="complete", expanded=False)
                            st.success(f"✅ {ss_name}さんの{success_count}日分の記録を保存！ 合計 {total_earned_points}pt 獲得！")
                            st.balloons()
                            time.sleep(2)
                            # リセット処理
                            for k in list(st.session_state.keys()):
                                if k.startswith(("d_","s_","e_","b_","m_","ss_")): del st.session_state[k]
                            st.rerun()