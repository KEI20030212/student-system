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

# --- 画像描画ロジック（デザイン大改造・プロフェッショナル版） ---
def create_report_image(student_name, target_month_str, df_logs, df_quiz):
    # 🌟 デザイン設定（Tailwind CSS風のモダンカラーパレット）
    COLOR_BG = "#F1F5F9"        # 全体背景（薄いグレー）
    COLOR_HEADER = "#0F172A"    # 一番上のヘッダー帯（濃いネイビー）
    COLOR_TEXT_MAIN = "#1E293B" # メインテキスト（濃いグレー）
    COLOR_TEXT_SUB = "#64748B"  # サブテキスト（中間グレー）
    COLOR_BAR = "#3B82F6"       # 棒グラフ（爽やかなブルー）
    
    # 画像のキャンバスを用意
    fig = plt.figure(figsize=(10, 14), facecolor=COLOR_BG)
    gs = fig.add_gridspec(3, 1, height_ratios=[0.8, 2.5, 6])
    
    # ==========================================
    # 🎨 1. ヘッダーエリア（リッチな帯）
    # ==========================================
    ax_head = fig.add_subplot(gs[0])
    ax_head.axis('off')
    # ヘッダーの背景帯を描画
    ax_head.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax_head.transAxes, color=COLOR_HEADER, zorder=-1))
    
    # 文字の配置
    ax_head.text(0.05, 0.7, "Monthly Learning Report", color='#94A3B8', fontsize=14, fontweight='bold', transform=ax_head.transAxes)
    ax_head.text(0.05, 0.3, f"{student_name} さんの学習レポート", color='white', fontsize=26, fontweight='bold', transform=ax_head.transAxes)
    ax_head.text(0.95, 0.3, f"{target_month_str}", color='#38BDF8', fontsize=22, fontweight='bold', ha='right', transform=ax_head.transAxes)

    # ==========================================
    # 📊 2. 今月の学習量（モダンな棒グラフ）
    # ==========================================
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
            bars = ax_graph.barh(y_pos, subject_counts.values, color=COLOR_BAR, height=0.4)
            
            # 軸の装飾
            ax_graph.set_yticks(y_pos)
            ax_graph.set_yticklabels(subject_counts.index, fontsize=14, fontweight='bold', color=COLOR_TEXT_MAIN)
            ax_graph.invert_yaxis() # 上から多い順
            
            # 不要な枠線や目盛りを完全に消してスタイリッシュに！
            for spine in ax_graph.spines.values():
                spine.set_visible(False)
            ax_graph.xaxis.set_visible(False)
            ax_graph.tick_params(axis='y', length=0, pad=10)
            
            # 棒の右側に直接数値を書く
            for bar in bars:
                width = bar.get_width()
                ax_graph.text(width + 0.15, bar.get_y() + bar.get_height()/2, 
                              f"{int(width)} コマ", 
                              va='center', fontsize=14, fontweight='bold', color=COLOR_BAR)
        else:
            ax_graph.text(0.5, 0.5, "今月の受講データがありません", ha='center', va='center', fontsize=14, color=COLOR_TEXT_SUB)
            ax_graph.axis('off')
    else:
        ax_graph.text(0.5, 0.5, "授業データがありません", ha='center', va='center', fontsize=14, color=COLOR_TEXT_SUB)
        ax_graph.axis('off')

    # ==========================================
    # 👑 3. 小テスト習熟度（Webデザイン風の美しい表）
    # ==========================================
    ax_table = fig.add_subplot(gs[2])
    ax_table.axis('off')
    ax_table.set_title("最近の小テスト習熟度", fontsize=18, fontweight='bold', color=COLOR_TEXT_MAIN, loc='left', pad=15)
    
    name_col_quiz = '生徒名' if '生徒名' in df_quiz.columns else '名前'
    df_student_quiz = df_quiz[df_quiz[name_col_quiz] == student_name].copy()
    
    if not df_student_quiz.empty:
        df_student_quiz['日時'] = pd.to_datetime(df_student_quiz['日時'], format='mixed', errors='coerce')
        df_quiz_sorted = df_student_quiz.sort_values(by=['テキスト', '単元', '日時'], ascending=[True, True, False])
        latest_quiz = df_quiz_sorted.drop_duplicates(subset=['テキスト', '単元'], keep='first')
        
        display_data = latest_quiz.head(12) # 見やすさ重視で最大12件
        
        cell_text = []
        cell_colors = []
        text_colors = []
        
        for _, row in display_data.iterrows():
            text = str(row.get('テキスト', ''))
            unit = str(row.get('単元', ''))
            score_raw = row.get('点数', 0)
            date_str = row['日時'].strftime('%m/%d') if pd.notna(row['日時']) else ""
            
            try: score = float(score_raw)
            except: score = 0
            
            # 点数に応じたステータスカラー
            if score >= 100:
                bg_c = "#FEF9C3" # 薄い黄色
                txt_c = "#854D0E" # 濃い茶色
                s_txt = f"👑 {int(score)}点"
            elif score >= 80:
                bg_c = "#DCFCE7" # 薄い緑
                txt_c = "#166534" # 濃い緑
                s_txt = f"🟢 {int(score)}点"
            else:
                bg_c = "#FEE2E2" # 薄い赤
                txt_c = "#991B1B" # 濃い赤
                s_txt = f"🔴 {int(score)}点"
                
            # 文字列を適度な長さにカットしてレイアウト崩れを防ぐ
            if len(text) > 10: text = text[:9] + "…"
            if len(unit) > 12: unit = unit[:11] + "…"
                
            cell_text.append([date_str, text, unit, s_txt])
            cell_colors.append(["", "", "", bg_c])
            text_colors.append([COLOR_TEXT_MAIN, COLOR_TEXT_MAIN, COLOR_TEXT_MAIN, txt_c])
            
        if cell_text:
            col_labels = ["実施日", "テキスト名", "単元名", "点数・評価"]
            # bboxを指定して表を画面いっぱいに広げ、ゆとりを持たせる
            table = ax_table.table(cellText=cell_text, colLabels=col_labels, loc='center', cellLoc='center', bbox=[0, 0, 1, 1])
            table.auto_set_font_size(False)
            table.set_fontsize(13)
            
            # 🌟 表のデザインを徹底的に作り込む
            for (row, col), cell in table.get_celld().items():
                # 罫線を背景色と同じにして「見えない太枠（パディング）」のように扱う
                cell.set_edgecolor(COLOR_BG)
                cell.set_linewidth(5)
                
                if row == 0:
                    # ヘッダー行
                    cell.set_facecolor('#E2E8F0')
                    cell.set_text_props(color=COLOR_TEXT_SUB, fontweight='bold')
                else:
                    # 行ごとに背景色を交互に変える（ストライプ）
                    if row % 2 == 1:
                        cell.set_facecolor('#FFFFFF')
                    else:
                        cell.set_facecolor('#F8FAFC')
                        
                    # セルの文字色を設定
                    cell.set_text_props(color=text_colors[row-1][col], fontweight='normal')
                    
                    # 🌟 点数列（一番右）のみ特別デザイン
                    if col == 3:
                        cell.set_facecolor(cell_colors[row-1][3])
                        cell.set_text_props(fontweight='bold')
                        
            # 列幅の調整
            table.auto_set_column_width(col=[0, 3])
            
        else:
            ax_table.text(0.5, 0.5, "小テストの記録がありません", ha='center', va='center', fontsize=14, color=COLOR_TEXT_SUB)
    else:
        ax_table.text(0.5, 0.5, "小テストの記録がありません", ha='center', va='center', fontsize=14, color=COLOR_TEXT_SUB)

    # 署名（フッター）
    fig.text(0.95, 0.02, "Generated by 教室管理システム", fontsize=10, color='#CBD5E1', ha='right')

    plt.tight_layout(rect=[0.02, 0.05, 0.98, 0.98], h_pad=3.0) 
    
    # 画像データとして保存（超高画質）
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=250, bbox_inches='tight', facecolor=fig.get_facecolor())
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