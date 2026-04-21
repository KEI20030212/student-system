import time
import random
import logging
import streamlit as st

# 内部のログ出力用設定（コンソールでエラーの正体を確認しやすくします）
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def robust_api_call(func, *args, retries=4, base_delay=1.5, fallback_value=None, notify=True, **kwargs):
    """
    外部通信（Google Sheets APIなど）のエラーを完全に防ぎ、安全に再試行するための強化版関数。
    
    引数:
        func: 実行したい関数
        *args: 関数に渡す引数
        retries: 最大再試行回数（デフォルト: 4回に少し増強）
        base_delay: 最初の待機時間（秒）。
        fallback_value: すべての再試行が失敗した場合に返す安全な値
        notify: 完全に失敗した際に Streamlit の toast でユーザーに通知するかどうか
        **kwargs: 関数に渡すキーワード引数
    """
    func_name = getattr(func, '__name__', 'データ通信')
    
    for attempt in range(retries):
        try:
            # 関数の実行を試みる
            result = func(*args, **kwargs)
            return result
            
        except Exception as e:
            # 最後の試行以外なら、待機して再挑戦
            if attempt < retries - 1:
                # 🌟 強化ポイント1: 指数関数的バックオフ ＋ ジッター（ランダムな揺らぎ）
                # 単純に 2秒→4秒→8秒 と待つと、複数アクセスが同時にリトライして再び弾かれやすいです。
                # そこに 0〜1秒の「ランダムなズレ」を加えることで、アクセスのタイミングを分散させます。
                sleep_time = base_delay * (1.5 ** attempt) + random.uniform(0.1, 1.0)
                
                # 🌟 強化ポイント2: コンソールに警告を出して、裏で何が起きているか把握できるようにする
                logger.warning(f"⚠️ {func_name} でエラー発生。{sleep_time:.2f}秒後に再試行します ({attempt+1}/{retries}) | エラー詳細: {e}")
                
                time.sleep(sleep_time)
                
            # 規定回数すべて失敗した場合
            else:
                logger.error(f"🚨 {func_name} が最大再試行回数に達しました。処理を中断します。 | エラー詳細: {e}")
                
                if notify:
                    # エラーでアプリを落とさず、画面右下に小さく通知を出す
                    st.toast(f"⚠️ {func_name} の通信に失敗しました。時間をおいてお試しください。", icon="🚨")
                
                # 安全な代替データ（フォールバック）を返して処理を続行させる
                return fallback_value