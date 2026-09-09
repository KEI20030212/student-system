import google.generativeai as genai
import streamlit as st
import json

def generate_ai_feedback(student_name, subject, homework_status, concentration, report_text):
    """
    授業ログからAIフィードバック(Y列)とスコア(Z列)を自動生成する関数
    """
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    except Exception as e:
        return "B", f"APIキー設定エラー: {str(e)}"

    ai_model_name = st.secrets.get("GEMINI_MODEL_NAME", "gemini-3.6-flash")
    model = genai.GenerativeModel(ai_model_name)
    
    prompt = f"""
    あなたは学習塾で多数の講師を育成してきた、指導力とコミュニケーション能力に優れた「ベテラン教室長」です。
    以下の講師が作成した授業報告書（ログ）を読み、講師のモチベーションを高めつつ、報告書の質を底上げするための「フィードバック」と「品質スコア」を出力してください。

    【今回の授業情報】
    ・生徒名: {student_name}
    ・科目: {subject}
    ・宿題の実施状況: {homework_status}
    ・授業中の様子: {concentration}
    ・講師の報告コメント: {report_text}

    【評価基準（スコア）】
    S (最高): 生徒の「具体的なつまずき箇所」と「それに対する指導内容（どう教えたか）」、さらに「次回の改善策・引継ぎ」がセットで明確に書かれている。
    A (良好): 指導内容は書かれているが、やや抽象的（例：「二次関数が苦手でした」のみで、どう教えたかの記載が薄い等）。あと一歩でS。
    B (改善が必要): 事実の羅列（「〇〇ページまで進みました」「集中していました」）のみで、講師の考察や指導内容が書かれていない。
    C (要指導): 文字数が極端に少ない。または、「全然やってきませんでした」などネガティブな事実のみで、改善に向けた講師からのアプローチがない。

    【フィードバックの書き方（超重要）】
    以下の構成で、温かみのある先輩のようなトーンで書いてください（150〜250文字程度）。
    1. 承認: まずは「お疲れ様です！」と労い、報告内容の中で良かった点（具体的に書けている点や、生徒への向き合い方）を必ず1つ見つけて褒める。
    2. 助言: スコアがA以下の場合は、「次回はこうすると、保護者や次の担当講師にさらに伝わりやすくなりますよ！」という前向きなアドバイスを添える。
    3. 例文の提示: スコアがBまたはCの場合、単に注意するのではなく、「例えば『〜〜』のように一言添えてもらえると助かります！」と、具体的なお手本（例文）をAI自身が考えて提示する。
    4. 禁止事項: 「分析します」「提案します」「〜と推測されます」といったAI特有の機械的な表現は絶対に使わず、チャットツールで人間が送るような自然な言葉遣いにすること。

    【出力形式】
    以下のJSON形式でのみ出力してください。JSON以外の挨拶や解説は絶対に含めないでください。
    {{
        "score": "S, A, B, Cのいずれか",
        "comment": "講師へのフィードバックコメント"
    }}
    """
    
    try:
        # AIに考えてもらう
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # 🌟 改善：AIが余計な文字をつけてきても、データ部分だけを抜き取る処理
        clean_text = response_text
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```")[1].strip()
            
        try:
            # データをシステムで使える形に変換
            result = json.loads(clean_text)
            return str(result.get("score", "B")), str(result.get("comment", response_text))
            
        except json.JSONDecodeError:
            # 🌟 失敗した場合、AIが何を喋ったのかをそのままスプレッドシートに書き込む（原因特定用）
            return "B", f"【AI回答の形式エラー】{response_text}"
            
    except Exception as e:
        # 🌟 APIの通信そのものに失敗した場合、本当のエラー理由を書き込む
        error_msg = str(e)
        if "403" in error_msg or "API_KEY_INVALID" in error_msg:
            return "B", "APIキーが間違っているか、有効になっていません。(認証エラー)"
        else:
            return "B", f"API通信エラー: {error_msg}"
        

def generate_conference_summary(student_name, target_goal, hw_rate, attendance_rate, total_quiz, weak_points_text):
    """
    面談レポート用の総合学習アドバイスを生成する関数
    """
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    except Exception as e:
        return f"APIキー設定エラー: {str(e)}"

    # ※モデル名は最新の軽量高速モデル gemini-1.5-flash を推奨します
    ai_model_name = st.secrets.get("GEMINI_MODEL_NAME", "gemini-1.5-flash")
    model = genai.GenerativeModel(ai_model_name)
    
    prompt = f"""
    あなたは学習塾のベテラン教室長です。
    面談に向けて、以下の生徒の学習データを分析し、保護者と生徒に向けた温かく前向きな「総合学習アドバイス」を作成してください。

    【生徒情報】
    ・生徒名: {student_name}
    ・目標/志望校: {target_goal}
    ・宿題実施率: {hw_rate}
    ・出席率: {attendance_rate}
    ・小テスト実施回数: {total_quiz}回
    ・苦手傾向の単元（直近）: {weak_points_text}

    【作成の条件（重要）】
    1. 構成: まずは生徒の頑張り（宿題や出席、小テストの回数など）を具体的に数字を挙げて褒めてください。
    2. 課題へのアプローチ: 「苦手傾向の単元」がある場合は、それをどう克服していくか、塾での対策を含めた前向きなアドバイスを書いてください。（「特になし」の場合は、今のペースを維持することの重要性を伝えてください）
    3. 目標への道筋: 志望校や目標に向けて、今後ご家庭と塾でどのように連携していくかを示してください。
    4. トーン: 保護者に安心感を与え、生徒のモチベーションが上がるような、丁寧で温かみのある「です・ます」調にしてください。AI特有の機械的な表現（「分析します」「提案します」など）は禁止です。
    5. 文字数: 300〜400文字程度で、段落を適度に分けて読みやすくしてください。
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        error_msg = str(e)
        if "403" in error_msg or "API_KEY" in error_msg:
            return "APIキーが間違っているか、有効になっていません。(認証エラー)"
        else:
            return f"AI生成エラー: {error_msg}"