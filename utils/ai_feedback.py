import google.generativeai as genai
import streamlit as st
import json

def generate_ai_feedback(student_name, subject, homework_status, concentration, report_text):
    """
    授業ログからAIフィードバック(Y列)とスコア(Z列)を自動生成する関数
    """
    # secrets.tomlからAPIキーを読み込んでGeminiをセットアップ
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    except Exception:
        return "B", "APIキーが設定されていないため、AIの自動評価をスキップしました。"

    # Geminiの中でも「高速かつ賢い」最新のFlashモデルを使用
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # 🌟 ここがAIの頭脳（プロンプト）！先生の代わりにどう評価するかを指示しています
    prompt = f"""
    あなたは学習塾のプロの教室長です。
    以下の講師が書いた授業報告書（ログ）を読み、講師に対する「フィードバックコメント」と、「報告書の品質スコア（S, A, B, C）」を作成してください。

    【今回の授業情報】
    ・生徒名: {student_name}
    ・科目: {subject}
    ・宿題の実施状況: {homework_status}
    ・授業中の様子（集中力など）: {concentration}
    ・講師が書いた報告コメント: {report_text}

    【評価基準（スコア）】
    S: 生徒の具体的なつまずきや、それに対する具体的な指導内容、次回の改善策が明確に書かれている。素晴らしいレポート。
    A: 指導内容は書かれているが、さらに具体的な声かけや生徒の反応があるとより良くなる。
    B: 事実の羅列（「〇〇をやりました」）のみで、講師の考察や具体的な指導内容が薄い。
    C: 文字数が極端に少ない、または内容が不十分。ネガティブな事実のみで改善の対策がない。

    【フィードバックのトーン＆マナー】
    ・講師のモチベーションが上がるよう、まずは「お疲れ様です！」「〇〇の記載、素晴らしいですね！」とポジティブに褒めてください。
    ・その上で、スコアに応じて「次回はこうするともっと良くなりますよ」という具体的なアドバイスを1〜2文で添えてください。
    ・文字数は150〜200文字程度に収めてください。

    【出力形式】
    以下のJSON形式でのみ出力してください。他のテキスト（マークダウンなど）は絶対に含めないでください。
    {{
        "score": "S, A, B, Cのいずれか",
        "comment": "講師へのフィードバックコメント"
    }}
    """
    
    try:
        # AIに考えてもらう
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # JSON（データ）以外のゴミ文字が入っていたら取り除く安全処理
        if response_text.startswith("```json"):
            response_text = response_text[7:-3]
        elif response_text.startswith("```"):
            response_text = response_text[3:-3]
            
        # データをPythonで扱える形に変換
        result = json.loads(response_text)
        
        return result.get("score", "B"), result.get("comment", "フィードバックの生成に失敗しました。")
        
    except Exception as e:
        print(f"AI Feedback Error: {e}")
        return "B", "通信エラーまたは文字数制限などにより、AIの自動評価ができませんでした。"