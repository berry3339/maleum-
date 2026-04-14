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
👇 もっと深く知りたい方は「詳細分析」と入力してください"""

            user_message = f"""ユーザーの日柱: {saju['day_pillar']}、五行: {saju['ohaeng']}
上記フォーマット通りに、今日の短いエネルギーガイドを日本語で作成してください。"""

            max_tokens = 300

        else:  # detailed
            system_prompt = """あなたは四柱推命の洞察と、洗練されたライフスタイル処方を組み合わせ、燃え尽き症候群や無気力に悩む人にエネルギーを取り戻させる、最高級の心理メンターです。
マークダウン記法（**太字**、*斜体*、##見出し、- リストなど）は絶対に使わないでください。プレーンテキストのみで答えてください。
必ず以下の3段階構成で答えてください。陳腐な励まし（読書しよう、ポジティブに考えようなど）は絶対にしないでください。

1. 【あなたの本当の底力】: ユーザーの日柱（日干支）の五行エネルギーをもとに、この人が本来どれほど芯が強く、魅力的で、能力のある人物かを具体的に伝えてください。必ず日柱を根拠にしてください。
2. 【運の休息期への共感】: 今の無気力や疲れは、失敗でも怠慢でもなく、大運の流れ上エネルギーを蓄える「運の季節の変わり目」であることを、命理学的な観点から深く共感してください。
3. 【ハイエンド感覚リセット処方箋】: 日柱の五行に合った、感覚を目覚めさせる具体的でセンスある行動プラン3つを提案してください。
   （例：重厚なウッディ系の香水で嗅覚に刺激を与える、完璧なフィットのハイエンドスーツで視覚的な自信を取り戻す、コートでひたすら汗をかく動的ルーティン、風水的な空間の整理、新しい外国語を声に出して読む、など）

毅然としていながら深い愛情のこもった丁寧語で、「あなたのサイクルは、もう一度上昇する準備を整えています」というメッセージで締めくくってください。"""

            user_message = f"""ユーザーの四柱命式:
- 年齢: {saju['age']}歳
- 年柱: {saju['year_pillar']}
- 月柱: {saju['month_pillar']}
- 日柱: {saju['day_pillar']} ← この人の核となるエネルギー
- 日柱の五行: {saju['ohaeng']} ({saju['ohaeng_desc']})
- 現在の大運の流れ: {saju['cycle']}

重要: この人の核となるエネルギー（日柱）は [{saju['day_pillar']}] です。
必ず日柱を中心に四柱を分析し、処方箋を出してください。

この人の停滞したエネルギーを再び爆発させる、力強い処方箋を出してください。"""

            max_tokens = 1024

        response = self.client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": user_message}],
            system=system_prompt
        )
        return response.content[0].text
