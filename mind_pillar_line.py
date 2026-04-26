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


def build_prescription_cards(text, saju=None):
    """有料処方箋テキストから ラッキー/ミッション/辛口 の3枚カードを生成"""
    import re

    def extract(section):
        m = re.search(rf'【{re.escape(section)}】(.*?)(?=【|$)', text, re.DOTALL)
        return m.group(1).strip() if m else ""

    # ── ラッキーカード: AIテキストから全項目を抽出 ────────────────────────
    color_match     = re.search(r'ラッキーカラー[：:]\s*(.+?)[\n（\(]', text)
    number_match    = re.search(r'ラッキーナンバー[：:]\s*(\d+)', text)
    direction_match = re.search(r'ラッキー方位[：:]\s*(.+?)[\n（\(]', text)
    lc = color_match.group(1).strip()     if color_match     else "—"
    ln = number_match.group(1).strip()    if number_match    else "—"
    ld = direction_match.group(1).strip() if direction_match else "—"
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

    # ── ミッション/辛口: テキスト抽出バブル ─────────────────────
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

    return {
        "type": "carousel",
        "contents": [lucky_card, mission_card, advice_card]
    }


def build_kyoumei_card(result):
    """궁합 full 결과 텍스트에서 공명도 % 와 코멘트를 추출해 Flex 버블 생성"""
    import re
    pct_match = re.search(r'共鳴度[：:]\s*(\d+)%', result)
    pct = (pct_match.group(1) + '%') if pct_match else '—%'
    comment_match = re.search(r'「([^」\n]+)」', result)
    comment = f'「{comment_match.group(1)}」' if comment_match else '二つの魂が響き合う'
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#1a1a2e",
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": "推しとの共鳴度", "size": "sm",
                 "color": "#888888", "align": "center"},
                {"type": "text", "text": pct, "size": "3xl", "weight": "bold",
                 "color": "#FF69B4", "align": "center"},
                {"type": "separator", "margin": "lg"},
                {"type": "text", "text": comment, "size": "xs", "color": "#888888",
                 "align": "center", "wrap": True, "margin": "lg"},
                {"type": "text", "text": "🔮 あなたの共鳴のお守り🌙", "size": "xxs",
                 "color": "#aaaaaa", "align": "center", "margin": "md"}
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
        today = datetime.now().strftime('%Y年%m月%d日')

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
                f"{ohaeng_emoji} {saju['day_pillar']}（{day_yomi}）／ {saju['ohaeng']}のエネルギー\n"
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
2. 【今日の課題】（恋愛・今あなたが最もエネルギーを注いでいること・人間関係のうち最も強いもの）"""
                + category_system_rule
            )

            user_message = f"""{category_user_note}現在時刻: {current_time_str} ({period})
禁止表現: {forbidden}
推奨表現: {recommended}
指示: {instruction}

今日の日付: {today}
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
                f"{ohaeng_emoji} {saju['day_pillar']}（{day_yomi}）"
                f"— {PREVIEW_TAGLINE.get(saju['ohaeng'], '命のエネルギー。')}"
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

            # 相生相剋の関係を判定
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
                f"{ohaeng_emoji} {saju['day_pillar']}（{day_yomi}）／ {saju['ohaeng']}のエネルギー\n"
                f"（以下を4〜6行で書くこと：\n"
                f"① 「5つの気（木・火・土・金・水）のうち、あなたは{u}の使命を持って生まれた」という書き出しで5つの気の原理に自然に触れながら、あなたの{u}を詩的に描写すること\n"
                f"② 今日の五行との相生相剋：今日は{today_ohaeng_emoji}{today_ohaeng}の気。関係→【{today_relation}】。この命理学的意味を1〜2文で具体的に説明すること\n"
                f"③ この関係が今日この人にどう作用するかを1文で締めること\n"
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
この処方箋のさらに奥を知りたい方は
「鑑定予約」と入力してください。🌙""" + category_system_rule

            user_message = f"""{category_user_note}現在時刻: {current_time_str} ({period})
禁止表現: {forbidden}
推奨表現: {recommended}
指示: {instruction}

今日の日付: {today}
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
        today = datetime.now().strftime('%Y年%m月%d日')

        # 二人の五行関係を判定
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
            system_prompt = """あなたは数十年のキャリアを持つ命理学の恋愛鑑定師です。
蝋燭の灯りの下、静かに二人の命式を読み解くように書いてください。
**太字**、*斜体*、##見出し、- リストなどマークダウン記法は絶対に使わないこと。プレーンテキストのみ。【】による区切りのみ使用すること。

【トーン&マナー必須ルール】
・すべての洞察の前に、必ず五行の根拠を簡潔に示すこと。根拠なしに感想のみを述べることは禁止。
・命令形は絶対に使わないこと。必ず提案形で表現すること。
・最後に必ず温かい応援の言葉を添えること：「無理をしなくても大丈夫です」「できる範囲で十分です」のいずれか。

必ず以下の構成のみで書くこと:

【二人の気の関係】
1行: 五行の関係を詩的に表現すること

【魂の共鳴】
2〜3行: 感性的な궁합 설명。深く、詩的に。
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

二人の五行関係: {relation}

上記の構成でプレビューを書いてください。"""

            max_tokens = 400

        else:  # full
            system_prompt = """あなたは数十年のキャリアを持つ命理学の恋愛鑑定師です。
蝋燭の灯りの下、静かに二人の命式を読み解くように書いてください。
**太字**、*斜体*、##見出し、- リストなどマークダウン記法は絶対に使わないこと。プレーンテキストのみ。【】による区切りのみ使用すること。

【トーン&マナー必須ルール】
・すべての洞察の前に、必ず五行の根拠を簡潔に示すこと。根拠なしに感想のみを述べることは禁止。
・命令形は絶対に使わないこと。必ず提案形で表現すること。
・最後に必ず温かい応援の言葉を添えること：「無理をしなくても大丈夫です」「できる範囲で十分です」のいずれか。

必ず以下の構成で書くこと:

【二人の気の関係】
2〜3行: 五行の関係を詩的かつ命理学的に説明すること

【魂の共鳴】
4〜5行: 二人の感性的な絆を深く詩的に描写すること

【二人の課題と恵み】
3〜4行: この関係が持つ光と影を正直に伝えること

【今この瞬間、あなたへ】
2〜3行: 相手との関係で今最も大切にすべきことを伝えること

【共鳴度の算出ルール — 絶対遵守】
共鳴度は二人の日干の五行関係に基づいて算出すること。
毎回同じ数値を出すことは絶対禁止。

相生（木生火、火生土、土生金、金生水、水生木）: 82〜88%
比和（同じ五行同士）: 70〜76%
相剋（木剋土、土剋水、水剋火、火剋金、金剋木）: 55〜65%

各範囲内で日干の陰陽組み合わせにより±3%微調整。
同じ組み合わせでも毎回1〜2%変動させること。

【共鳴度が低い場合の対応ルール】
共鳴度60%以下の場合、必ず以下を含めること:
1. 低い理由を肯定的に説明すること
例) まだ互いの真心が届いていない成長の時期
2. 共鳴度を高める具体的行動を1つ提示すること
例) 今夜、相手の写真を見ながら赤い小物を手元に
3. 最後は必ず希望的な一文で締めること
例) この距離感こそが、やがて深い絆に変わります
共鳴度に関わらず、結果は必ず温かく前向きに締めること。

最後に必ず以下のカードをそのまま出力すること（XX%のみ命理学的に算出して埋めること）:
┏━━━━━━━━━━━━━━━━━━━┓
   💘 推しとの共鳴度：XX%🌙
┗━━━━━━━━━━━━━━━━━━━┛
「(二人の五行関係を詩的に一行で)」
🔮 マルム｜魂の処方箋"""

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

二人の五行関係: {relation}

上記の構成で全궁합 분석を書いてください。"""

            max_tokens = 1200

        response = self.client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": user_message}],
            system=system_prompt
        )
        return response.content[0].text
