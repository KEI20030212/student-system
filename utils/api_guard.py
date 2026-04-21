import time
import streamlit as st

def robust_api_call(func, *args, retries=3, base_delay=1.0, fallback_value=None, notify=True, **kwargs):
    """
    外部通信（Google Sheets APIなど）のエラーを完全に防ぎ、安全に再試行するための共通関数。
    
    引数:
        func: 実行したい関数
        *args: 関数に渡す引数
        retries: 最大再試行回数（デフォルト: 3回）
        base_delay: 最初の待機時間（秒）。試行ごとに 1秒 → 2秒 → 4秒 と倍増します。（指数的バックオフ）
        fallback_value: すべての再試行が失敗した場合に返す安全な値（空のリストや DataFrame など）
        notify: 完全に失敗した際に Streamlit の toast でユーザーに通知するかどうか
        **kwargs: 関数に渡すキーワード引数
    """
    for attempt in range(retries):
        try:
            # 関数の実行を試みる
            result = func(*args, **kwargs)
            return result
            
        except Exception as e:
            # 最後の試行以外なら、待機して再挑戦
            if attempt < retries - 1:
                sleep_time = base_delay * (2 ** attempt)
                time.sleep(sleep_time)
            # 規定回数すべて失敗した場合
            else:
                if notify:
                    # エラーでアプリを落とさず、画面右下に小さく通知を出す
                    func_name = getattr(func, '__name__', 'データ通信')
                    st.toast(f"⚠️ {func_name} の通信に失敗しました。時間をおいてお試しください。", icon="🚨")
                
                # 安全な代替データ（フォールバック）を返して処理を続行させる
                return fallback_value