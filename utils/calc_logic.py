import math

def calculate_quiz_points(score):
    try:
        s = float(score)
        if s >= 100: return 20
        elif s >= 90: return 10
        elif s >= 80: return 9
        elif s >= 70: return 8
        elif s >= 60: return 7
        elif s >= 50: return 6
        elif s >= 40: return 5
        elif s >= 30: return 4
        elif s >= 20: return 3
        elif s >= 10: return 2
        else: return 1
    except:
        return 0

# ✨ 新しく追加：宿題履行率を計算する魔法
def calculate_hw_rate(assigned_pages, completed_pages):
    """
    出したページ数とやってきたページ数から履行率(%)を出す。
    1ページも出していない場合は 0% とする。
    """
    try:
        assigned = float(assigned_pages)
        completed = float(completed_pages)
        if assigned <= 0:
            return 0.0
        # 100%を超えることはないので、minで100に抑える
        rate = (completed / assigned) * 100
        return min(100.0, rate)
    except:
        return 0.0

def calculate_motivation_rank(hw_rate, quiz_pts):
    """
    宿題履行率(%)と小テストポイントからやる気(1〜5)を算出。
    ※ quiz_pts はこれまでの累計や平均など、先生の運用に合わせて渡します。
    """
    if hw_rate >= 100 and quiz_pts >= 120: return 5
    elif hw_rate >= 90 and quiz_pts >= 100: return 4
    elif hw_rate >= 75 and quiz_pts >= 80: return 3
    elif hw_rate >= 50 and quiz_pts >= 40: return 2
    else: return 1
def calculate_ability_rank(naishin, dev_score):
    """内申点と偏差値から能力(1〜5)を算出"""
    if naishin >= 5 and dev_score >= 65: return 5
    elif naishin >= 4 and dev_score >= 55: return 4
    elif naishin >= 3 and dev_score >= 45: return 3
    elif naishin >= 2 and dev_score >= 35: return 2
    else: return 1
