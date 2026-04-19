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
    STEMS_HJ  = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]
    STEMS_KR  = ["갑","을","병","정","무","기","경","신","임","계"]
    BRANCH_HJ = ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"]
    BRANCH_KR = ["자","축","인","묘","진","사","오","미","신","유","술","해"]

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

    def get_prescription(self, saju: dict, mode: str = 'short') -> str:
        today = datetime.now().strftime('%Y年%m月%d日')

        if mode == 'short':
            system_prompt = """あなたは四柱推命をベースにした、今日のエネルギーガイドです。
マークダウン記法（**太字**、*斜体*、##見出し、- リストなど）は絶対に使わないでください。プレーンテキストのみで答えてください。
必ず以下のフォーマットを正確に守り、[]の部分だけを埋めて答えてください。それ以外の言葉は絶対に追加しないでください。

🌅 今日は[日柱の五行を一言]のエネルギーで、あなたの一日を先読みしました。

今日は[エネルギー状態を一文で具体的に]。
[午前/午後 何時]以降に動くと、より良い流れに乗れますよ。

今日、ひとつだけ覚えておいてください。
👉 [小さく、簡単な行動をひとつ]

今日もそばにいます。🍃
👇 もっと深く知りたい方は「魂の処方箋」と入力してください"""

            ohaeng_time = {
                "木": "朝7〜9時",
                "火": "正午11〜13時",
                "土": "午後15〜17時",
                "金": "夕方18〜20時",
                "水": "夜21〜23時",
            }.get(saju['ohaeng'], "午後")

            user_message = f"""ユーザーの日柱: {saju['day_pillar']}、五行: {saju['ohaeng']}
この五行の推奨時間帯: {ohaeng_time}
フォーマットの[午前/午後 何時]には必ず「{ohaeng_time}」を使用してください。
上記フォーマット通りに、今日の短いエネルギーガイドを日本語で作成してください。"""

            max_tokens = 300

        elif mode == 'preview':
            system_prompt = """あなたは数十年のキャリアを持つ命理学のマスターです。
静かなプライベートサロンで、丁寧に淹れたお茶を差し出しながら、目の前の人に語りかけるように書いてください。
マークダウン記法（**太字**、*斜体*、##見出し、- リストなど）は絶対に使わないでください。プレーンテキストのみで答えてください。
哲学的な抽象表現は避け、現実的で具体的に。断定的でありながら、深い温かみのある文体で。

必ず以下の2段階構成で答えてください:

1. 【今日のエネルギーの流れ】
今日という日の気の流れを、この人の四柱命式をもとに深く読み解いてください。
今日がどんなエネルギーを持つ一日なのかを、具体的かつ鋭く伝えてください。

2. 【今日の課題】
今日この人が最も強く影響を受けているテーマ——恋愛・仕事・人間関係のうちのひとつ——を命式から見極め、
今まさに直面しているであろう葛藤を、鋭く、しかし優しく言葉にしてください。"""

            user_message = f"""今日の日付: {today}
ユーザーの四柱命式:
- 年齢: {saju['age']}歳
- 年柱: {saju['year_pillar']}
- 月柱: {saju['month_pillar']}
- 日柱: {saju['day_pillar']} ← 核となるエネルギー
- 日柱の五行: {saju['ohaeng']} ({saju['ohaeng_desc']})
- 現在の大運: {saju['cycle']}

今日（{today}）のエネルギーを深く読み解き、2段階の洞察をお願いします。"""

            max_tokens = 600

        else:  # prescription
            system_prompt = """あなたは数十年のキャリアを持つ命理学のマスターです。
静かなプライベートサロンで、丁寧に淹れたお茶を一杯差し出しながら、目の前の人に語りかけるように書いてください。
マークダウン記法（**太字**、*斜体*、##見出し、- リストなど）は絶対に使わないでください。プレーンテキストのみで答えてください。
哲学的な抽象表現は避け、現実的で具体的に。断定的でありながら、深い温かみのある文体で。

以下の構成で、今日の具体的な処方箋を授けてください。
先ほどお伝えした内容（エネルギーの流れ・今日の課題）は絶対に繰り返さないでください。

【今日の処方箋】
今日、注意すべきこと　1つ（具体的な状況や行動を明示すること）
今日、掴むべき機会　　1つ（具体的なタイミングまで明示すること）
今日、今すぐやること　1つ（とても具体的な行動を1〜2文で）

最後に必ず以下の文言をそのまま添えてください:
この処方箋のさらに奥を知りたい方は
「鑑定予約」と入力してください。🌙"""

            user_message = f"""今日の日付: {today}
ユーザーの四柱命式:
- 年齢: {saju['age']}歳
- 年柱: {saju['year_pillar']}
- 月柱: {saju['month_pillar']}
- 日柱: {saju['day_pillar']} ← 核となるエネルギー
- 日柱の五行: {saju['ohaeng']} ({saju['ohaeng_desc']})
- 現在の大運: {saju['cycle']}

今日（{today}）の具体的な処方箋を授けてください。先ほどの【今日のエネルギーの流れ】【今日の課題】の内容は繰り返さないでください。"""

            max_tokens = 1200

        response = self.client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": user_message}],
            system=system_prompt
        )
        return response.content[0].text
