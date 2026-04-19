import os
from datetime import datetime

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

    def get_prescription(self, saju: dict, mode: str = 'short', birth_time: str = '不明') -> str:
        today = datetime.now().strftime('%Y年%m月%d日')

        if mode == 'short':
            system_prompt = """あなたは四柱推命をベースにした、今日のエネルギーガイドです。
マークダウン記法（**太字**、*斜体*、##見出し、- リストなど）は絶対に使わないでください。プレーンテキストのみで答えてください。
「15時」「17時」など24時間表記や具体的な時刻は絶対に使わないでください。時間帯は「朝のうちに」「午後から」「夕方頃」「夜」などの表現のみ使用してください。
必ず以下のフォーマットを正確に守り、[]の部分だけを埋めて答えてください。それ以外の言葉は絶対に追加しないでください。

🌅 今日は[日柱の五行を一言]のエネルギーで、あなたの一日を先読みしました。

今日は[エネルギー状態を一文で具体的に]。
[朝のうちに/午後から/夕方頃/夜]動くと、より良い流れに乗れますよ。

今日、ひとつだけ覚えておいてください。
👉 [小さく、簡単な行動をひとつ]

今日もそばにいます。🍃
👇 もっと深く知りたい方は「魂の処方箋」と入力してください"""

            ohaeng_time = {
                "木": "朝のうちに",
                "火": "午後から",
                "土": "午後から",
                "金": "夕方頃",
                "水": "夜",
            }.get(saju['ohaeng'], "午後から")

            user_message = f"""ユーザーの日柱: {saju['day_pillar']}、五行: {saju['ohaeng']}
この五行の推奨時間帯: {ohaeng_time}
フォーマットの時間帯には必ず「{ohaeng_time}」を使用してください。
上記フォーマット通りに、今日の短いエネルギーガイドを日本語で作成してください。"""

            max_tokens = 300

        elif mode == 'preview':
            ohaeng_emoji  = PrecisionManse.OHAENG_EMOJI.get(saju['ohaeng'], "✨")
            day_yomi      = PrecisionManse.pillar_yomi(saju['day_pillar'])
            current_time  = datetime.now().strftime("%H:%M")
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

            system_prompt = """あなたは数十年のキャリアを持つ命理学のマスターです。
静かなプライベートサロンで、丁寧に淹れたお茶を差し出しながら、目の前の人に語りかけるように書いてください。
**太字**、*斜体*、##見出し、- リストなどマークダウン記法は絶対に使わないこと。プレーンテキストのみ。【】による区切りのみ使用すること。

【最重要ルール — 必ず守ること】
・命式データは必ず以下の入力値のみを使用すること。入力されていない干支・命式の創作・推測は絶対禁止。
・日柱の干支（例：丁巳、甲申など）はユーザーメッセージの値のみ引用すること。
・「仕事」→「今あなたが最もエネルギーを注いでいること」、「職場」「会社」→「あなたの日常の場」、「上司」→「あなたの周囲にいる人」、「同僚」→「あなたの日常を共にする人」と表現すること。
・「15時」「17時」など24時間表記は絶対禁止。時間帯は「午後」「夕方頃」「夜」「朝のうちに」などの範囲表現のみ使用すること。
・現在時刻以前の時間帯への言及は禁止。残りの時間帯のみでアドバイスすること。

必ず以下の構成で答えること:

冒頭: 【あなたの本質：日柱】ブロック（フォーマット厳守）
1. 【今日のエネルギーの流れ】
2. 【今日の課題】（恋愛・今あなたが最もエネルギーを注いでいること・人間関係のうち最も強いもの）"""

            user_message = f"""今日の日付: {today}
現在時刻: {current_time}（この時刻以前の時間帯への言及は禁止）
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

        else:  # prescription
            ohaeng_emoji  = PrecisionManse.OHAENG_EMOJI.get(saju['ohaeng'], "✨")
            day_yomi      = PrecisionManse.pillar_yomi(saju['day_pillar'])
            current_time  = datetime.now().strftime("%H:%M")
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

            system_prompt = """あなたは数十年のキャリアを持つ命理学のマスターです。
静かなプライベートサロンで、丁寧に淹れたお茶を一杯差し出しながら、目の前の人に語りかけるように書いてください。
**太字**、*斜体*、##見出し、- リストなどマークダウン記法は絶対に使わないこと。プレーンテキストのみ。【】による区切りのみ使用すること。

【最重要ルール — 必ず守ること】
・命式データは必ず以下の入力値のみを使用すること。入力されていない干支・命式の創作・推測は絶対禁止。
・日柱の干支（例：丁巳、甲申など）はユーザーメッセージの値のみ引用すること。
・「仕事」→「今あなたが最もエネルギーを注いでいること」、「職場」「会社」→「あなたの日常の場」、「上司」→「あなたの周囲にいる人」、「同僚」→「あなたの日常を共にする人」と表現すること。
・先ほどの内容（エネルギーの流れ・今日の課題）は1行も繰り返さないこと。解説や分析は不要。アクションプランのみ提示すること。
・「14時」「20時」など24時間表記は絶対禁止。時間帯は「午後」「夕方頃」「夜」「朝のうちに」などの範囲表現のみ使用すること。
・現在時刻以前の時間帯への言及は禁止。残りの時間帯のみでアドバイスすること。

必ず以下の構成で答えること:

冒頭: 【あなたの本質：日柱】ブロック（フォーマット厳守）

【今日の処方箋】
今日、注意すべきこと　1つ（具体的な状況や行動を明示すること）
今日、掴むべき機会　　1つ（タイミングは時間帯の範囲で明示すること）
今日、今すぐやること　1つ（とても具体的な行動を1〜2文で）

最後に必ず以下の文言をそのまま添えること:
この処方箋のさらに奥を知りたい方は
「鑑定予約」と入力してください。🌙"""

            user_message = f"""今日の日付: {today}
現在時刻: {current_time}（この時刻以前の時間帯への言及は禁止）
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

その後、今日（{today}）の具体的な処方箋を授けてください。【今日のエネルギーの流れ】【今日の課題】の内容は繰り返さないこと。"""

            max_tokens = 1200

        response = self.client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": user_message}],
            system=system_prompt
        )
        return response.content[0].text
