# utils/pdf_generator.py

import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

def generate_payslip_pdf(data_dict, month_str):
    """
    1人分の給与データを受け取り、PDFファイル（バイナリデータ）を作成して返す関数
    """
    # 日本語フォントの設定（面倒なダウンロード不要の組み込みフォント！）
    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
    
    # PDFを描き込むための「空の画用紙（メモリ）」を用意
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    
    # --- ここからPDFのデザイン（描画） ---
    
    # 1. タイトル
    c.setFont('HeiseiKakuGo-W5', 20)
    c.drawCentredString(297, 750, f"{month_str}分 給与明細書")
    
    # 2. 宛名
    c.setFont('HeiseiKakuGo-W5', 14)
    c.drawString(50, 680, f"{data_dict['👨‍🏫 担当講師']} 様")
    c.line(50, 675, 250, 675) # 名前の下にアンダーライン
    
    # 3. 明細の内容（項目と金額を並べる）
    c.setFont('HeiseiKakuGo-W5', 12)
    y_pos = 620
    step = 30
    
    # 項目のリスト
    items = [
        ("合計授業コマ数", f"{data_dict['合計コマ数']} コマ"),
        ("授業給", f"{data_dict['授業給 (円)']} 円"),
        ("役職手当", f"{data_dict['役職手当 (円)']} 円"),
        ("出勤日数", f"{data_dict['出勤日数']} 日"),
        ("交通費合計", f"{data_dict['交通費合計 (円)']} 円")
    ]
    
    for label, value in items:
        c.drawString(80, y_pos, label)
        c.drawRightString(400, y_pos, value) # 金額は右揃えで綺麗に！
        c.setDash(1, 2) # 点線にする
        c.line(80, y_pos - 5, 400, y_pos - 5)
        c.setDash() # 実線に戻す
        y_pos -= step
        
    # 4. 最終支給額（四角い枠で囲って目立たせる！）
    c.setFont('HeiseiKakuGo-W5', 16)
    c.rect(70, y_pos - 40, 340, 40) # 枠線
    c.drawString(90, y_pos - 25, "最終支給額（合計）")
    c.drawRightString(390, y_pos - 25, f"{data_dict['💰 最終支給額 (円)']} 円")
    
    # 5. フッター（塾名など）
    c.setFont('HeiseiKakuGo-W5', 10)
    c.drawRightString(500, 50, "※本明細に関するお問い合わせは塾長まで")
    
    # --- 描画終わり ---
    
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()