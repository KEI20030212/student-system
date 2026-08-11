import streamlit as st
import pandas as pd
import datetime
import io
import os
import urllib.request
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

from utils.g_sheets import get_all_logs, load_quiz_records, get_student_master
from utils.api_guard import robust_api_call

# ==========================================
# 🌟 日本語文字化けを防ぐ最新のプロ仕様関数（ブロック回避版）
# ==========================================
@st.cache_resource
def setup_japanese_font():
    font_path = "BIZUDGothic-Regular.ttf"
    
    # サーバーにフォントファイルが無ければダウンロード
    if not os.path.exists(font_path):
        # 🌟 変更点1: 教育現場のレポートに最適な美しいフォント（BIZ UDゴシック）
        url = "https://raw.githubusercontent.com/googlefonts/morisawa-biz-ud-gothic/main/fonts/ttf/BIZUDGothic-Regular.ttf"
        
        # 🌟 変更点2: サーバーにブロックされないように「身分証(User-Agent)」を持たせて通信する
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(font_path, 'wb') as out_file:
            out_file.write(response.read())
            
    # ダウンロードしたフォントをMatplotlib（画像描画ツール）に直接セット
    fm.fontManager.addfont(font_path)
    plt.rcParams['font.family'] = 'BIZ UDGothic'

# 描画の前にフォント設定を呼び出す（キャッシュにより起動時1回だけ実行されます）
setup_japanese_font()

# --- キャッシュ関数 ---
def cached_get_all_logs():
    return robust_api_call(get_all_logs, fallback_value=pd.DataFrame())

def cached_load_quiz_records():
    return robust_api_call(load_quiz_records, fallback_value=pd.DataFrame())

def cached_get_student_master():
    return robust_api_call(get_student_master, fallback_value=pd.DataFrame())

# --- 画像描画ロジック ---
def create_report_image(student_name, target_month_str, df_logs, df_quiz):
    # 画像のキャンバスを用意（スマホで見やすい縦長サイズ）
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 12), gridspec_kw={'height_ratios': [1, 2]})
    fig.patch.set_facecolor('#f8f9fa') # 優しい背景色
    
    # 🌟 タイトル
    fig.suptitle(f"{student_name} さん 月末学習レポート\n【 {target_month_str} 】", fontsize=24, fontweight='bold', color='#333333', y=0.95)
    
    # ==========================================
    # 📊 1. 今月の学習量（科目別コマ数グラフ）
    # ==========================================
    name_col_log = '生徒名' if '生徒名' in df_logs.columns else '名前'
    df_student_logs = df_logs[df_logs[name_col_log] == student_name].copy()
    
    if not df_student_logs.empty:
        df_student_logs['日時'] = pd.to_datetime(df_student_logs['日時'], format='mixed', errors='coerce')
        df_student_logs['年月'] = df_student_logs['日時'].dt.strftime('%Y年%m月')
        df_month_logs = df_student_logs[df_student_logs['年月'] == target_month_str]
        
        if not df_month_logs.empty and '科目' in df_month_logs.columns:
            subject_counts = df_month_logs['科目'].value_counts()
            
            # 横棒グラフを描画
            bars = ax1.barh(subject_counts.index, subject_counts.values, color='#4CAF50', height=0.6)
            ax1.set_title("📚 今月の受講状況（科目別 授業回数）", fontsize=18, fontweight='bold', color='#555555')
            ax1.set_xlabel("回数 (コマ)", fontsize=14)
            ax1.tick_params(axis='both', which='major', labelsize=14)
            ax1.invert_yaxis() # 上から多い順にする
            
            # 棒の横に数字を書く
            for bar in bars:
                ax1.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height()/2, 
                         f"{int(bar.get_width())} 回", 
                         va='center', fontsize=14, fontweight='bold', color='#333333')
        else:
            ax1.text(0.5, 0.5, "今月の授業データがありません", ha='center', va='center', fontsize=16)
            ax1.axis('off')
    else:
        ax1.text(0.5, 0.5, "授業データがありません", ha='center', va='center', fontsize=16)
        ax1.axis('off')
        
    # ==========================================
    # 👑 2. 今までの小テスト習熟度（色付き表）
    # ==========================================
    ax2.set_title("👑 これまでの小テスト習熟度", fontsize=18, fontweight='bold', color='#555555')
    ax2.axis('off') # グラフの軸を消して表だけにする
    
    name_col_quiz = '生徒名' if '生徒名' in df_quiz.columns else '名前'
    df_student_quiz = df_quiz[df_quiz[name_col_quiz] == student_name].copy()
    
    if not df_student_quiz.empty:
        df_student_quiz['日時'] = pd.to_datetime(df_student_quiz['日時'], format='mixed', errors='coerce')
        # 最新の記録だけを残す
        df_quiz_sorted = df_student_quiz.sort_values(by=['テキスト', '単元', '日時'], ascending=[True, True, False])
        latest_quiz = df_quiz_sorted.drop_duplicates(subset=['テキスト', '単元'], keep='first')
        
        # 表のデータを作る（最新15件くらいに絞る）
        display_data = latest_quiz.head(15)
        
        cell_text = []
        cell_colors = []
        for _, row in display_data.iterrows():
            text = str(row.get('テキスト', ''))
            unit = str(row.get('単元', ''))
            score_raw = row.get('点数', 0)
            date_str = row['日時'].strftime('%Y/%m/%d') if pd.notna(row['日時']) else ""
            
            try: score = float(score_raw)
            except: score = 0
            
            score_text = f"👑 {int(score)} 点" if score >= 100 else f"🔴 {int(score)} 点" if score < 80 else f"🟢 {int(score)} 点"
            
            # 色分けロジック
            color = "#ffebee" # 🔴 赤系（80点未満）
            if score >= 100: color = "#fff8e1" # 👑 金系（100点）
            elif score >= 80: color = "#e8f5e9" # 🟢 緑系（80点以上）
                
            cell_text.append([text, unit, score_text, date_str])
            cell_colors.append(["#ffffff", "#ffffff", color, "#ffffff"])
            
        if cell_text:
            col_labels = ["テキスト名", "単元", "最新点数", "最終実施日"]
            table = ax2.table(cellText=cell_text, cellColours=cell_colors, colLabels=col_labels, loc='center', cellLoc='center', bbox=[0.05, 0.1, 0.9, 0.8])
            table.auto_set_font_size(False)
            table.set_fontsize(12)
            
            # ヘッダーの色付け
            for j, label in enumerate(col_labels):
                table[(0, j)].set_facecolor('#e0e0e0')
                table[(0, j)].set_text_props(weight='bold')
        else:
            ax2.text(0.5, 0.5, "小テストの記録がありません", ha='center', va='center', fontsize=16)
    else:
        ax2.text(0.5, 0.5, "小テストの記録がありません", ha='center', va='center', fontsize=16)

    # 署名
    fig.text(0.95, 0.02, "Powered by 教室管理システム", fontsize=10, color='gray', ha='right')

    plt.tight_layout(rect=[0, 0.05, 1, 0.92]) # タイトルとフッターの余白調整
    
    # 画像データとして保存（メモリ上）
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=200, bbox_inches='tight', facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close(fig)
    return buf.getvalue()


# --- タブの描画関数 ---
def render_monthly_visual_report_tab():
    st.write("保護者のLINEへ送付する「月末学習レポート画像（PNG）」を自動生成します。")
    st.caption("※スクショ不要！ボタンを押すと、画質が統一された最高品質のレポート画像がダウンロードできます。")
    
    df_students = cached_get_student_master()
    if df_students.empty:
        st.warning("生徒データが読み込めません。")
        return
        
    student_options = (df_students['生徒ID'].astype(str) + " - " + df_students['生徒名']).tolist()
    
    c1, c2 = st.columns(2)
    with c1:
        selected_student = st.selectbox("👤 対象の生徒を選択", student_options, index=None, placeholder="-- 生徒を選択 --", key="monthly_report_student")
    with c2:
        today = datetime.date.today()
        # 直近6ヶ月分の選択肢を作る
        month_options = [(today.replace(day=1) - pd.DateOffset(months=i)).strftime('%Y年%m月') for i in range(6)]
        selected_month = st.selectbox("📅 出力する月", month_options)
        
    if selected_student:
        student_name = selected_student.split(" - ")[1]
        
        st.divider()
        if st.button(f"🚀 {student_name} さんの {selected_month} レポート画像を生成する", type="primary", use_container_width=True):
            
            with st.spinner("データを集計し、プロ仕様のレポート画像を描き上げています...（約3秒）"):
                df_logs = cached_get_all_logs()
                df_quiz = cached_load_quiz_records()
                
                # 裏側で画像を作成
                img_bytes = create_report_image(student_name, selected_month, df_logs, df_quiz)
                
                st.success("✅ レポート画像の生成が完了しました！プレビューを確認してダウンロードしてください。")
                
                # プレビュー表示
                st.image(img_bytes, caption=f"{student_name}さん {selected_month} レポート", use_container_width=True)
                
                # ダウンロードボタン
                file_name = f"{student_name}_{selected_month}_学習レポート.png"
                st.download_button(
                    label="📥 この画像をダウンロードして公式LINEに添付する",
                    data=img_bytes,
                    file_name=file_name,
                    mime="image/png",
                    type="primary",
                    use_container_width=True
                )