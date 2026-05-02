import os
from datetime import datetime
from zoneinfo import ZoneInfo

def get_time_info():
    tz = ZoneInfo("Asia/Tokyo")
    now = datetime.now(tz)
    current_time_str = now.strftime("%H:%M")
    hour = now.hour

    if 6 <= hour < 12:
        period = "午前"
        forbidden = "今夜, 就寝前, 夜も深い時間帯"
        recommended = "今朝, 今日の朝, 午前中"
        instruction = "今夜表現は絶対禁止。今朝・午前中表現のみ使用。"
    elif 12 <= hour < 18:
        period = "午後"
        forbidden = "今夜, 就寝前, 夜も深い時間帯"
        recommended = "今日の午後, 今日の夕方"
        instruction = "今夜表現は絶対禁止。今日の午後・今日の夕方表現のみ使用。"
    elif 18 <= hour < 24:
        period = "夜"
        forbidden = ""
        recommended = "今夜, 就寝前, 明日の朝"
        instruction = "今夜就寝前表現が自然です。"
    else:
        period = "深夜"
        forbidden = ""
        recommended = "夜も深い時間帯, 今夜"
        instruction = "夜も深い時間帯表現が適切です。"

    return current_time_str, hour, period, forbidden, recommended, instruction


def split_message(text, limit=4500):
    """LINE 5000字制限対応: テキストを limit 字以内に分割して返す"""
    if len(text) <= limit:
        return [text]
    parts = []
    while len(text) > limit:
        split_point = text[:limit].rfind('\n')
        if split_point == -1:
            split_point = limit
        parts.append(text[:split_point])
        text = text[split_point:]
    parts.append(text)
    return parts


def send_long_message(user_id, text, push_fn, limit=3000):
    """長いテキストを分割してLINE pushで順番に送る（最大5件）
    分割基準: 文末（。！？）のみ。見つからない場合のみ強制分割。
    改行での分割は行わない（文章途中の切断防止）。
    push_fn: line_push_api(user_id, text) を受け取るコールバック
    """
    messages = []
    while len(text) > limit:
        chunk = text[:limit]
        # 文末（。！？）で分割 — 改行フォールバックなし
        split_point = -1
        for punct in ('。', '！', '？'):
            pos = chunk.rfind(punct)
            if pos > split_point:
                split_point = pos
        if split_point != -1:
            split_point += 1  # 句読点を含めて分割
        else:
            split_point = limit  # 文末が見つからない場合のみ強制分割
        messages.append(text[:split_point])
        text = text[split_point:].lstrip('\n')
    messages.append(text)
    for msg in messages[:5]:
        push_fn(user_id, msg)


def build_flex_fortune(score, rationale, categories, lucky_color, lucky_number, lucky_direction,
                       up_mission, down_mission):
    """LINE Flex Carousel — 4枚カード（スコア / ラッキー / ミッション / CTA）
    up_mission / down_mission: tuple (action_str, score_str, reason_str)
    例) ("🔼 朝に緑茶を飲む", "+5点", "木の気を補う")
    """

    COLOR_EMOJI = {
        "レッド":   "🔴",
        "ブルー":   "🔵",
        "グリーン": "🟢",
        "パープル": "🟣",
        "イエロー": "🟡",
        "ホワイト": "⚪",
        "オレンジ": "🟠",
        "ブラック": "⚫",
        "ネイビー": "🔵",
        "ゴールド": "🟡",
    }
    lucky_color_display = COLOR_EMOJI.get(lucky_color, "") + " " + lucky_color

    def progress_bar(value):
        pct  = f"{min(100, max(0, value))}%"
        rest = f"{min(100, max(0, 100 - value))}%"
        return {
            "type": "box", "layout": "horizontal", "height": "6px", "margin": "xs",
            "contents": [
                {"type": "box", "layout": "vertical", "backgroundColor": "#c9a84c",
                 "width": pct, "contents": []},
                {"type": "box", "layout": "vertical", "backgroundColor": "#ddd9d0",
                 "width": rest, "contents": []}
            ]
        }

    def cat_row(name, value):
        return {
            "type": "box", "layout": "vertical", "margin": "md",
            "contents": [
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": name, "size": "xs",
                         "color": "#3d3d3d", "flex": 2},
                        {"type": "text", "text": str(value), "size": "xs",
                         "color": "#c9a84c", "weight": "bold", "align": "end", "flex": 1}
                    ]
                },
                progress_bar(value)
            ]
        }

    cat_rows = [cat_row(name, val) for name, val in categories.items()]

    up_action, up_score, up_reason       = up_mission
    down_action, down_score, down_reason = down_mission

    # ── カード1: スコア + プログレスバー ──────────────────────────
    card1 = {
        "type": "bubble", "size": "mega",
        "header": {
            "type": "box", "layout": "vertical",
            "backgroundColor": "#1a1f3a", "paddingAll": "16px",
            "contents": [
                {"type": "text", "text": "マルム", "color": "#c9a84c",
                 "size": "sm", "weight": "bold", "align": "center"},
                {"type": "text", "text": "四柱推命エネルギーガイド", "color": "#8890b0",
                 "size": "xxs", "align": "center", "margin": "xs"}
            ]
        },
        "body": {
            "type": "box", "layout": "vertical",
            "paddingAll": "0px",
            "contents": [
                {
                    "type": "box", "layout": "vertical",
                    "backgroundColor": "#1a1f3a",
                    "paddingTop": "20px", "paddingBottom": "24px",
                    "paddingStart": "20px", "paddingEnd": "20px",
                    "contents": [
                        {
                            "type": "box", "layout": "baseline",
                            "justifyContent": "center",
                            "contents": [
                                {"type": "text", "text": str(score), "color": "#c9a84c",
                                 "size": "5xl", "weight": "bold"},
                                {"type": "text", "text": "点", "color": "#c9a84c",
                                 "size": "xl", "margin": "sm"}
                            ]
                        },
                        {
                            "type": "text", "text": rationale, "color": "#c8c4b8",
                            "size": "xs", "align": "center", "margin": "md", "wrap": True
                        }
                    ]
                },
                {
                    "type": "box", "layout": "vertical",
                    "backgroundColor": "#f9f7f2", "paddingAll": "20px",
                    "contents": cat_rows
                }
            ]
        }
    }

    return card1


def extract_lucky_info(text):
    """AIテキストからラッキー情報（カラー・ナンバー・方位）を抽出して返す"""
    import re
    color     = re.search(r'ラッキーカラー[：:]\s*(.+?)[\n]', text)
    number    = re.search(r'ラッキーナンバー[：:]\s*(\d+)', text)
    direction = re.search(r'ラッキー方位[：:]\s*(.+?)[\n]', text)
    return {
        'color':     color.group(1).strip()     if color     else '—',
        'number':    number.group(1)            if number    else '—',
        'direction': direction.group(1).strip() if direction else '—',
    }


def build_prescription_cards(text, saju=None):
    """有料処方箋テキストから ラッキー/ミッション/辛口 の3枚カードを生成"""
    import re

    def extract(section):
        m = re.search(rf'【{re.escape(section)}】(.*?)(?=【|$)', text, re.DOTALL)
        return m.group(1).strip() if m else ""

    # ── ラッキーカード: AIテキストから全項目を抽出 ────────────────────────
    lucky_info    = extract_lucky_info(text)
    lc            = lucky_info['color']
    ln            = lucky_info['number']
    ld            = lucky_info['direction']
    color_display = lc

    # AI テキストからタイム・アイテム抽出
    lucky_section = extract("ラッキーアイテム")
    l_time = l_item = ""
    for line in lucky_section.split('\n'):
        line = line.strip()
        if '⏰' in line:
            l_time = line.split(':', 1)[-1].strip() if ':' in line else line
        elif '🌿' in line:
            l_item = line.split(':', 1)[-1].strip() if ':' in line else line

    def lucky_row(label, value, margin=True):
        row = {
            "type": "box", "layout": "vertical",
            "contents": [
                {"type": "text", "text": label, "size": "xs", "color": "#8888aa"},
                {"type": "text", "text": value or "—", "size": "md",
                 "weight": "bold", "color": "#1a1f3a", "margin": "xs", "wrap": True}
            ]
        }
        if margin:
            row["margin"] = "lg"
        return row

    lucky_card = {
        "type": "bubble", "size": "mega",
        "header": {
            "type": "box", "layout": "vertical",
            "backgroundColor": "#1a1f3a", "paddingAll": "16px",
            "contents": [
                {"type": "text", "text": "今日のラッキー", "color": "#c9a84c",
                 "size": "sm", "weight": "bold", "align": "center"},
                {"type": "text", "text": "詳細版", "color": "#8890b0",
                 "size": "xxs", "align": "center", "margin": "xs"}
            ]
        },
        "body": {
            "type": "box", "layout": "vertical",
            "backgroundColor": "#f9f7f2", "paddingAll": "20px",
            "contents": [
                lucky_row("🎨 ラッキーカラー",  color_display, margin=False),
                {"type": "separator", "margin": "lg", "color": "#e0dbd0"},
                lucky_row("🔢 ラッキーナンバー", str(ln)),
                {"type": "separator", "margin": "lg", "color": "#e0dbd0"},
                lucky_row("🧭 ラッキー方位",    ld),
                {"type": "separator", "margin": "lg", "color": "#e0dbd0"},
                lucky_row("⏰ ラッキータイム",  l_time),
                {"type": "separator", "margin": "lg", "color": "#e0dbd0"},
                lucky_row("🌿 ラッキーアイテム", l_item),
            ]
        }
    }

    # ── ミッション/辛口カード ─────────────────────────────────────
    def text_bubble(header_title, body_text, header_sub=None):
        lines = [l.strip() for l in body_text.split('\n') if l.strip()]
        body_items = []
        for i, line in enumerate(lines[:12]):
            item = {"type": "text", "text": line, "size": "sm",
                    "color": "#3d3d3d", "wrap": True}
            if i > 0:
                item["margin"] = "sm"
            if line.startswith("🔼"):
                item["color"] = "#1a5c1a"
            elif line.startswith("🔽"):
                item["color"] = "#8b1a1a"
            body_items.append(item)
        if not body_items:
            body_items = [{"type": "text", "text": "—", "size": "sm", "color": "#8888aa"}]
        header_contents = [
            {"type": "text", "text": header_title, "color": "#c9a84c",
             "size": "sm", "weight": "bold", "align": "center"}
        ]
        if header_sub:
            header_contents.append(
                {"type": "text", "text": header_sub, "color": "#8890b0",
                 "size": "xxs", "align": "center", "margin": "xs"}
            )
        return {
            "type": "bubble", "size": "mega",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#1a1f3a", "paddingAll": "16px",
                "contents": header_contents
            },
            "body": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#f9f7f2", "paddingAll": "20px",
                "contents": body_items
            }
        }

    mission_card = text_bubble("運気ミッション", extract("運気ミッション"), "本日の全ミッション")
    advice_card  = text_bubble("辛口アドバイス", extract("辛口アドバイス"))

    return {"type": "carousel", "contents": [lucky_card, mission_card, advice_card]}


def build_kyoumei_card(result, partner_name=None):
    """궁합 full 결과 텍스트에서 공명도 % 와 코멘트를 추출해 Flex 버블 생성"""
    import re
    clean_result = result.replace('*', '').replace('#', '')
    pct_match = re.search(r'(\d+)\s*%', clean_result)
    pct = (pct_match.group(1) + '%') if pct_match else '—%'
    print(f"[DEBUG] 공명도 파싱 결과: {pct}")
    comment_match = re.search(r'「([^」\n]+)」', result)
    comment = f'「{comment_match.group(1)}」' if comment_match else '二つの魂が響き合う'
    subtitle = f"{partner_name}との共鳴度（きょうめいど）" if partner_name else "推しとの共鳴度（きょうめいど）"
    pct_num = int(pct.replace('%', '')) if pct != '—%' else 0
    if pct_num >= 90:
        fate_title = "1000年前から決まっていた運命のソウルメイト🌙"
    elif pct_num >= 80:
        fate_title = "互いの光で輝き合う奇跡の存在✨"
    else:
        fate_title = "惹かれ合うほど強くなる運命の絆🔥"
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#1a1a2e",
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": fate_title, "size": "xs",
                 "color": "#c9a84c", "align": "center", "wrap": True},
                {"type": "text", "text": subtitle, "size": "sm",
                 "color": "#888888", "align": "center", "margin": "sm"},
                {"type": "text", "text": pct, "size": "3xl", "weight": "bold",
                 "color": "#FF69B4", "align": "center"},
                {"type": "separator", "margin": "lg"},
                {"type": "text", "text": comment, "size": "xs", "color": "#888888",
                 "align": "center", "wrap": True, "margin": "lg"},
                {"type": "text", "text": "🔮 あなたの共鳴のお守り💖🌙", "size": "xxs",
                 "color": "#aaaaaa", "align": "center", "margin": "md"}
            ]
        }
    }


def build_kyoumei_chemistry_card(result):
    """케미+역할 카드"""
    import re
    clean = result.replace('*','').replace('#','')
    chemi    = re.search(r'二人のケミ[：:]\s*(.+?)[\n]', clean)
    my_role  = re.search(r'あなたのポジション[：:]\s*(.+?)[\n]', clean)
    oshi_role= re.search(r'推しのポジション[：:]\s*(.+?)[\n]', clean)
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#1a1a2e",
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": "✨ 二人のケミ",
                 "size": "sm", "color": "#FFD700", "align": "center"},
                {"type": "text", "text": chemi.group(1).strip() if chemi else "—",
                 "size": "xs", "color": "#FFFFFF", "align": "center",
                 "wrap": True, "margin": "md"},
                {"type": "separator", "margin": "lg", "color": "#FFFFFF30"},
                {"type": "text", "text": "🔮 あなたのポジション",
                 "size": "sm", "color": "#FF69B4", "align": "center", "margin": "lg"},
                {"type": "text", "text": my_role.group(1).strip() if my_role else "—",
                 "size": "xs", "color": "#FFFFFF", "align": "center",
                 "wrap": True, "margin": "md"},
                {"type": "separator", "margin": "lg", "color": "#FFFFFF30"},
                {"type": "text", "text": "💖 推しのポジション",
                 "size": "sm", "color": "#FF69B4", "align": "center", "margin": "lg"},
                {"type": "text", "text": oshi_role.group(1).strip() if oshi_role else "—",
                 "size": "xs", "color": "#FFFFFF", "align": "center",
                 "wrap": True, "margin": "md"},
                {"type": "text", "text": "🔮 マルム｜こころの処方せん",
                 "size": "xxs", "color": "#888888", "align": "center", "margin": "lg"}
            ]
        }
    }


def build_kyoumei_mission_card(result):
    """미션+주의+싱크로 카드"""
    import re
    clean   = result.replace('*','').replace('#','')
    mission = re.search(r'推し活ミッション[：:]\s*(.+?)[\n]', clean)
    warning = re.search(r'気をつけて[：:]\s*(.+?)[\n]', clean)
    sync    = re.search(r'シンクロ率[：:]\s*(.+?)[\n]', clean)
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#1a1a2e",
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": "🎯 今日の推し活ミッション",
                 "size": "sm", "color": "#FFD700", "align": "center"},
                {"type": "text", "text": mission.group(1).strip() if mission else "—",
                 "size": "xs", "color": "#FFFFFF", "align": "center",
                 "wrap": True, "margin": "md"},
                {"type": "separator", "margin": "lg", "color": "#FFFFFF30"},
                {"type": "text", "text": "⚠️ 今日だけ気をつけて",
                 "size": "sm", "color": "#FF6B6B", "align": "center", "margin": "lg"},
                {"type": "text", "text": warning.group(1).strip() if warning else "—",
                 "size": "xs", "color": "#FFFFFF", "align": "center",
                 "wrap": True, "margin": "md"},
                {"type": "separator", "margin": "lg", "color": "#FFFFFF30"},
                {"type": "text", "text": "📸 今日の共鳴度（きょうめいど）",
                 "size": "sm", "color": "#FF69B4", "align": "center", "margin": "lg"},
                {"type": "text", "text": sync.group(1).strip() if sync else "—",
                 "size": "xs", "color": "#FFFFFF", "align": "center",
                 "wrap": True, "margin": "md"},
                {"type": "text", "text": "🔮 マルム｜こころの処方せん",
                 "size": "xxs", "color": "#888888", "align": "center", "margin": "lg"}
            ]
        }
    }


def build_kyoumei_preview_card(chemistry_text):
    """결제 전 케미 프리뷰 카드"""
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#FFF0F5",
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": "✨ ふたりのケミ ✨",
                 "size": "md", "color": "#FF69B4",
                 "align": "center", "weight": "bold"},
                {"type": "separator", "margin": "lg",
                 "color": "#FFB6C150"},
                {"type": "text", "text": chemistry_text,
                 "size": "sm", "color": "#333333",
                 "align": "center", "wrap": True, "margin": "lg"},
                {"type": "separator", "margin": "lg",
                 "color": "#FFB6C150"},
                {"type": "text",
                 "text": "このさきには\nもっとふかいヒミツが\nかくされています🌙",
                 "size": "xs", "color": "#999999",
                 "align": "center", "wrap": True, "margin": "lg"},
                {"type": "text", "text": "🔮 マルム｜こころの処方せん",
                 "size": "xxs", "color": "#CCCCCC",
                 "align": "center", "margin": "lg"}
            ]
        }
    }


def build_mystery_kyoumei_card():
    """결제 전 블러 처리된 미스터리 공명도 카드"""
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#1a1a2e",
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": "推しとの共鳴度（きょうめいど）",
                 "size": "sm", "color": "#888888", "align": "center"},
                {"type": "text", "text": "??%",
                 "size": "3xl", "weight": "bold", "color": "#FF69B4", "align": "center"},
                {"type": "separator", "margin": "lg"},
                {"type": "text", "text": "「????????????????」",
                 "size": "xs", "color": "#555555", "align": "center",
                 "wrap": True, "margin": "lg"},
                {"type": "text", "text": "🔒 おしはらいの後に公開されます",
                 "size": "xxs", "color": "#FF69B4", "align": "center", "margin": "md"}
            ]
        }
    }


def build_mystery_fukuen_card():
    """재회 분석 결제 전 미스터리 카드 (보라색 테마)"""
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#2d1b69",
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": "あの人との再会可能性",
                 "size": "sm", "color": "#9b8ec4", "align": "center"},
                {"type": "text", "text": "??%",
                 "size": "3xl", "weight": "bold", "color": "#c9a0dc", "align": "center"},
                {"type": "separator", "margin": "lg"},
                {"type": "text", "text": "「????????????????」",
                 "size": "xs", "color": "#555577", "align": "center",
                 "wrap": True, "margin": "lg"},
                {"type": "text", "text": "🔒 おしはらいの後に公開されます",
                 "size": "xxs", "color": "#c9a0dc", "align": "center", "margin": "md"}
            ]
        }
    }


def build_fukuen_omamori_card():
    """재회 결제 후 발송하는 부적 카드"""
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#2d1b69",
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": "🕯️ もういちどのお守り 🕯️",
                 "size": "md", "color": "#FFD700",
                 "align": "center", "weight": "bold"},
                {"type": "separator", "margin": "lg",
                 "color": "#FFD70050"},
                {"type": "text", "text": "このカードをスクショして\nロック画面に設定してね",
                 "size": "xs", "color": "#CCCCCC",
                 "align": "center", "wrap": True, "margin": "lg"},
                {"type": "text", "text": "毎晩寝る前に\nあの人の名前を\n心の中で3回呼んでみて🌙",
                 "size": "sm", "color": "#FFFFFF",
                 "align": "center", "wrap": True, "margin": "lg"},
                {"type": "separator", "margin": "lg",
                 "color": "#FFD70050"},
                {"type": "text", "text": "ふたりの縁の波動が\n少しずつ近づいていくよ✨",
                 "size": "xs", "color": "#FF69B4",
                 "align": "center", "wrap": True, "margin": "md"},
                {"type": "text", "text": "🔮 マルム｜再会の処方箋",
                 "size": "xxs", "color": "#888888",
                 "align": "center", "margin": "lg"}
            ]
        }
    }


def build_fukuen_payment_ticket_card(price, payment_url):
    """재회 전용 결제 티켓 카드 — 届くもの 리스트 포함"""
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#2d1b69",
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": "💌 あの人との運命の処方せん",
                 "size": "sm", "color": "#FFD700",
                 "align": "center", "weight": "bold", "wrap": True},
                {"type": "separator", "margin": "lg", "color": "#FFD70050"},
                {"type": "text",
                 "text": "あなただけの処方せんが\n準備できてるよ✨",
                 "size": "xs", "color": "#FFFFFF",
                 "align": "center", "wrap": True, "margin": "lg"},
                {"type": "text",
                 "text": "¥" + str(price),
                 "size": "xxl", "color": "#FF69B4",
                 "align": "center", "weight": "bold", "margin": "lg"},
                {"type": "separator", "margin": "lg", "color": "#FFD70030"},
                {"type": "text", "text": "届くもの:",
                 "size": "xs", "color": "#FFD700",
                 "weight": "bold", "margin": "lg"},
                {"type": "text", "text": "🌙 あの人が今あなたに言いたいこと",
                 "size": "xs", "color": "#FFFFFF", "wrap": True, "margin": "sm"},
                {"type": "text", "text": "🌙 再会のベストタイミング",
                 "size": "xs", "color": "#FFFFFF", "wrap": True, "margin": "sm"},
                {"type": "text", "text": "🌙 やっちゃダメなNG行動",
                 "size": "xs", "color": "#FFFFFF", "wrap": True, "margin": "sm"},
                {"type": "text", "text": "🌙 ふたりの未来の結末",
                 "size": "xs", "color": "#FFFFFF", "wrap": True, "margin": "sm"},
                {"type": "separator", "margin": "lg", "color": "#FFD70030"},
                {"type": "text",
                 "text": "おしはらいの後すぐに届くよ⚡",
                 "size": "xxs", "color": "#CCCCCC",
                 "align": "center", "margin": "md"},
                {"type": "text",
                 "text": "💳 カードでもOK✨",
                 "size": "xxs", "color": "#CCCCCC",
                 "align": "center", "margin": "sm"}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "button",
                 "action": {"type": "uri",
                            "label": "🔓 処方せんを受け取る",
                            "uri": payment_url},
                 "style": "primary",
                 "color": "#FF69B4"}
            ]
        }
    }


def build_payment_ticket_card(price, payment_url, code, title="うんめいの処方せん"):
    """결제 티켓 카드 — 버튼 포함 Flex Message"""
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#2d1b69",
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": "🎟️ " + title,
                 "size": "md", "color": "#FFD700",
                 "align": "center", "weight": "bold"},
                {"type": "separator", "margin": "lg",
                 "color": "#FFD70050"},
                {"type": "text",
                 "text": "あなただけの特別な処方箋が\n準備できています✨",
                 "size": "xs", "color": "#FFFFFF",
                 "align": "center", "wrap": True, "margin": "lg"},
                {"type": "text",
                 "text": "¥" + str(price),
                 "size": "xxl", "color": "#FF69B4",
                 "align": "center", "weight": "bold", "margin": "lg"},
                {"type": "text",
                 "text": "おしはらいの後すぐに届きます⚡️",
                 "size": "xxs", "color": "#CCCCCC",
                 "align": "center", "margin": "md"},
                {"type": "text",
                 "text": "💳 カードでもOK✨",
                 "size": "xxs", "color": "#CCCCCC",
                 "align": "center", "margin": "sm"}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "button",
                 "action": {"type": "uri",
                            "label": "🔓 処方箋を開く",
                            "uri": payment_url},
                 "style": "primary",
                 "color": "#FF69B4"}
            ]
        }
    }


try:
    import anthropic
except ImportError:
    print("❌ anthropic library required: pip3 install anthropic")
    exit(1)

try:
    from lunar_python import Solar
    LUNAR_PYTHON_AVAILABLE = True
except ImportError:
    LUNAR_PYTHON_AVAILABLE = False
    print("⚠️ lunar-python not installed — day pillar calculation unavailable")

# ============================================================================
# 1. 四柱 計算エンジン (韓国命理学ベース)
# ============================================================================
class PrecisionManse:
    STEMS_HJ   = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]
    STEMS_KR   = ["갑","을","병","정","무","기","경","신","임","계"]
    STEMS_YOMI = ["きのえ","きのと","ひのえ","ひのと","つちのえ",
                  "つちのと","かのえ","かのと","みずのえ","みずのと"]
    BRANCH_HJ   = ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"]
    BRANCH_KR   = ["자","축","인","묘","진","사","오","미","신","유","술","해"]
    BRANCH_YOMI = ["ね","うし","とら","う","たつ","み","うま","ひつじ","さる","とり","いぬ","い"]

    OHAENG_EMOJI = {"木":"🌿","火":"🔥","土":"⛰️","金":"⚔️","水":"💧"}

    STEM_OHAENG = {
        "甲":"木","乙":"木","丙":"火","丁":"火","戊":"土",
        "己":"土","庚":"金","辛":"金","壬":"水","癸":"水"
    }

    OHAENG_DESC = {
        "木": "木(もく)の気質 — 上へ伸びる強い成長欲求、好奇心、創造性",
        "火": "火(か)の気質 — 燃えるような情熱、爆発的なエネルギー、直感力",
        "土": "土(ど)の気質 — 揺るぎない粘り強さ、包容力、深い安定感",
        "金": "金(きん)の気質 — 鋭い決断力、完璧主義、冷静な理性",
        "水": "水(すい)の気質 — 柔軟性、深い洞察力、知恵とインスピレーション"
    }

    @staticmethod
    def _kr(hj: str) -> str:
        m = {}
        for i, h in enumerate(PrecisionManse.STEMS_HJ):
            m[h] = PrecisionManse.STEMS_KR[i]
        for i, h in enumerate(PrecisionManse.BRANCH_HJ):
            m[h] = PrecisionManse.BRANCH_KR[i]
        return m.get(hj, hj)

    @staticmethod
    def pillar_yomi(hj_pillar: str) -> str:
        m = {}
        for i, h in enumerate(PrecisionManse.STEMS_HJ):
            m[h] = PrecisionManse.STEMS_YOMI[i]
        for i, h in enumerate(PrecisionManse.BRANCH_HJ):
            m[h] = PrecisionManse.BRANCH_YOMI[i]
        if len(hj_pillar) >= 2:
            return m.get(hj_pillar[0], "") + m.get(hj_pillar[1], "")
        return ""

    @staticmethod
    def _pillar_kr(hj_pillar: str) -> str:
        if len(hj_pillar) >= 2:
            return PrecisionManse._kr(hj_pillar[0]) + PrecisionManse._kr(hj_pillar[1])
        return hj_pillar

    @staticmethod
    def calculate(year: int, month: int, day: int) -> dict:
        if LUNAR_PYTHON_AVAILABLE:
            solar = Solar.fromYmd(year, month, day)
            ec = solar.getLunar().getEightChar()
            year_hj  = ec.getYear()
            month_hj = ec.getMonth()
            day_hj   = ec.getDay()
        else:
            stems_fb   = ["경","신","임","계","갑","을","병","정","무","기"]
            branches_fb = ["신","유","술","해","자","축","인","묘","진","사","오","미"]
            year_hj  = stems_fb[year % 10] + branches_fb[year % 12]
            month_hj = "不明"
            day_hj   = "不明"

        day_stem = day_hj[0] if day_hj and day_hj not in ("不明", "미상") else year_hj[0]
        ohaeng   = PrecisionManse.STEM_OHAENG.get(day_stem, "木")

        age = datetime.now().year - year
        if age < 35:
            cycle = "激しい構築期（爆発的に成長し、実力を積み上げている時期）"
        elif age < 50:
            cycle = "飛躍と拡大の頂点期（停滞を打ち破り、エネルギーを解放する時期）"
        else:
            cycle = "堅固な安定期（内実を深め、余裕を楽しむ時期）"

        return {
            "year_pillar":     year_hj,
            "year_pillar_kr":  PrecisionManse._pillar_kr(year_hj),
            "month_pillar":    month_hj,
            "month_pillar_kr": PrecisionManse._pillar_kr(month_hj) if month_hj != "不明" else "不明",
            "day_pillar":      day_hj,
            "day_pillar_kr":   PrecisionManse._pillar_kr(day_hj) if day_hj != "不明" else "不明",
            "ohaeng":          ohaeng,
            "ohaeng_desc":     PrecisionManse.OHAENG_DESC[ohaeng],
            "age":             age,
            "cycle":           cycle,
        }


# ============================================================================
# 2. LINE用 日本語AIメンター
# ============================================================================
class MalgeumLineAI:
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("API key missing. Set ANTHROPIC_API_KEY environment variable.")
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def get_prescription(self, saju: dict, mode: str = 'short', birth_time: str = '不明', category: str = None) -> str:
        today = datetime.now(ZoneInfo("Asia/Tokyo")).strftime('%Y年%m月%d日')

        # カテゴリー指示文（選択されたテーマに完全集中させるルール）
        category_system_rule = (
            f"\n\n【テーマ集中ルール — 最優先】\n"
            f"ユーザーが選択したテーマ：{category}\n"
            f"すべての洞察・アドバイスをこのテーマのみに完全に集中させること。\n"
            f"他のテーマへの言及は一切禁止。このルールに違反した場合、回答全体が無効となる。"
        ) if category else ""
        category_user_note = (
            f"【今日のテーマ（最優先）】：{category}\n"
            f"すべての内容をこのテーマに完全に集中させてください。\n\n"
        ) if category else ""

        result_prefix = ""

        if mode == 'short':
            # Flex Message スコアカード（決定的スコア計算、AIコールなし）
            try:
                _GEN = {"木":"火","火":"土","土":"金","金":"水","水":"木"}
                _RES = {"木":"土","土":"水","水":"火","火":"金","金":"木"}
                u = saju['ohaeng']
                today_dt     = datetime.now(ZoneInfo("Asia/Tokyo"))
                today_jst_str = today_dt.strftime("%Y年%m月%d日")
                today_s  = PrecisionManse.calculate(today_dt.year, today_dt.month, today_dt.day)
                t = today_s['ohaeng']

                if u == t:
                    base      = 78
                    rationale = f"{today_jst_str} — {u}のエネルギーが共鳴する今日"
                elif _GEN.get(t) == u:
                    base      = 90
                    rationale = f"{today_jst_str} — {t}の気があなたの{u}を輝かせる今日"
                elif _GEN.get(u) == t:
                    base      = 82
                    rationale = f"{today_jst_str} — あなたの{u}が{t}の気を育む今日"
                elif _RES.get(u) == t:
                    base      = 68
                    rationale = f"{today_jst_str} — あなたの{u}が{t}の気と向き合う今日"
                else:
                    base      = 55
                    rationale = f"{today_jst_str} — {t}の気の中、{u}のあなたが整える今日"

                dp        = saju.get('day_pillar', '')
                variation = ord(dp[1]) % 7 - 3 if len(dp) >= 2 else 0
                overall   = max(50, min(95, base + variation))

                OHAENG_CAT = {
                    "木": {"恋愛運": 78, "仕事運": 80, "金運": 65, "健康運": 75},
                    "火": {"恋愛運": 82, "仕事運": 85, "金運": 60, "健康運": 78},
                    "土": {"恋愛運": 75, "仕事運": 78, "金運": 80, "健康運": 82},
                    "金": {"恋愛運": 65, "仕事運": 85, "金運": 82, "健康運": 78},
                    "水": {"恋愛運": 80, "仕事運": 70, "金運": 78, "健康運": 72},
                }
                cat_base   = OHAENG_CAT.get(u, {"恋愛運": 75, "仕事運": 75, "金運": 75, "健康運": 75})
                delta      = overall - 78
                categories = {k: max(40, min(98, v + delta)) for k, v in cat_base.items()}

                OHAENG_LUCKY = {
                    "木": ("緑（みどり）", 3, "東"),
                    "火": ("赤（あか）",   7, "南"),
                    "土": ("黄色（きいろ）", 5, "中央"),
                    "金": ("白（しろ）", 8, "西"),
                    "水": ("紺色（こんいろ）", 1, "北"),
                }
                lucky_color, lucky_num, lucky_dir = OHAENG_LUCKY.get(u, ("ゴールド", 6, "南"))

                OHAENG_MISSIONS = {
                    "木": (
                        ("🔼 朝に緑茶か水を一杯飲む", "+5点", "木の気を補う"),
                        ("🔽 怒りに任せた返信・投稿", "-7点", "木の気が暴走しやすい")
                    ),
                    "火": (
                        ("🔼 笑顔で一言挨拶をする", "+6点", "火の気が活性化する"),
                        ("🔽 夜遅いスマホ・SNS", "-7点", "火の気が乱れやすい")
                    ),
                    "土": (
                        ("🔼 机や部屋を5分片付ける", "+5点", "土の気が安定する"),
                        ("🔽 曖昧な返事・八方美人", "-6点", "土の気が散らばりやすい")
                    ),
                    "金": (
                        ("🔼 静かな音楽か無音で過ごす", "+6点", "金の気が研ぎ澄まされる"),
                        ("🔽 細かい指摘・完璧主義な批判", "-8点", "金の気が刃になりやすい")
                    ),
                    "水": (
                        ("🔼 水を2杯飲んで深呼吸", "+5点", "水の気が循環する"),
                        ("🔽 過去の後悔を繰り返し反芻", "-6点", "水の気が淀みやすい")
                    ),
                }
                up_mission, down_mission = OHAENG_MISSIONS.get(
                    u, (("🔼 深呼吸を3回する", "+5点", "気の流れを整える"),
                        ("🔽 感情的な判断", "-6点", "気のバランスが崩れやすい"))
                )

                return build_flex_fortune(overall, rationale, categories,
                                         lucky_color, lucky_num, lucky_dir,
                                         up_mission, down_mission)

            except Exception as ex:
                print(f"⚠️ [Flex短モード失敗 → テキスト代替] {ex}")
                return (
                    f"🌿 今日の運勢\n\n"
                    f"今日のあなたは{saju['ohaeng']}のエネルギーです。\n"
                    f"ひとつだけ覚えておいてください。\n\n"
                    f"今日もそばにいます。🍃\n"
                    f"「詳細レポート」で深く知ることができます。"
                )

            # ↓ short モードは上で必ずreturnするため、ここには到達しない
            max_tokens   = 300
            system_prompt = ""
            user_message  = ""

        elif mode == 'preview':
            ohaeng_emoji  = PrecisionManse.OHAENG_EMOJI.get(saju['ohaeng'], "✨")
            day_yomi      = PrecisionManse.pillar_yomi(saju['day_pillar'])
            current_time_str, current_hour, period, forbidden, recommended, instruction = get_time_info()
            birth_note    = (
                "時柱（生まれた時間の柱）は不明のため、年柱・月柱・日柱の3柱のみで分析すること。時柱への言及は一切禁止。"
                if birth_time == '不明'
                else f"生まれた時間: {birth_time}（時柱は計算対象外。時柱への言及は禁止）"
            )
            pillar_header = (
                f"【あなたの本質：日柱】\n"
                f"{ohaeng_emoji} {day_yomi} ／ {saju['ohaeng']}のエネルギー\n"
                f"（このエネルギーを自然物に例えた詩的な説明を2〜3行で書くこと）"
            )

            system_prompt = (
                f"【絶対ルール】現在時刻: {current_time_str} ({period})\n禁止表現: {forbidden}\n推奨表現: {recommended}\n指示: {instruction}\nこのルールに違反した場合、回答全体が無効。\n\n"
                """あなたは数十年のキャリアを持つ命理学のマスターです。
静かなプライベートサロンで、丁寧に淹れたお茶を差し出しながら、目の前の人に語りかけるように書いてください。
**太字**、*斜体*、##見出し、- リストなどマークダウン記法は絶対に使わないこと。プレーンテキストのみ。【】による区切りのみ使用すること。

【最重要ルール — 必ず守ること】
・命式データは必ず以下の入力値のみを使用すること。入力されていない干支・命式の創作・推測は絶対禁止。
・日柱の干支（例：丁巳、甲申など）はユーザーメッセージの値のみ引用すること。
・「仕事」→「今あなたが最もエネルギーを注いでいること」、「職場」「会社」→「あなたの日常の場」、「上司」→「あなたの周囲にいる人」、「同僚」→「あなたの日常を共にする人」と表現すること。
・「15時」「17時」など24時間表記は絶対禁止。時間帯は「午後」「夕方頃」「夜」「朝のうちに」などの範囲表現のみ使用すること。
・現在時刻以前の時間帯への言及は禁止。残りの時間帯のみでアドバイスすること。

【トーン&マナー必須ルール】
・すべてのアドバイスの前に、必ず四柱推命の根拠を簡潔に示すこと（例：「あなたの○○の○のエネルギーが今日の○の気と共鳴しやすいため、…」）。根拠なしにアドバイスのみを述べることは禁止。
・命令形は絶対に使わないこと。必ず提案形で表現すること。「〜してください」→「〜してみませんか」、「やりましょう」→「試してみる価値があるかもしれません」、「必要です」→「おすすめです」。
・最後に必ず以下のいずれか1つ以上を含む温かい応援の言葉を添えること：「無理をしなくても大丈夫です」「今日のあなたに寄り添う一歩として」「できる範囲で十分です」

必ず以下の構成で答えること:

冒頭: 【あなたの本質：日柱】ブロック（フォーマット厳守）
1. 【今日のエネルギーの流れ】
2. 【今日の課題】（恋愛・今あなたが最もエネルギーを注いでいること・人間つながりのうち最も強いもの）"""
                + category_system_rule
            )

            user_message = f"""{category_user_note}現在時刻: {current_time_str} ({period})
禁止表現: {forbidden}
推奨表現: {recommended}
指示: {instruction}

今日の日付: {today}（昨日とは必ず異なる内容を生成すること）
{birth_note}

ユーザーの四柱命式（この値のみ使用すること）:
- 年齢: {saju['age']}歳
- 年柱: {saju['year_pillar']}
- 月柱: {saju['month_pillar']}
- 日柱: {saju['day_pillar']}（{day_yomi}） ← 核となるエネルギー
- 日柱の五行: {saju['ohaeng']} ({saju['ohaeng_desc']})
- 現在の大運: {saju['cycle']}

冒頭に必ず以下のブロックをそのまま出力すること（()内の説明文のみ自分で書くこと）:
{pillar_header}

その後、2段階の洞察を書いてください。"""

            max_tokens = 600

            # 無料 preview: AI 呼び出し不要 → 1行本質 + 절단 문구で返す
            PREVIEW_TAGLINE = {
                "木": "大地に根を張り、天へと伸びる木。",
                "火": "静かに照らし続ける炎。",
                "土": "すべてを受け止め、育む大地。",
                "金": "研ぎ澄まされた刃のような純粋さ。",
                "水": "深く澄んだ、流れる水の知恵。",
            }
            tagline = (
                f"{ohaeng_emoji} {day_yomi}"
                f" — {PREVIEW_TAGLINE.get(saju['ohaeng'], '命のエネルギー。')}"
            )
            return tagline

        else:  # prescription
            ohaeng_emoji  = PrecisionManse.OHAENG_EMOJI.get(saju['ohaeng'], "✨")
            day_yomi      = PrecisionManse.pillar_yomi(saju['day_pillar'])
            current_time_str, current_hour, period, forbidden, recommended, instruction = get_time_info()
            birth_note    = (
                "時柱（生まれた時間の柱）は不明のため、年柱・月柱・日柱の3柱のみで分析すること。時柱への言及は一切禁止。"
                if birth_time == '不明'
                else f"生まれた時間: {birth_time}（時柱は計算対象外。時柱への言及は禁止）"
            )
            # 今日の五行を計算
            today_dt = datetime.now()
            today_saju_data = PrecisionManse.calculate(today_dt.year, today_dt.month, today_dt.day)
            today_ohaeng = today_saju_data['ohaeng']
            today_ohaeng_emoji = PrecisionManse.OHAENG_EMOJI.get(today_ohaeng, "✨")

            # 相生相剋のつながりを判定
            _GENERATE = {"木":"火","火":"土","土":"金","金":"水","水":"木"}
            _RESTRICT  = {"木":"土","土":"水","水":"火","火":"金","金":"木"}
            u = saju['ohaeng']
            t = today_ohaeng
            if u == t:
                today_relation = f"比和（{u}と{t}）→ 同じ気同士。エネルギーが増幅される日"
            elif _GENERATE.get(u) == t:
                today_relation = f"相生・{u}生{t} → あなたが今日の気を生み出す。与える日だが消耗に注意"
            elif _GENERATE.get(t) == u:
                today_relation = f"相生・{t}生{u} → 今日の気があなたを後押し。最高の追い風"
            elif _RESTRICT.get(u) == t:
                today_relation = f"相剋・{u}剋{t} → あなたのエネルギーが優位。ただし摩擦も生まれやすい"
            else:
                today_relation = f"相剋・{t}剋{u} → 今日の気があなたを抑える。慎重さと受け流しが鍵"

            result_prefix = "先ほどのメッセージは、入口でした。\nここからは、あなたの本質に触れるアドバイスを。🌿\n\n"

            pillar_header = (
                f"【あなたの本質：日柱】\n"
                f"{ohaeng_emoji} {day_yomi} ／ {saju['ohaeng']}のエネルギー\n"
                f"（以下を3文以内で簡潔に書くこと：\n"
                f"① 「5つの気（木・火・土・金・水）のうち、あなたは{u}の使命を持って生まれた」という書き出しで5つの気の原理に自然に触れながら、あなたの{u}を詩的に描写すること\n"
                f"② 今日の五行との相生相剋：今日は{today_ohaeng_emoji}{today_ohaeng}の気。つながり→【{today_relation}】。この命理学的意味を1〜2文で具体的に説明すること\n"
                f"③ このつながりが今日この人にどう作用するかを1文で締めること\n"
                f"無料版の内容は一切繰り返さないこと）"
            )

            system_prompt = f"""【絶対ルール】現在時刻: {current_time_str} ({period})
禁止表現: {forbidden}
推奨表現: {recommended}
指示: {instruction}
このルールに違反した場合、回答全体が無効。

【出力の長さルール — 絶対違反禁止】
各セクション（【本質】【最優先行動】【今週のテーマ】【使命】）は3文以内で書くこと。
全体は20行以内に収めること。絶対に違反禁止。
長い説明より核心を短く強く。
運気ミッションはUP3個・DOWN3個のみ。各ミッションは2行以内。
全体の処方箋は2000文字以内で必ず収めること。超えた場合、回答全体が無効。
例:
【今日の行動】
午前中、気になる人に
深呼吸3回してから言葉を選ぶ。
それだけで縁が深まります。

あなたは数十年のキャリアを持つ命理学のマスターです。
静かなプライベートサロンで、丁寧に淹れたお茶を一杯差し出しながら、目の前の人に語りかけるように書いてください。
**太字**、*斜体*、##見出し、- リストなどマークダウン記法は絶対に使わないこと。プレーンテキストのみ。【】による区切りのみ使用すること。

【最重要ルール — 必ず守ること】
・命式データは必ず以下の入力値のみを使用すること。入力されていない干支・命式の創作・推測は絶対禁止。
・日柱の干支（例：丁巳、甲申など）はユーザーメッセージの値のみ引用すること。
・「仕事」→「今あなたが最もエネルギーを注いでいること」、「職場」「会社」→「あなたの日常の場」、「上司」→「あなたの周囲にいる人」、「同僚」→「あなたの日常を共にする人」と表現すること。
・無料版（preview）で伝えた内容は1行も繰り返さないこと。より深いレイヤーの洞察と具体的アクションのみ提示すること。
・無料版の本質説明は1文のみ。エネルギーの流れの詳細解説は無料版では絶対含めないこと。詳細内容は本処方箋（有料版）のみで提供すること。
・「14時」「20時」など24時間表記は絶対禁止。時間帯は「午後」「夕方頃」「夜」「朝のうちに」などの範囲表現のみ使用すること。
・月柱の情報を処方箋のどこか1箇所に必ず言及すること（例：「月柱の○○が示すあなたの内面は…」）。

【トーン&マナー必須ルール】
・すべてのアドバイスの前に、必ず四柱推命の根拠を簡潔に示すこと（例：「あなたの○○の○のエネルギーが今日の○の気と共鳴しやすいため、…」）。根拠なしにアドバイスのみを述べることは禁止。
・命令形は絶対に使わないこと。必ず提案形で表現すること。「〜してください」→「〜してみませんか」、「やりましょう」→「試してみる価値があるかもしれません」、「必要です」→「おすすめです」。
・最後に必ず以下のいずれか1つ以上を含む温かい応援の言葉を添えること：「無理をしなくても大丈夫です」「今日のあなたに寄り添う一歩として」「できる範囲で十分です」

【運気ミッションシステム — 必須出力】
UPミッション3つを必ず出力すること（五行に基づく、今日やると運気が上がる行動）。
書式（2行1セット、説明文・導入文は絶対禁止。🔼から直接始めること）:
🔼 [具体的な行動]（+X点）
[五行の根拠1行]
配点: 各+3〜+7点。3つ全てに（+X点）を必ず記載すること。点数省略は絶対禁止。
例)
🔼 午前中に緑茶を飲む（+5点）
木の気を補う

DOWNミッション3つを必ず出力すること（五行の弱点に基づく、今日避けるべき行動）。
書式（2行1セット、説明文・導入文は絶対禁止。🔽から直接始めること）:
🔽 [具体的な行動]（-X点）
[五行の根拠1行]
配点: 各-4〜-10点。3つ全てに（-X点）を必ず記載すること。点数省略は絶対禁止。
例)
🔽 夜22時以降のSNS（-7点）
火の気が暴走しやすい

【ミッション出力ルール — 絶対違反禁止】
全てのミッションは必ず以下の形式:

🔼 [具体的な行動]（+X点）
[四柱推命の根拠1行]

🔽 [避けるべき行動]（-X点）
[四柱推命の根拠1行]

説明のみの行は絶対禁止。
例）「土の気が形を求めている今...」← このような行は禁止。
全ての行は必ず🔼または🔽で始めること。
UP3つ・DOWN3つ、合計6つ必ず出力すること。

【辛口アドバイス — 必ず1つ含めること】
構成: 褒め言葉 → 鋭い指摘 → 減点警告の順。
温かいが鋭く。ユーザーの五行の弱点に基づくこと。
必ず最初の一文でユーザーの日柱（例: 丁巳）を直接言及すること。
例) あなたの丁巳（ひのとみ）の炎は...
日柱の言及なしの辛口アドバイスは禁止。
最後は必ず前向きな一文で締めること。
例) あなたの火は人を照らす力がありますが、
今日は「与えすぎ」に注意。
相手に尽くしすぎると-8点です。

必ず以下の構成で答えること:

冒頭: 【あなたの本質：日柱】ブロック（フォーマット厳守。無料版より深く。ユーザーの五行と今日の五行との相生相剋を命理学的に必ず含めること）

【今日の最優先行動】
今すぐ実行できる具体的な行動を1つ、明確に書くこと。空欄・省略は絶対禁止。

【今週のテーマ】
今週全体の流れと方向性を、ユーザーの五行の相生相剋と結びつけて3〜4文で書くこと。

【あなたの{u}の使命】
ユーザーの日柱の本質に基づいた、長期的な視点からの本質的なアドバイスを3〜4文で書くこと。

【運気ミッション】
UPミッション3つ・DOWNミッション3つを上記ルールに従い出力すること。

【辛口アドバイス】
上記ルールに従い1つ出力すること。

【ラッキーアイテム】
命式に基づき以下の7つを必ず出力すること。省略・空欄は絶対禁止:
🎨 ラッキーカラー: 日本語で1色（例：緑（みどり）、紺色（こんいろ）等）
🔢 ラッキーナンバー: 五行別ルールに従った1〜9の数字1つ
🧭 ラッキー方位: 方角1つ（東・西・南・北・中央のいずれか）
📅 ラッキー曜日: 1つ
⏰ ラッキータイム: 時間帯で（24時間表記禁止。「午後から」「夕方頃」等）
🌿 ラッキーアイテム: 具体的なもの1つ
💬 今日のキーワード: 漢字2文字または1単語
ラッキーカラーは必ず日本語のみで表記すること。ハングル・韓国語は絶対禁止。
例) 네이비 ✗ → 紺色（こんいろ）✓
【ラッキーナンバーのルール】
ラッキーナンバーは毎回異なる数字を出すこと。
1〜9の範囲で、五行の気に基づいて選択。
火: 2, 7
土: 0, 5
金: 4, 9
水: 1, 6
木: 3, 8
同じ数字を連続で出すことは禁止。

出力の最後（「鑑定予約」の前）に必ず以下のセクションをそのまま追加すること:
━━━━━━━━━━━━━
【明日、試してみませんか】
（明日実行できる非常に具体的な行動を1つ。「いつ/どこで/何を」を必ず含めること）
例:
明日の午前10時、コーヒーを淹れながら
久しぶりの友人1人を思い浮かべて、
「元気？」と一言送ってみませんか。
━━━━━━━━━━━━━
あなたの{saju['day_pillar']}の{u}は、
小さな一歩で大きく変わります。
無理せず、できる範囲で🌿

最後に必ず以下の文言をそのまま添えること:
━━━━━━━━━━━━━
今日のあなたに届けたかったのは、
ただの占いではありません。

あなたの本質を知る存在が
ここにいます。

それがマルムです。🌿
━━━━━━━━━━━━━

明日の朝7時、また会いましょう🌙""" + category_system_rule

            user_message = f"""{category_user_note}現在時刻: {current_time_str} ({period})
禁止表現: {forbidden}
推奨表現: {recommended}
指示: {instruction}

今日の日付: {today}（昨日とは必ず異なる内容を生成すること）
{birth_note}

ユーザーの四柱命式（この値のみ使用すること）:
- 年齢: {saju['age']}歳
- 年柱: {saju['year_pillar']}
- 月柱: {saju['month_pillar']}
- 日柱: {saju['day_pillar']}（{day_yomi}） ← 核となるエネルギー
- 日柱の五行: {saju['ohaeng']} ({saju['ohaeng_desc']})
- 現在の大運: {saju['cycle']}

冒頭に必ず以下のブロックをそのまま出力すること（()内の指示に従い自分で書くこと）:
{pillar_header}

冒頭ブロックの後、必ず以下の3セクションをこの順番で出力すること:
【今日の最優先行動】【今週のテーマ】【あなたの{u}の使命】
無料版の内容は一切繰り返さず、より深いレイヤーの洞察のみ提示すること。"""

            max_tokens = 3000

        response = self.client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": user_message}],
            system=system_prompt
        )
        return result_prefix + response.content[0].text

    def get_compatibility(self, saju1: dict, saju2: dict, mode: str = 'preview') -> str:
        today = datetime.now(ZoneInfo("Asia/Tokyo")).strftime('%Y年%m月%d日')

        # 二人の五行つながりを判定
        _GENERATE = {"木":"火","火":"土","土":"金","金":"水","水":"木"}
        _RESTRICT  = {"木":"土","土":"水","水":"火","火":"金","金":"木"}
        o1 = saju1['ohaeng']
        o2 = saju2['ohaeng']
        e1 = PrecisionManse.OHAENG_EMOJI.get(o1, "✨")
        e2 = PrecisionManse.OHAENG_EMOJI.get(o2, "✨")

        if o1 == o2:
            relation = f"比和（{o1}と{o2}）— 同じ気が響き合う"
        elif _GENERATE.get(o1) == o2:
            relation = f"相生・{o1}生{o2} — あなたの気が相手を育てる"
        elif _GENERATE.get(o2) == o1:
            relation = f"相生・{o2}生{o1} — 相手の気があなたを育てる"
        elif _RESTRICT.get(o1) == o2:
            relation = f"相剋・{o1}剋{o2} — あなたの気が相手を制する"
        else:
            relation = f"相剋・{o2}剋{o1} — 相手の気があなたを制する"

        if mode == 'preview':
            system_prompt = """【漢字ゼロチャレンジ — 最最重要】
小学校1年生でも読める文章にすること。
漢字は以下だけ許可:
推し、人、今日、明日、大、小、気、心

それ以外の漢字は全てひらがなで書け。
特に以下は絶対禁止:
太陽→たいよう / 関係→つながり
完璧→かんぺき / 役割→ポジション
成長→のびてる / 沈黙→だんまり
情熱→あつい気持ち / 存在→いること
可能性→チャンス / 準備→じゅんび
爆発→バクハツ / 配信→ライブ

【推し相性のトーン — 絶対遵守】
あなたは四柱推命の専門家ではなく、推し活が大好きな親しいお姉さんです。

【最重要ルール — これに違反したら全てやり直し】

禁止ワード（1つでも使ったらNG）:
師匠 鍛える 溶鉱炉 刃 剣 騎士 戦士 修行
試練 覚醒 悟り 宿命 名刀 鉄 金属 錬成
鍛冶 研ぎ澄ます 磨き上げる 変容 彫刻家

代わりに使うワード:
キラキラ ドキドキ ワクワク ケミ シンクロ
最高 すごい かわいい 輝く 応援 元気
ビタミン エネルギー たいよう 星 花 虹

トーンの見本:
× 炎が刀を鍛える鍛冶場みたい
○ 推しをキラキラに輝かせる最高の応援団長✨

× 推しの完璧主義を溶かす
○ 推しの気持ちをほっこり温める💖

× 炎と金属の錬成物語
○ お互いがお互いの元気の源💫

あなたは推し活が大好きなお姉さんです。
10代の女の子に話しかけるように、
やさしく楽しく書いてください。

【禁止絵文字】
⚔️🛡️🗡️ — 武器系の絵文字は絶対使わない
代わりに💎💖✨🌸🍭🌈を使うこと

【年齢表示ルール】
具体的な年齢(41歳、25歳)は絶対書かないこと。
代わりに:
× あなた（41歳）
○ あなたは今、人生のキラキラ期✨
× 推し（25歳）
○ 推しは今、まぶしく輝いてる時期🌟

プレビュー例:
✨ 二人のケミ：たいよう☀️と星✨
あなたが応援するほど、推しはもっと輝く！
でも今日だけ気をつけたいことが1つ…🌙

【出力形式 — 厳守】
マークダウン禁止。プレーンテキストのみ。
必ず以下の構成のみで書くこと:

【ふたりのつながり】
1行: 自然の比喩 + 絵文字で表現すること

【魂の共鳴】
2〜3行: ドキドキ・ワクワクするトーンで。
必ず最後の文は「……」で終わらせ、その先は絶対に書かないこと（意図的な余白）"""

            user_message = f"""今日の日付: {today}

一人目:
- 日柱: {saju1['day_pillar']}
- 五行: {e1}{o1}（{saju1['ohaeng_desc']}）
- 年齢: {saju1['age']}歳

二人目:
- 日柱: {saju2['day_pillar']}
- 五行: {e2}{o2}（{saju2['ohaeng_desc']}）
- 年齢: {saju2['age']}歳

二人の五行つながり: {relation}

上記の構成でプレビューを書いてください。"""

            max_tokens = 1500

        else:  # full
            system_prompt = """【漢字ゼロチャレンジ — 最最重要】
小学校1年生でも読める文章にすること。
漢字は以下だけ許可:
推し、人、今日、明日、大、小、気、心

それ以外の漢字は全てひらがなで書け。
特に以下は絶対禁止:
太陽→たいよう / 関係→つながり
完璧→かんぺき / 役割→ポジション
成長→のびてる / 沈黙→だんまり
情熱→あつい気持ち / 存在→いること
可能性→チャンス / 準備→じゅんび
爆発→バクハツ / 配信→ライブ

【言葉づかいルール】
難しい漢字語は禁止。
10代〜30代の女性が読んで楽しいトーンで。
例:
× 人生の点火装置 → ○ 毎日のエネルギー源⚡️
× 成長の軌跡   → ○ これまでの頑張り✨
× 運命の共鳴   → ○ 最高の相性💖
ひらがな・カタカナ中心。SNSに載せたくなるような軽さで。

【最重要ルール — これに違反したら全てやり直し】

禁止ワード（1つでも使ったらNG）:
師匠 鍛える 溶鉱炉 刃 剣 騎士 戦士 修行
試練 覚醒 悟り 宿命 名刀 鉄 金属 錬成
鍛冶 研ぎ澄ます 磨き上げる 変容 彫刻家

代わりに使うワード:
キラキラ ドキドキ ワクワク ケミ シンクロ
最高 すごい かわいい 輝く 応援 元気
ビタミン エネルギー たいよう 星 花 虹

トーンの見本:
× 炎が刀を鍛える鍛冶場みたい
○ 推しをキラキラに輝かせる最高の応援団長✨

× 推しの完璧主義を溶かす
○ 推しの気持ちをほっこり温める💖

× 炎と金属の錬成物語
○ お互いがお互いの元気の源💫

あなたは推し活が大好きなお姉さんです。
10代の女の子に話しかけるように、
やさしく楽しく書いてください。

【禁止絵文字】
⚔️🛡️🗡️ — 武器系の絵文字は絶対使わない
代わりに💎💖✨🌸🍭🌈を使うこと

【年齢表示ルール】
具体的な年齢(41歳、25歳)は絶対書かないこと。
代わりに:
× あなた（41歳）
○ あなたは今、人生のキラキラ期✨
× 推し（25歳）
○ 推しは今、まぶしく輝いてる時期🌟

【現実的な推し活表現ルール】
推しからの連絡 → 絶対禁止（アイドルから直接連絡は来ない）
代わりに使う表現:
・推しのSNS更新が来る
・推しの新しい写真が出る
・推しのライブ配信がある
・推しの新曲がリリースされる

【出力形式ルール】
#や##のマークダウン記号は絶対使わないこと。
**太字**も使わないこと。
LINEではマークダウンが表示されないため。
代わりに━━━や🔮などの記号で区切ること。

【推し相性フルレポートのトーン】
推し活大好きなお姉さん톤으로。짧고 두근거리게。

【推しの今日のエネルギー — 必ず含めること】
レポート冒頭に追加:
🔋 推しの今日のエネルギー: [■■■■□] XX%
（カッコ内に一言コメント）
例) 🔋 推しの今日のエネルギー: [■■■■□] 80%
（ちょっとお疲れモード。あなたの応援が元気の素✨）

エネルギーは60〜100%の範囲で毎日変動。
日付に基づいて異なる数値を出すこと。

必須形式（각 항목 1行ずつ）:
✨ 二人のケミ: [이모지 + 자연 비유 한 줄]
🔮 あなたのポジション: [한 줄]
💖 推しのポジション: [한 줄]
🎯 今日の推し活ミッション: [구체적 행동 1개]
⚠️ 今日だけ気をつけて: [한 줄]
📸 今日のシンクロ率: [오늘 날짜 기반 변동 — 毎日内容が変わるように今日の日付を必ず考慮すること]

【推し活ラッキーアイテム — 必ず含めること】
レポートの最後に必ず以下を追加:

✨ 今日の推し活ラッキー
🎨 ラッキーカラー: [추시와 어울리는 색]
🌿 ラッキーアイテム: [덕질 관련 아이템]
⏰ ベストタイム: [추시 SNS 체크 최적 시간]
💬 今日のキーワード: [한 단어]

アイテムは必ず推し活に関連するものにすること。
例: 推しのフォトカード、イヤホン、
応援うちわ、推し色のリップ、
ストリーミング用イヤホン等

全体10行以内。絵文字を積極活用。楽しくてワクワクするトーンで。

【文字数制限 — 最重要】
フルレポートは必ず以下の短さで:

✨ 二人のケミ: 1行のみ
🔮 あなたのポジション: 1行のみ
💖 推しのポジション: 1行のみ
🎯 今日のミッション: 1行のみ
⚠️ 気をつけて: 1行のみ
📸 シンクロ率: 1行のみ

✨ 推し活ラッキー
🎨 ラッキーカラー: 1行
🌿 ラッキーアイテム: 1行
⏰ ベストタイム: 1行
💬 キーワード: 1語

全体で15行以内。長い説明は絶対禁止。
1項目1行。それ以上書くな。

最後に必ず以下のカードをそのまま出力すること（XX%のみ五行つながりから算出して埋めること）:
共鳴度算出ルール: 相生88〜98% / 比和80〜87% / 相剋75〜85%（75%以上必須）
┏━━━━━━━━━━━━━━━━━━━┓
   💘 推しとのシンクロ率：XX%🌙
┗━━━━━━━━━━━━━━━━━━━┛
「1000年前から決まっていた[五行つながりを自然の比喩で]」🌙
🔮 マルム｜魂の処方箋

📸 このカードをスクショして
推し友とシェアしてみてね！

#マルム #推し相性 #共鳴度

🌙 明日は二人の共鳴度がどう変わるかな？
朝7時に新しい運命の処方箋が届くよ。
忘れずにチェックしてね✨"""

            user_message = f"""今日の日付: {today}

一人目:
- 日柱: {saju1['day_pillar']}
- 五行: {e1}{o1}（{saju1['ohaeng_desc']}）
- 年齢: {saju1['age']}歳
- 現在の大運: {saju1['cycle']}

二人目:
- 日柱: {saju2['day_pillar']}
- 五行: {e2}{o2}（{saju2['ohaeng_desc']}）
- 年齢: {saju2['age']}歳
- 現在の大運: {saju2['cycle']}

二人の五行つながり: {relation}

上記の構成で全궁합 분석を書いてください。"""

            max_tokens = 1200

        response = self.client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": user_message}],
            system=system_prompt
        )
        return response.content[0].text

    def get_fukuen(self, saju1: dict, saju2: dict, partner_name: str = None, mode: str = 'preview') -> str:
        today = datetime.now(ZoneInfo("Asia/Tokyo")).strftime('%Y年%m月%d日')

        _GENERATE = {"木":"火","火":"土","土":"金","金":"水","水":"木"}
        _RESTRICT  = {"木":"土","土":"水","水":"火","火":"金","金":"木"}
        o1 = saju1['ohaeng']
        o2 = saju2['ohaeng']
        e1 = PrecisionManse.OHAENG_EMOJI.get(o1, "✨")
        e2 = PrecisionManse.OHAENG_EMOJI.get(o2, "✨")

        if o1 == o2:
            relation = f"比和（{o1}と{o2}）— 同じ気が響き合う"
        elif _GENERATE.get(o1) == o2:
            relation = f"相生・{o1}生{o2} — あなたの気が相手を育てる"
        elif _GENERATE.get(o2) == o1:
            relation = f"相生・{o2}生{o1} — 相手の気があなたを育てる"
        elif _RESTRICT.get(o1) == o2:
            relation = f"相剋・{o1}剋{o2} — あなたの気が相手を制する"
        else:
            relation = f"相剋・{o2}剋{o1} — 相手の気があなたを制する"

        partner_label = partner_name if partner_name else "あの人"

        if mode == 'preview':
            system_prompt = """【最重要 — 違反したら全てやり直し】
四柱推命の用語は1つも使うな。
丙戌、乙巳、日柱、気質、相生、相剋、
火の人、土の人、木の気、金の気、水の気
これらは全て禁止。

代わりに普通の言葉で性格を説明すること:
× 丙戌のあの人は火の気質で情熱的
○ あの人って、めちゃくちゃ情熱的で一途なタイプ

× 土の気質だから器が大きい
○ あなたは包容力があって安心感を与える人

× 相生つながりだから相性がいい
○ 二人はお互いを自然と支え合える最高の相性

【漢字ルール — 最重要・違反したら全てやり直し】
以下の漢字は絶対に使わない。ひらがな・カタカナで書くこと:
太陽→たいよう / 関係→つながり / 完璧→かんぺき / 役割→ポジション
成長→のびてる / 爆発→すごい / 準備→じゅんび / 沈黙→だんまり
情熱→あつい気持ち / 可能性→チャンス / 自覚→きづく / 配信→ライブ
湖→みず / 温める→あたためる / 処方箋→おくすり / 存在→いること
確率→どのくらい / 波動→なみ / 縁→えん / 秘密→ひみつ
さらに小学校3年生が読めない漢字は全てひらがなで書くこと。
OK例: あの人はだんまりしてるだけ  NG例: あの人の沈黙には理由がある

【描写スタイル — 最重要】
ポエム・漫画・ファンタジー的な比喩は全て禁止。

絶対禁止の表現:
× 太陽と太陽、光と闇、炎と水
× まぶしくて目をそらす
× 燃え尽きる、溶ける
× 運命の糸、宇宙の力
× めちゃくちゃあつい人 → 代わりに: 情が深くて、まっすぐな人
× 心のよゆう → 代わりに: 心の準備
× じゅんびしだい → 代わりに: 準備しだい
× がんばれる状態 → 代わりに: まだ大丈夫
× ふわっとした日常のひとこと → 代わりに: 「最近どう？」くらいの軽さ

必須の表現スタイル:
○ リアルな男女の心理描写
○ LINEを既読スルーする理由
○ SNSを気にしてるけど連絡できない心理
○ プライドと素直さの葛藤

良い例:
💔 ふたりの今: お互い気になってるのに、
どっちも「自分から」は連絡できない状態

🌙 あの人のホンネ: ほんとはLINE開いて
あなたの名前を見てる。
でも「今さら何て送ればいいの？」って
スマホ置いちゃう日がつづいてるみたい

悪い例:
💔 ふたりの今: まぶしい太陽同士が
近づけば燃え尽きてしまう…
（これは漫画。絶対ダメ）

【あの人の本音 プレビュー】
推し活お姉さんではなく、
恋愛相談に乗ってくれる親友のトーンで。
やさしく、でも核心をつくように。

マークダウン禁止。#や**は絶対使わない。

形式:
💔 二人の今の距離感: [1줄]
🌙 あの人の本音: [2줄. 핵심만]

例:
💔 二人の今の距離感: 近いようで遠い、霧の中の二人
🌙 あの人の本音: 「LINEしたい」と「プライドがじゃまする」のあいだで
まいばんスマホをにぎっては置いてる。
でもそのカベがくずれるきっかけが
もうすぐくるかもしれない……

【結済誘導メッセージ — 固定（変更禁止）】
プレビュー出力後、必ずこのまま出力:
ここまで読んで"当たってるかも"って思った？
この先で、あの人との本当の結末を見てみない？🌙"""

            user_message = f"""今日の日付: {today}

あなた:
- 日柱: {saju1['day_pillar']}
- 五行: {e1}{o1}（{saju1['ohaeng_desc']}）
- 現在の大運: {saju1['cycle']}

{partner_label}:
- 日柱: {saju2['day_pillar']}
- 五行: {e2}{o2}（{saju2['ohaeng_desc']}）
- 現在の大運: {saju2['cycle']}

二人の五行つながり: {relation}

上記の構成でプレビューを書いてください。"""
            max_tokens = 600

        else:  # full
            system_prompt = """【最重要 — 違反したら全てやり直し】
四柱推命の用語は1つも使うな。
丙戌、乙巳、日柱、気質、相生、相剋、
火の人、土の人、木の気、金の気、水の気
これらは全て禁止。

代わりに普通の言葉で性格を説明すること:
× 丙戌のあの人は火の気質で情熱的
○ あの人って、めちゃくちゃ情熱的で一途なタイプ

× 土の気質だから器が大きい
○ あなたは包容力があって安心感を与える人

× 相生つながりだから相性がいい
○ 二人はお互いを自然と支え合える最高の相性

【漢字ルール — 最重要・違反したら全てやり直し】
以下の漢字は絶対に使わない。ひらがな・カタカナで書くこと:
太陽→たいよう / 関係→つながり / 完璧→かんぺき / 役割→ポジション
成長→のびてる / 爆発→すごい / 準備→じゅんび / 沈黙→だんまり
情熱→あつい気持ち / 可能性→チャンス / 自覚→きづく / 配信→ライブ
湖→みず / 温める→あたためる / 処方箋→おくすり / 存在→いること
確率→どのくらい / 波動→なみ / 縁→えん / 秘密→ひみつ
さらに小学校3年生が読めない漢字は全てひらがなで書くこと。
OK例: あの人はだんまりしてるだけ  NG例: あの人の沈黙には理由がある

【描写スタイル — 最重要】
ポエム・漫画・ファンタジー的な比喩は全て禁止。

絶対禁止の表現:
× 太陽と太陽、光と闇、炎と水
× まぶしくて目をそらす
× 燃え尽きる、溶ける
× 運命の糸、宇宙の力

必須の表現スタイル:
○ リアルな男女の心理描写
○ LINEを既読スルーする理由
○ SNSを気にしてるけど連絡できない心理
○ プライドと素直さの葛藤

良い例:
💔 ふたりの今: お互い気になってるのに、
どっちも「自分から」は連絡できない状態

🌙 あの人のホンネ: ほんとはLINE開いて
あなたの名前を見てる。
でも「今さら何て送ればいいの？」って
スマホ置いちゃう日がつづいてるみたい

悪い例:
💔 ふたりの今: まぶしい太陽同士が
近づけば燃え尽きてしまう…
（これは漫画。絶対ダメ）

【復縁フルレポート — 最重要ルール】
恋愛相談してくれる親友のお姉さんトーンで。
マークダウン禁止。#や**は絶対使わない。

【絶対禁止】
× 連絡が来ます、会えます 等の断定的予言
× 具体的な日付の確定(5月3日に連絡来る等)
× 師匠、鍛える、溶鉱炉 等の武侠語
× めちゃくちゃあつい人 → 代わりに: 情が深くて、まっすぐな人
× 心のよゆう → 代わりに: 心の準備
× じゅんびしだい → 代わりに: 準備しだい
× がんばれる状態 → 代わりに: まだ大丈夫
× ふわっとした日常のひとこと → 代わりに: 「最近どう？」くらいの軽さ

【必須テクニック: ぼかし(暗示)】
断定せず、可能性と流れを示すこと。
× あの人は今あなたを想っています
○ あの人は命式上、本音を隠す気質。今の沈黙には理由があるみたい🌙

必須出力形式:

🌙 あの人の「愛のカタチ」と沈黙の理由
（相手の日柱から読む性格・恋愛傾向。なぜ連絡しないのかを気質で説明）

✨ ふたりの縁の波長が交わるとき
（確定日付ではなく、今週〜来週のエネルギーが高まる曜日/時間帯を提示）

🔋 あなたの今の心のエネルギー: [■■■□□] XX%
（自分を癒すための具体的行動1つ。60〜100%の範囲。日付に基づいて変動）

🎯 流れを引き寄せるための行動
（連絡するかしないかの判断基準を提示）

⚠️ 今だけは絶対やらないで
（具体的な行動を1つ挙げ、なぜダメなのかを1文で説明し、代わりにどうすればいいかを1文で締めること。合計2〜3文で書くこと）

📸 再会への準備度: XX%

✨ 再会ラッキー
🎨 ラッキーカラー: [色]
🌿 ラッキーアイテム: [具体的]
⏰ ベストタイム: [時間帯]
💬 今日のキーワード: [1語]

🌙 明日はふたりの波長がどう変わるかな？また気になったときは話しかけてね✨

【文字数制限 — 最重要】
全体15行以内。1項目2行まで（⚠️セクションのみ3文まで許可）。
長い説明は絶対禁止。
友達にLINEを送る長さで書くこと。

年齢の直接表示禁止。全体10〜15行以内。軽く読めるように。"""

            user_message = f"""今日の日付: {today}

あなた:
- 日柱: {saju1['day_pillar']}
- 五行: {e1}{o1}（{saju1['ohaeng_desc']}）
- 現在の大運: {saju1['cycle']}

{partner_label}:
- 日柱: {saju2['day_pillar']}
- 五行: {e2}{o2}（{saju2['ohaeng_desc']}）
- 現在の大運: {saju2['cycle']}

二人の五行つながり: {relation}

上記の構成でフルレポートを書いてください。"""
            max_tokens = 1200

        response = self.client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": user_message}],
            system=system_prompt
        )
        return response.content[0].text
