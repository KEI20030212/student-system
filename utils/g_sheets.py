import streamlit as st
import json
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import datetime
import re
import math
import time
import streamlit.components.v1 as components
import base64
import altair as alt # 座標グラフを描くための魔法の絵の具

# --------------------------------------------------
# ⚙️ 設定（デザインとファイル連携）
# --------------------------------------------------
SPREADSHEET_ID = '1tnhK-rvf_cSXmuY9REkD_cK6Wg4XP7alc1UHTpSRrv4'
@st.cache_resource
def get_gc_client():
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    # ❌ 修正前：PCの中のファイルを探しに行く
    # credentials = Credentials.from_service_account_file('secret.json', scopes=scopes)
    
    # ⭕ 修正後：Streamlitの秘密の金庫から鍵のデータを取り出して読み込む！
    secret_dict = json.loads(st.secrets["gcp_service_account_json"])
    credentials = Credentials.from_service_account_info(secret_dict, scopes=scopes)
    return gspread.authorize(credentials)

@st.cache_data(ttl=60)
def get_all_student_names():
    gc = get_gc_client()
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        ensure_global_sheets(sh)
        exclude = ["自習記録", "テキスト情報一覧", "設定_掲示板", "成績_定期テスト", "設定_小テスト一覧", "設定_生徒情報", "設定_座席表", "講師マスタ"]
        return [ws.title for ws in sh.worksheets() if ws.title not in exclude]
    except:
        return []
@st.cache_data(ttl=60)
def get_student_info(name):
    gc = get_gc_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("設定_生徒情報")
    records = ws.get_all_records()
    for r in records:
        if r.get('生徒名') == name:
            return r
    return {}
def load_seating_data():
    """スプレッドシートから最新の座席情報を取得する"""
    gc = get_gc_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    try:
        ws = sh.worksheet("設定_座席表")
    except:
        ws = sh.add_worksheet(title="設定_座席表", rows="20", cols="5")
        ws.append_row(["ブース", "生徒名", "状態"])
        for i in range(1, 7):
            ws.append_row([f"ブース{i}", "-- 空席 --", "出席"])
            
    records = ws.get_all_records()
    seating = {}
    for r in records:
        seating[str(r.get("ブース", ""))] = {
            "生徒名": str(r.get("生徒名", "-- 空席 --")),
            "状態": str(r.get("状態", "出席"))
        }
    
    if not seating:
        return {f"ブース{i}": {"生徒名": "-- 空席 --", "状態": "出席"} for i in range(1, 7)}
        
    return seating
def save_seating_data(seating_dict):
    """座席情報をスプレッドシートに上書き保存する"""
    gc = get_gc_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    try:
        ws = sh.worksheet("設定_座席表")
    except:
        ws = sh.add_worksheet(title="設定_座席表", rows="20", cols="5")
        
    ws.clear() 
    
    data_to_append = [["ブース", "生徒名", "状態"]]
    for booth, info in seating_dict.items():
        data_to_append.append([booth, info["生徒名"], info["状態"]])
        
    for row in data_to_append:
        ws.append_row(row)
def get_last_page_from_sheet(name):
    df = load_all_data(name)
    if not df.empty and 'ページ数' in df.columns:
        return int(df['ページ数'].iloc[-1])
    return 0
def save_to_spreadsheet(name, subject, text_name, advanced_p, quiz_records, date, teacher_name="未入力", class_type="1:1", attendance="出席（通常）", class_slot="-", advice="-", parent_msg="-", next_handover="-", assigned_p=0, completed_p=0, motivation_rank=0, next_hw_text="-", next_hw_pages=0):
    gc = get_gc_client()
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        existing_sheets = [ws.title for ws in sh.worksheets()]
        
        # 🌟 追加：昔の列名に加えて、新メンバー5人を追加します！
        new_columns = ["宿題", "担当講師", "授業形態", "出欠", "授業コマ", "アドバイス", "保護者への連絡", "次回への引継ぎ", "出した宿題P", "やった宿題P", "やる気ランク", "次回の宿題テキスト", "次回の宿題ページ数"]
        
        if name in existing_sheets:
            worksheet = sh.worksheet(name)
            header = worksheet.row_values(1)
            # 先生の神コード！足りない列名があれば自動で右に追加
            for col_name in new_columns:
                if col_name not in header:
                    worksheet.update_cell(1, len(header) + 1, col_name)
                    header.append(col_name)
        else:
            worksheet = sh.add_worksheet(title=name, rows="100", cols="20")
            # 新しい生徒の時のヘッダーにも、右端に新メンバーを追加！
            header = ["日時", "名前", "科目", "テキスト", "終了ページ", "単元", "点数", "宿題", "担当講師", "授業形態", "出欠", "授業コマ", "アドバイス", "保護者への連絡", "次回への引継ぎ", "出した宿題P", "やった宿題P", "やる気ランク", "次回の宿題テキスト", "次回の宿題ページ数"]
            worksheet.append_row(header)
        
        date_str = date.strftime("%Y/%m/%d")
        
        # 🚨 超重要ポイント！
        # 列がズレないように、昔「宿題 (hw_status)」が入っていた8番目の場所にはダミーの "-" を入れます！
        if not quiz_records:
            worksheet.append_row([date_str, name, subject, text_name, advanced_p, "-", "-", "-", teacher_name, class_type, attendance, class_slot, advice, parent_msg, next_handover, assigned_p, completed_p, motivation_rank, next_hw_text, next_hw_pages])
        else:
            for q in quiz_records:
                worksheet.append_row([date_str, name, subject, text_name, advanced_p, f"第{q['unit']}章", q['score'], "-", teacher_name, class_type, attendance, class_slot, advice, parent_msg, next_handover, assigned_p, completed_p, motivation_rank, next_hw_text, next_hw_pages])
        return True
    except Exception as e:
        print(f"スプレッドシート保存エラー: {e}") # 万が一のエラー時に原因をターミナルに出す親切設計
        return False
import pandas as pd
import datetime

def update_student_homework_rate(name):
    from utils.calc_logic import calculate_quiz_points, calculate_motivation_rank
    
    # 生徒の全データを取得
    df = load_all_data(name)
    if df.empty: return
    
    # ==========================================
    # ⚠️ 先生へ：以下の3つの変数名（''の中身）を、
    # 実際のスプレッドシートの「1行目（見出し）」の文字とピッタリ合わせてください！
    # ==========================================
    date_col = '日付'             # 例: '日付', '授業日' など
    assigned_col = '出した宿題P'      # 例: '指示ページ数', '宿題出したP' など
    completed_col = 'やった宿題P' # 例: '実施ページ数', '宿題やってきたP' など
    score_col = '点数'            # 例: '小テスト点数', '点数' など

    # 日付列がない場合は計算できないのでストップ
    if date_col not in df.columns:
        return

    # 1. 「今月」のデータだけに絞り込む
    # 日付データをPandasが計算しやすい形式に変換
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    
    today = datetime.date.today()
    current_month = today.month
    current_year = today.year

    # 今月＆今年のデータだけを抽出
    df_this_month = df[(df[date_col].dt.month == current_month) & (df[date_col].dt.year == current_year)]

    if df_this_month.empty:
        return

    # 2. 今月の「宿題ページ数」の合計を出す
    total_assigned = 0
    total_completed = 0

    if assigned_col in df_this_month.columns and completed_col in df_this_month.columns:
        # 空欄や「-」などの文字を無視して、数字だけを合計する
        total_assigned = pd.to_numeric(df_this_month[assigned_col], errors='coerce').fillna(0).sum()
        total_completed = pd.to_numeric(df_this_month[completed_col], errors='coerce').fillna(0).sum()

    # 3. 宿題履行率の計算 (0除算を防止しつつ、最大100%でストップさせる)
    if total_assigned > 0:
        hw_rate = (total_completed / total_assigned) * 100
        if hw_rate > 100.0:
            hw_rate = 100.0
    else:
        hw_rate = 0.0

    # 83.3333... のようになるので、小数点第1位で丸める
    hw_rate = round(hw_rate, 1)

    # 4. 今月の小テストの合計ポイントを計算
    info = get_student_info(name)
    total_points = 0
    if score_col in df_this_month.columns:
        scores = pd.to_numeric(df_this_month[score_col], errors='coerce').dropna()
        for s in scores:
            total_points += calculate_quiz_points(s)
            
    # 5. 新しいやる気ランクを算出
    new_motivation = calculate_motivation_rank(hw_rate, total_points)
    
    # 6. 生徒マスターを更新
    update_student_info(
        name, 
        info.get('学年', ''), info.get('学校名', ''), info.get('志望校・目的', ''), info.get('受講科目', ''),
        int(info.get('能力', 3)), new_motivation, int(info.get('内申点', 3)), float(info.get('最新偏差値', 50.0)), hw_rate
    )
def save_test_score(date, name, test_type, eng, math_score, jpn, sci, soc, 
                    dev_eng=None, dev_math=None, dev_jpn=None, dev_sci=None, dev_soc=None, 
                    dev_3=None, dev_5=None, 
                    pe=None, tech=None, home=None, mus=None, is_naishin=False):
    gc = get_gc_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("成績_定期テスト")
    
    header = ws.row_values(1)
    
    required_cols = [
        '偏差値_英語', '偏差値_数学', '偏差値_国語', '偏差値_理科', '偏差値_社会', 
        '英語 偏差値', '数学 偏差値', '国語 偏差値', '理科 偏差値', '社会 偏差値', 
        '偏差値_3科', '偏差値_5科', '保体', '技術', '家庭', '音楽', '9科総合',
        '英語 内申', '数学 内申', '国語 内申', '理科 内申', '社会 内申',
        '保体 内申', '技術 内申', '家庭 内申', '音楽 内申'
    ]
    missing_cols = [col for col in required_cols if col not in header]
    
    if missing_cols:
        if len(header) + len(missing_cols) > ws.col_count:
            ws.add_cols(len(missing_cols) + 5)
        for col_name in missing_cols:
            ws.update_cell(1, len(header) + 1, col_name)
            header.append(col_name)

    row_dict = {
        '日時': date.strftime("%Y/%m/%d"), '生徒名': name, 'テスト種別': test_type,
    }

    if is_naishin:
        row_dict.update({
            '英語 内申': eng if eng is not None else "-",
            '数学 内申': math_score if math_score is not None else "-",
            '国語 内申': jpn if jpn is not None else "-",
            '理科 内申': sci if sci is not None else "-",
            '社会 内申': soc if soc is not None else "-",
            '保体 内申': pe if pe is not None else "-",
            '技術 内申': tech if tech is not None else "-",
            '家庭 内申': home if home is not None else "-",
            '音楽 内申': mus if mus is not None else "-"
        })
    else:
        total_5 = sum([x for x in [eng, math_score, jpn, sci, soc] if x is not None])
        total_9 = total_5 + sum([x for x in [pe, tech, home, mus] if x is not None]) if test_type == "期末テスト" else "-"

        row_dict.update({
            '英語': eng if eng is not None else "-", '数学': math_score if math_score is not None else "-",
            '国語': jpn if jpn is not None else "-", '理科': sci if sci is not None else "-",
            '社会': soc if soc is not None else "-", '総合': total_5, 
            
            '偏差値_英語': dev_eng if dev_eng is not None else "-",
            '偏差値_数学': dev_math if dev_math is not None else "-",
            '偏差値_国語': dev_jpn if dev_jpn is not None else "-",
            '偏差値_理科': dev_sci if dev_sci is not None else "-",
            '偏差値_社会': dev_soc if dev_soc is not None else "-",
            
            '英語 偏差値': dev_eng if dev_eng is not None else "-",
            '数学 偏差値': dev_math if dev_math is not None else "-",
            '国語 偏差値': dev_jpn if dev_jpn is not None else "-",
            '理科 偏差値': dev_sci if dev_sci is not None else "-",
            '社会 偏差値': dev_soc if dev_soc is not None else "-",
            
            '偏差値_3科': dev_3 if dev_3 is not None else "-",
            '偏差値_5科': dev_5 if dev_5 is not None else "-",
            '保体': pe if pe is not None else "-", '技術': tech if tech is not None else "-",
            '家庭': home if home is not None else "-", '音楽': mus if mus is not None else "-",
            '9科総合': total_9
        })
    
    row_to_append = [row_dict.get(col, "-") for col in header]
    ws.append_row(row_to_append)
    st.cache_data.clear()
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
def delete_specific_log(name, date_str, subject):
    """間違えて入力した授業記録を1件削除する（生徒別シート対応版）"""
    gc = get_gc_client()
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet(name) 
        records = ws.get_all_values()
        
        target_date_obj = pd.to_datetime(date_str).date()
        
        for i in range(len(records)-1, 0, -1):
            row = records[i]
            if len(row) < 2: 
                continue 
                
            try:
                row_date_obj = pd.to_datetime(row[0]).date()
            except:
                continue 
                
            if row_date_obj == target_date_obj and subject in row:
                ws.delete_rows(i + 1)
                st.cache_data.clear() 
                return True
                
        return False
    except Exception as e:
        print(f"削除エラー: {e}")
        return False
@st.cache_data(ttl=60)
def get_quiz_maker_sheets():
    gc = get_gc_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("設定_小テスト一覧")
    records = ws.get_all_records()
    return {str(row['テスト名']): str(row['スプレッドシートID']) for row in records if row['テスト名']}
def add_quiz_maker_sheet(test_name, sheet_id):
    gc = get_gc_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("設定_小テスト一覧")
    ws.append_row([test_name, sheet_id])
    st.cache_data.clear()
def delete_quiz_maker_sheet(test_name):
    gc = get_gc_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("設定_小テスト一覧")
    cell = ws.find(test_name, in_column=1)
    if cell: ws.delete_rows(cell.row)
    st.cache_data.clear()
def update_student_info(name, grade, school, target, subjects, ability, motivation, naishin, dev_score, hw_rate):
    gc = get_gc_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("設定_生徒情報")
    
    header = ws.row_values(1)
    required_cols = ['内申点', '最新偏差値', '宿題履行率']
    missing_cols = [col for col in required_cols if col not in header]
    
    if missing_cols:
        if len(header) + len(missing_cols) > ws.col_count:
            ws.add_cols(len(missing_cols) + 3) 
        for col in missing_cols:
            ws.update_cell(1, len(header) + 1, col)
            header.append(col)

    cell = ws.find(name, in_column=1)
    if cell:
        ws.update_cell(cell.row, 2, grade)
        ws.update_cell(cell.row, 3, school)
        ws.update_cell(cell.row, 4, target)
        ws.update_cell(cell.row, 5, subjects)
        ws.update_cell(cell.row, 6, ability)
        ws.update_cell(cell.row, 7, motivation)
        ws.update_cell(cell.row, header.index('内申点') + 1, naishin)
        ws.update_cell(cell.row, header.index('最新偏差値') + 1, dev_score)
        ws.update_cell(cell.row, header.index('宿題履行率') + 1, hw_rate)
    else:
        row_dict = {
            header[0]: name, header[1]: grade, header[2]: school, 
            header[3]: target, header[4]: subjects, header[5]: ability, header[6]: motivation,
            '内申点': naishin, '最新偏差値': dev_score, '宿題履行率': hw_rate
        }
        row_to_append = [row_dict.get(col, "") for col in header]
        ws.append_row(row_to_append)
    st.cache_data.clear()
def ensure_global_sheets(sh):
    titles = [ws.title for ws in sh.worksheets()]
    if "設定_掲示板" not in titles:
        ws = sh.add_worksheet(title="設定_掲示板", rows="10", cols="2")
        ws.update_cell(1, 1, "ここに先生たちへの連絡事項を入力してください。")
    if "成績_定期テスト" not in titles:
        ws = sh.add_worksheet(title="成績_定期テスト", rows="1000", cols="15")
        ws.append_row(['日時', '生徒名', 'テスト種別', '英語', '数学', '国語', '理科', '社会', '総合', '偏差値', '保体', '技術', '家庭', '音楽', '9科総合'])
    if "設定_小テスト一覧" not in titles:
        ws = sh.add_worksheet(title="設定_小テスト一覧", rows="100", cols="2")
        ws.append_row(['テスト名', 'スプレッドシートID'])
    if "設定_生徒情報" not in titles:
        ws = sh.add_worksheet(title="設定_生徒情報", rows="100", cols="7")
        ws.append_row(['生徒名', '学年', '学校名', '志望校・目的', '受講科目', '能力', 'やる気'])
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
@st.cache_data(ttl=60)
def load_test_scores():
    gc = get_gc_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("成績_定期テスト")
    return pd.DataFrame(ws.get_all_records())
@st.cache_data(ttl=120)
def load_board_message():
    """掲示板のメッセージを取得する"""
    gc = get_gc_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    try:
        ws = sh.worksheet("設定_掲示板")
    except:
        ws = sh.add_worksheet(title="設定_掲示板", rows="10", cols="2")
        ws.update_cell(1, 1, "メッセージ")
        ws.update_cell(2, 1, "本日の連絡事項はありません。")
    
    val = ws.cell(2, 1).value
    return val if val else "本日の連絡事項はありません。"
def save_board_message(message):
    """掲示板のメッセージを保存する"""
    gc = get_gc_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    try:
        ws = sh.worksheet("設定_掲示板")
    except:
        ws = sh.add_worksheet(title="設定_掲示板", rows="10", cols="2")
        ws.update_cell(1, 1, "メッセージ")
    ws.update_cell(2, 1, message)
    st.cache_data.clear()
# ==========================================
# 📝 自習記録を保存する機能
# ==========================================
def save_self_study_record(date, name, start_time, end_time, break_time, actual_minutes):
    """自習の記録を「自習記録」シートに保存する"""
    try:
        # 👇👇 🚨 鍵を取り付けました！！ 🚨 👇👇
        gc = get_gc_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        
        # 「自習記録」という名前のシートを開く
        worksheet = sh.worksheet("自習記録")
        
        # 保存するデータのリストを作る
        row_data = [
            str(date),          # 日付
            name,               # 生徒名
            str(start_time),    # 開始時間
            str(end_time),      # 終了時間
            break_time,         # 休憩時間
            actual_minutes      # 自習時間(分)
        ]
        
        # スプレッドシートの空いている一番下の行に追記！
        worksheet.append_row(row_data)
        return True, "成功"  # 👈 成功したよ！と報告
    except Exception as e:
        print(f"自習記録の保存エラー: {e}")
        return False, str(e)

def load_self_study_data():
    """自習記録シートから全データを取得してシステム用の表（データフレーム）にして返す"""
    try:
        # 👇👇 🚨 ここにも鍵を取り付けました！！ 🚨 👇👇
        gc = get_gc_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        
        worksheet = sh.worksheet("自習記録")
        # 1行目が見出し（日付、生徒名…）になっている前提で全データを取得
        data = worksheet.get_all_records()
        import pandas as pd
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        print(f"自習記録の読み込みエラー: {e}")
        import pandas as pd
        return pd.DataFrame()

# ==========================================
# 📚 テキストマスタ（一覧）を取得する機能
# ==========================================
def get_textbook_master():
    import streamlit as st  # 画面にエラーを出すための魔法
    try:
        # 👇👇 🚨 ここにも鍵を取り付けました！！ 🚨 👇👇
        gc = get_gc_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        
        # 正しいシート名を指定
        worksheet = sh.worksheet("テキスト情報一覧") 
        records = worksheet.get_all_records()
        
        # 🚨 【透視メガネ】もし列の名前がズレていたら画面に犯人を映し出す！
        if len(records) > 0:
            keys = list(records[0].keys())
            if "テキスト" not in keys or "章" not in keys:
                st.error(f"🚨 スプレッドシートの1行目の名前がズレています！今の名前: {keys}")
        
        master_dict = {}
        for row in records:
            # 空白が入っていても安全に読み取る魔法
            text_name = str(row.get("テキスト", "")).strip()
            chap = str(row.get("章", "")).strip()
            
            if text_name and chap:
                if text_name not in master_dict:
                    master_dict[text_name] = []
                master_dict[text_name].append(chap)
                
        return master_dict
        
    except Exception as e:
        # 🚨 【透視メガネ】裏側でエラーが起きたら、その理由を画面に叫ぶ！
        st.error(f"🚨 マスタ取得の裏側でエラー発生: {e}")
        return {}
def get_last_handover(name, subject):
    """
    指定された生徒のシートから、特定の科目の「最新の引継ぎ事項」を抜き出す関数
    """
    gc = get_gc_client()
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        existing_sheets = [ws.title for ws in sh.worksheets()]
        
        if name not in existing_sheets:
            return "（初回授業のため、前回の記録はありません）"
            
        worksheet = sh.worksheet(name)
        all_data = worksheet.get_all_values() # 全データを取得
        
        if len(all_data) <= 1:
            return "（記録がまだありません）"
            
        # ヘッダーから「科目」と「次回への引継ぎ」が何列目にあるか探す
        header = all_data[0]
        try:
            sub_idx = header.index("科目")
            note_idx = header.index("次回への引継ぎ")
        except ValueError:
            return "（シートの項目が正しく設定されていません）"

        # 下の行（最新）から順番に見て、同じ科目のデータを探す
        for row in reversed(all_data[1:]):
            if row[sub_idx] == subject:
                last_note = row[note_idx]
                return last_note if last_note and last_note != "-" else "（前回の引継ぎ事項は空欄でした）"
        
        return f"（{subject} の過去の記録は見つかりませんでした）"

    except Exception as e:
        return f"（データ取得エラー: {e}）"
def add_new_textbook(new_name):
    """
    アプリから新規テキストを登録し、自動で五十音順（A列基準）に並べ替える魔法！
    """
    import streamlit as st
    gc = get_gc_client()
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.worksheet("テキスト情報一覧")
        
        # 先生のシートは「テキスト」と「章」の2列構成なので、
        # 新規登録時はとりあえず章に「-」を入れて追加します
        worksheet.append_row([new_name, "-"])
        
        # 🌟 ここが自動並べ替えの魔法！
        # 1行目（ヘッダー）は残したまま、2行目以降を1列目（テキスト名）の昇順でソートします
        worksheet.sort((1, 'asc'), range='A2:B1000')
        return True
    except Exception as e:
        st.error(f"🚨 新規テキストの裏側でエラー発生: {e}")
        return False

def get_last_homework_info(name, subject):
    """
    前回の『次回の宿題テキスト』と『ページ数（範囲）』を探し出す関数！
    """
    gc = get_gc_client()
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        existing_sheets = [ws.title for ws in sh.worksheets()]
        if name not in existing_sheets:
            return "なし", "-"  # 🌟 0 から "-" に変更

        ws = sh.worksheet(name)
        all_data = ws.get_all_values()
        if len(all_data) <= 1:
            return "なし", "-"  # 🌟 ここも
            
        header = all_data[0]
        
        # 新しい項目がどこにあるか探す
        try:
            sub_idx = header.index("科目")
            hw_text_idx = header.index("次回の宿題テキスト") 
            hw_pages_idx = header.index("次回の宿題ページ数")
        except ValueError:
            # まだ一度も宿題が出されていなくて列が無い場合は「なし」を返す
            return "なし", "-"  # 🌟 ここも

        # 下（最新）から順番に見て、同じ科目のデータを探す
        for row in reversed(all_data[1:]):
            # 行のデータがしっかり埋まっていて、科目が一致するかチェック
            if len(row) > max(sub_idx, hw_text_idx, hw_pages_idx) and row[sub_idx] == subject:
                text_name = row[hw_text_idx]
                pages = row[hw_pages_idx]
                # 🌟 データがあればそのまま（15でも P.10〜20 でも）返し、空っぽなら "-" を返す
                return text_name if text_name and text_name != "-" else "なし", pages if pages else "-"
                
        return "なし", "-"
    except Exception as e:
        return "なし", "-"

        # utils/g_sheets.py に追加

def load_instructor_master():
    """
    スプレッドシートの「講師マスタ」シートのデータを読み込む
    """
    try:
        # load_raw_data に "講師マスタ" というシート名を入れて呼び出すだけ！
        df = load_raw_data("講師マスタ")
        return df
    except Exception as e:
        print(f"講師マスタ読み込みエラー: {e}")
        import pandas as pd
        return pd.DataFrame() # エラーの時は空の表を返す

def update_instructor_master(df_updated):
    """
    画面上で編集されたデータフレームを「講師マスタ」シートに全体上書き保存する
    """
    try:
        gc = get_gc_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet("講師マスタ")
        
        # 1. 今シートにある古いデータを一旦まっさらにクリアする
        ws.clear()
        
        # 2. DataFrameをスプレッドシートに書き込める形（リストのリスト）に変換する
        # （1行目にヘッダー、2行目以降にデータが入る形になります）
        data_to_write = [df_updated.columns.tolist()] + df_updated.values.tolist()
        
        # 3. A1セルを起点にして、新しいデータを一気にドーンと書き込む
        # ※もしここでエラーが出る場合は、 gspreadのバージョンに合わせて ws.update('A1', data_to_write) に変更してみてください。
        ws.update(data_to_write, 'A1') 
        
        # 4. Streamlitのキャッシュをクリアして、次回から最新状態が読み込まれるようにする
        import streamlit as st
        st.cache_data.clear()
        
    except Exception as e:
        print(f"講師マスタ更新エラー: {e}")

def get_all_teacher_names():
    """講師マスタから講師名のリストを取得して五十音順にする"""
    gc = get_gc_client() # 👈 先生の環境に合わせた接続！
    try:
        sh = gc.open_by_key(SPREADSHEET_ID) # 👈 IDで開く！
        
        # ⚠️ スプレッドシート側のシート名が「講師マスタ」であることを確認してください。
        # (もし「設定_講師一覧」など別の名前で作っている場合は、ここを変更します)
        sheet = sh.worksheet("講師マスタ")
        
        names = sheet.col_values(1)[1:] # 1行目の見出しを飛ばしてA列を取得
        names = sorted([name.strip() for name in names if name.strip()])
        return names
        
    except Exception as e:
        import streamlit as st
        st.error(f"🚨 講師マスタの取得に失敗しました！原因: {e}")
        return []

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