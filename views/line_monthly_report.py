import streamlit as st
import pandas as pd
import datetime
import io
import os
import urllib.request
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# 🌟 追加: get_textbook_master をインポート
from utils.g_sheets import get_all_logs, load_quiz_records, get_student_master, get_textbook_master
from utils.api_guard import robust_api_call

# ==========================================
# 🌟 日本語文字化けを防ぐ関数
# ==========================================
@st.cache_resource
def setup_japanese_font():
    font_path = "BIZUDGothic-Regular.ttf"
    if not os.path.exists(font_path):
        url = "https://raw.githubusercontent.com/googlefonts/morisawa-biz-ud-gothic/main/fonts/ttf/BIZUDGothic-Regular.ttf"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(font_path, 'wb') as out_file:
            out_file.write(response.read())
            
    fm.fontManager.addfont(font_path)
    plt.rcParams['font.family'] = 'BIZ UDGothic'

setup_japanese_font()

# --- キャッシュ関数 ---
def cached_get_all_logs():
    return robust_api_call(get_all_logs, fallback_value=pd.DataFrame())

def cached_load_quiz_records():
    return robust_api_call(load_quiz_records, fallback_value=pd.DataFrame())

def cached_get_student_master():
    return robust_api_call(get_student_master, fallback_value=pd.DataFrame())

# 🌟 追加: テキストマスタ（分母）を取得する関数
def cached_get_textbook_master():
    return robust_api_call(get_textbook_master, fallback_value={})

# ==========================================
# 🎨 画像描画ロジック（プログレスバー進化版）
# ==========================================
def create_report_image(student_name, target_month_str, df_logs, df_quiz, tb_master):
    # デザイン設定（モダンカラーパレット）
    COLOR_BG = "#F1F5F9"
    COLOR_HEADER = "#0F172A"
    COLOR_TEXT_MAIN = "#1E293B"
    COLOR_TEXT_SUB = "#64748B"
    COLOR_BAR_FILL = "#3B82F6" # プログレスバーの鮮やかな青
    COLOR_BAR_BG = "#E2E8F0"   # プログレスバーの背景グレー
    
    fig = plt.figure(figsize=(10, 14), facecolor=COLOR_BG)
    gs = fig.add_gridspec(3, 1, height_ratios=[0.8, 2.5, 6])
    
    # ------------------------------------------
    # 1. ヘッダーエリア
    # ------------------------------------------
    ax_head = fig.add_subplot(gs[0])
    ax_head.axis('off')
    ax_head.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax_head.transAxes, color=COLOR_HEADER, zorder=-1))
    
    ax_head.text(0.05, 0.7, "Monthly Learning Report", color='#94A3B8', fontsize=14, fontweight='bold', transform=ax_head.transAxes)
    ax_head.text(0.05, 0.3, f"{student_name} さんの学習レポート", color='white', fontsize=26, fontweight='bold', transform=ax_head.transAxes)
    ax_head.text(0.95, 0.3, f"{target_month_str}", color='#38BDF8', fontsize=22, fontweight='bold', ha='right', transform=ax_head.transAxes)

    # ------------------------------------------
    # 2. 今月の学習量（コマ数）
    # ------------------------------------------
    ax_graph = fig.add_subplot(gs[1])
    ax_graph.set_facecolor(COLOR_BG)
    ax_graph.set_title("今月の受講状況", fontsize=18, fontweight='bold', color=COLOR_TEXT_MAIN, loc='left', pad=15)
    
    name_col_log = '生徒名' if '生徒名' in df_logs.columns else '名前'
    df_student_logs = df_logs[df_logs[name_col_log] == student_name].copy()
    
    if not df_student_logs.empty:
        df_student_logs['日時'] = pd.to_datetime(df_student_logs['日時'], format='mixed', errors='coerce')
        df_student_logs['年月'] = df_student_logs['日時'].dt.strftime('%Y年%m月')
        df_month_logs = df_student_logs[df_student_logs['年月'] == target_month_str]
        
        if not df_month_logs.empty and '科目' in df_month_logs.columns:
            subject_counts = df_month_logs['科目'].value_counts()
            y_pos = range(len(subject_counts))
            bars = ax_graph.barh(y_pos, subject_counts.values, color=COLOR_BAR_FILL, height=0.4)
            
            ax_graph.set_yticks(y_pos)
            ax_graph.set_yticklabels(subject_counts.index, fontsize=14, fontweight='bold', color=COLOR_TEXT_MAIN)
            ax_graph.invert_yaxis() 
            
            for spine in ax_graph.spines.values(): spine.set_visible(False)
            ax_graph.xaxis.set_visible(False)
            ax_graph.tick_params(axis='y', length=0, pad=10)
            
            for bar in bars:
                width = bar.get_width()
                ax_graph.text(width + 0.15, bar.get_y() + bar.get_height()/2, 
                              f"{int(width)} コマ", va='center', fontsize=14, fontweight='bold', color=COLOR_BAR_FILL)
        else:
            ax_graph.text(0.5, 0.5, "今月の受講データがありません", ha='center', va='center', fontsize=14, color=COLOR_TEXT_SUB)
            ax_graph.axis('off')
    else:
        ax_graph.text(0.5, 0.5, "授業データがありません", ha='center', va='center', fontsize=14, color=COLOR_TEXT_SUB)
        ax_graph.axis('off')

    # ------------------------------------------
    # 🌟 3. 進行中テキストのプログレスバー（大改造部分）
    # ------------------------------------------
    ax_prog = fig.add_subplot(gs[2])
    ax_prog.axis('off')
    ax_prog.set_title("テキスト習熟度 ＆ 進捗ゲージ", fontsize=18, fontweight='bold', color=COLOR_TEXT_MAIN, loc='left', pad=15)
    
    name_col_quiz = '生徒名' if '生徒名' in df_quiz.columns else '名前'
    df_student_quiz = df_quiz[df_quiz[name_col_quiz] == student_name].copy()
    
    if not df_student_quiz.empty:
        df_student_quiz['日時'] = pd.to_datetime(df_student_quiz['日時'], format='mixed', errors='coerce')
        
        # 最近取り組んだテキスト上位5冊を特定
        recent_texts = df_student_quiz.groupby('テキスト')['日時'].max().sort_values(ascending=False).head(5).index.tolist()
        
        MAX_ITEMS = 5
        ax_prog.set_xlim(0, 100)
        ax_prog.set_ylim(-0.5, MAX_ITEMS - 0.5)
        
        for i, tb_name in enumerate(recent_texts):
            y_center = MAX_ITEMS - 1 - i # 上から順に描画
            
            # このテキストの生徒の記録
            df_tb = df_student_quiz[df_student_quiz['テキスト'] == tb_name].copy()
            # 各単元の「最新の点数」だけを残す
            latest_units = df_tb.sort_values('日時', ascending=False).drop_duplicates('単元', keep='first')
            
            def safe_float(val):
                try: return float(val)
                except: return 0.0
            latest_units['点数_num'] = latest_units['点数'].apply(safe_float)
            
            # 成績のカウント
            gold = len(latest_units[latest_units['点数_num'] >= 100])
            green = len(latest_units[(latest_units['点数_num'] >= 80) & (latest_units['点数_num'] < 100)])
            red = len(latest_units[latest_units['点数_num'] < 80])
            completed_units = len(latest_units)
            
            # 🌟 マスタから分母を取得
            master_units = tb_master.get(tb_name, {})
            total_units = len(master_units)
            
            # 万が一マスタに未登録の場合は、安全のために補正
            if total_units == 0 or total_units < completed_units:
                total_units = completed_units if completed_units > 0 else 1
                
            # 進捗率の計算
            pct = (completed_units / total_units) * 100
            if pct > 100: pct = 100
            
            # ① テキスト名 ＆ 右端に進捗テキスト
            ax_prog.text(0, y_center + 0.35, f"📘 {tb_name}", fontsize=15, fontweight='bold', color=COLOR_TEXT_MAIN, ha='left')
            ax_prog.text(100, y_center + 0.35, f"{completed_units} / {total_units} 単元完了 ({int(pct)}%)", fontsize=14, fontweight='bold', color=COLOR_TEXT_MAIN, ha='right')
            
            # ② プログレスバーの背景（全体）
            ax_prog.barh(y_center, 100, height=0.25, color=COLOR_BAR_BG, left=0, edgecolor='none')
            # ③ プログレスバーの前面（進捗分）
            if pct > 0:
                ax_prog.barh(y_center, pct, height=0.25, color=COLOR_BAR_FILL, left=0, edgecolor='none')
                
            # ④ バーの下に成績の内訳を表示
            stats_text = f"👑 完璧(100点): {gold} 単元   /   🟢 合格(80点~): {green} 単元   /   🔴 要復習: {red} 単元"
            ax_prog.text(0, y_center - 0.32, stats_text, fontsize=12, color=COLOR_TEXT_SUB, ha='left', fontweight='bold')

    else:
        ax_prog.text(50, 2.5, "小テストの記録がありません", ha='center', va='center', fontsize=14, color=COLOR_TEXT_SUB)

    # ------------------------------------------
    # フッター署名
    # ------------------------------------------
    fig.text(0.95, 0.02, "Generated by 教室管理システム", fontsize=10, color='#CBD5E1', ha='right')

    plt.tight_layout(rect=[0.02, 0.05, 0.98, 0.98], h_pad=3.0) 
    
    # 画像書き出し
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=250, bbox_inches='tight', facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close(fig)
    return buf.getvalue()


# --- タブの描画関数 ---
def render_monthly_visual_report_tab():
    st.write("保護者のLINEへ送付する「月末学習レポート画像（PNG）」を自動生成します。")
    st.caption("※テキストマスタと連携し、生徒が今どのテキストをどれくらい進めているかを美しいプログレスバーで可視化します。")
    
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
        month_options = [(today.replace(day=1) - pd.DateOffset(months=i)).strftime('%Y年%m月') for i in range(6)]
        selected_month = st.selectbox("📅 出力する月", month_options)
        
    if selected_student:
        student_name = selected_student.split(" - ")[1]
        
        st.divider()
        if st.button(f"🚀 {student_name} さんの {selected_month} レポート画像を生成する", type="primary", use_container_width=True):
            
            with st.spinner("データを集計し、プロ仕様のレポート画像を描き上げています...（約3秒）"):
                df_logs = cached_get_all_logs()
                df_quiz = cached_load_quiz_records()
                # 🌟 追加: テキストマスタを読み込んで画像生成に渡す
                tb_master = cached_get_textbook_master()
                
                img_bytes = create_report_image(student_name, selected_month, df_logs, df_quiz, tb_master)
                
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