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
👇 もっと深く知りたい方は「魂の処方箋」と入力してください""" + category_system_rule

            ohaeng_time = {
                "木": "朝のうちに",
                "火": "午後から",
                "土": "午後から",
                "金": "夕方頃",
                "水": "夜",
            }.get(saju['ohaeng'], "午後から")

            user_message = f"""{category_user_note}ユーザーの日柱: {saju['day_pillar']}、五行: {saju['ohaeng']}
この五行の推奨時間帯: {ohaeng_time}
フォーマットの時間帯には必ず「{ohaeng_time}」を使用してください。
上記フォーマット通りに、今日の短いエネルギーガイドを日本語で作成してください。"""

            max_tokens = 300

        elif mode == 'preview':
            ohaeng_emoji  = PrecisionManse.OHAENG_EMOJI.get(saju['ohaeng'], "✨")
            day_yomi      = PrecisionManse.pillar_yomi(saju['day_pillar'])
            current_time  = datetime.now().strftime("%H:%M")
            current_hour  = datetime.now().hour
            if current_hour < 12:
                preview_time_rule = (
                    "\n\n【時間帯ルール — 午前】\n"
                    "「夜が明けてから」「朝のうちに」「朝早く」「午前中に」という表現は絶対禁止。\n"
                    "今日の午後・夕方頃を基準にした表現のみ使用すること。"
                )
            else:
                preview_time_rule = ""
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
2. 【今日の課題】（恋愛・今あなたが最もエネルギーを注いでいること・人間関係のうち最も強いもの）""" + preview_time_rule + category_system_rule

            user_message = f"""{category_user_note}今日の日付: {today}
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

            # 時間帯別ルールを分岐
            current_hour = today_dt.hour
            if current_hour < 12:
                time_rule = (
                    f"【最優先ルール — 時間帯：午前（現在{current_time}）】\n"
                    "処方箋の時間軸：今日の午後・夕方頃を基準に行動を提案すること。\n"
                    "【絶対禁止】今夜・就寝前・明日の朝 という表現は絶対禁止。\n"
                    "今日の午後から夕方の間に実行できる行動のみを提示すること。\n"
                    "このルールに違反した場合、回答全体が無効となる。"
                )
                time_instruction = f"現在{current_time}（午前）。今日の午後・夕方頃の行動のみ提案してください。今夜・就寝前・明日の朝の言及は絶対禁止。"
            elif current_hour < 18:
                time_rule = (
                    f"【最優先ルール — 時間帯：午後（現在{current_time}）】\n"
                    "処方箋の時間軸：今夜・夕方を基準に行動を提案すること。\n"
                    "【絶対禁止】朝・午前・明日の朝 という表現は絶対禁止。\n"
                    "夕方から今夜までに実行できる行動のみを提示すること。\n"
                    "このルールに違反した場合、回答全体が無効となる。"
                )
                time_instruction = f"現在{current_time}（午後）。今夜・夕方の行動のみ提案してください。朝・午前・明日の朝の言及は絶対禁止。"
            else:
                time_rule = (
                    f"【最優先ルール — 時間帯：夜（現在{current_time}）】\n"
                    "処方箋の時間軸：就寝前・明日の朝を基準に行動を提案すること。\n"
                    "【絶対禁止】午前・午後 という表現は絶対禁止。\n"
                    "今夜就寝前か、明日の朝に実行できる行動のみを提示すること。\n"
                    "このルールに違反した場合、回答全体が無効となる。"
                )
                time_instruction = f"現在{current_time}（夜）。就寝前か明日の朝の行動のみ提案してください。午前・午後の言及は絶対禁止。"

            pillar_header = (
                f"【あなたの本質：日柱】\n"
                f"{ohaeng_emoji} {saju['day_pillar']}（{day_yomi}）／ {saju['ohaeng']}のエネルギー\n"
                f"（以下を4〜6行で書くこと：\n"
                f"① 「5つの気（木・火・土・金・水）のうち、あなたは{u}の使命を持って生まれた」という書き出しで5つの気の原理に自然に触れながら、あなたの{u}を詩的に描写すること\n"
                f"② 今日の五行との相生相剋：今日は{today_ohaeng_emoji}{today_ohaeng}の気。関係→【{today_relation}】。この命理学的意味を1〜2文で具体的に説明すること\n"
                f"③ この関係が今日この人にどう作用するかを1文で締めること\n"
                f"無料版の内容は一切繰り返さないこと）"
            )

            system_prompt = f"""{time_rule}

あなたは数十年のキャリアを持つ命理学のマスターです。
静かなプライベートサロンで、丁寧に淹れたお茶を一杯差し出しながら、目の前の人に語りかけるように書いてください。
**太字**、*斜体*、##見出し、- リストなどマークダウン記法は絶対に使わないこと。プレーンテキストのみ。【】による区切りのみ使用すること。

【最重要ルール — 必ず守ること】
・命式データは必ず以下の入力値のみを使用すること。入力されていない干支・命式の創作・推測は絶対禁止。
・日柱の干支（例：丁巳、甲申など）はユーザーメッセージの値のみ引用すること。
・「仕事」→「今あなたが最もエネルギーを注いでいること」、「職場」「会社」→「あなたの日常の場」、「上司」→「あなたの周囲にいる人」、「同僚」→「あなたの日常を共にする人」と表現すること。
・無料版（preview）で伝えた内容は1行も繰り返さないこと。より深いレイヤーの洞察と具体的アクションのみ提示すること。
・「14時」「20時」など24時間表記は絶対禁止。時間帯は「午後」「夕方頃」「夜」「朝のうちに」などの範囲表現のみ使用すること。

必ず以下の構成で答えること:

冒頭: 【あなたの本質：日柱】ブロック（フォーマット厳守。無料版より深く。ユーザーの五行と今日の季節の五行との相生相剋を命理学的に必ず含めること）

【今日の処方箋】
以下の3項目は必ず全て埋めること。空欄・省略・「—」は絶対禁止。

今日、注意すべきこと：（必須）具体的な状況や言動を1〜2文で書くこと
今日、掴むべき機会：（必須）時間帯を明示し、具体的な行動を1〜2文で書くこと
今日、今すぐやること：（必須）今この瞬間から実行できる具体的な行動を1〜2文で書くこと

最後に必ず以下の文言をそのまま添えること:
この処方箋のさらに奥を知りたい方は
「鑑定予約」と入力してください。🌙""" + category_system_rule

            user_message = f"""{category_user_note}{time_instruction}

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

その後、今日（{today}）の具体的な処方箋を授けてください。無料版の内容は一切繰り返さず、より深いアクションプランのみ提示すること。"""

            max_tokens = 1200

        response = self.client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": user_message}],
            system=system_prompt
        )
        return response.content[0].text

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

必ず以下の構成で書くこと:

【二人の気の関係】
2〜3行: 五行の関係を詩的かつ命理学的に説明すること

【魂の共鳴】
4〜5行: 二人の感性的な絆を深く詩的に描写すること

【二人の課題と恵み】
3〜4行: この関係が持つ光と影を正直に伝えること

【今この瞬間、あなたへ】
2〜3行: 相手との関係で今最も大切にすべきことを伝えること

最後に必ず以下のカードをそのまま出力すること（XX%のみ命理学的に算出して埋めること）:
┏━━━━━━━━━━━━━━━━━━━┓
   💘 魂の共鳴度：XX%
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
