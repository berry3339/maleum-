import os
from datetime import datetime

try:
    import anthropic
except ImportError:
    print("❌ anthropic 라이브러리 필요: pip3 install anthropic")
    exit(1)

try:
    from lunar_python import Solar
    LUNAR_PYTHON_AVAILABLE = True
except ImportError:
    LUNAR_PYTHON_AVAILABLE = False
    print("⚠️ lunar-python 미설치 — 일주 계산 불가")

# ============================================================================
# 1단계: 사주 四柱 정밀 계산 엔진
# ============================================================================
class PrecisionManse:
    STEMS_HJ  = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]
    STEMS_KR  = ["갑","을","병","정","무","기","경","신","임","계"]
    BRANCH_HJ = ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"]
    BRANCH_KR = ["자","축","인","묘","진","사","오","미","신","유","술","해"]

    # 천간 → 오행
    STEM_OHAENG = {
        "甲":"목","乙":"목","丙":"화","丁":"화","戊":"토",
        "己":"토","庚":"금","辛":"금","壬":"수","癸":"수"
    }

    OHAENG_DESC = {
        "목": "목(木)성향 — 위로 뻗어나가는 강한 성장 욕구, 호기심, 창의성",
        "화": "화(火)성향 — 뜨거운 열정, 폭발적인 에너지, 직관력",
        "토": "토(土)성향 — 흔들리지 않는 뚝심, 수용력, 깊은 안정감",
        "금": "금(金)성향 — 날카로운 결단력, 완벽주의, 냉철한 이성",
        "수": "수(水)성향 — 유연함, 깊은 통찰력, 지혜와 영감"
    }

    @staticmethod
    def _kr(hj: str) -> str:
        """한자 1글자 → 한글 독음 (天干/地支)"""
        m = {}
        for i, h in enumerate(PrecisionManse.STEMS_HJ):
            m[h] = PrecisionManse.STEMS_KR[i]
        for i, h in enumerate(PrecisionManse.BRANCH_HJ):
            m[h] = PrecisionManse.BRANCH_KR[i]
        return m.get(hj, hj)

    @staticmethod
    def _pillar_kr(hj_pillar: str) -> str:
        """'丁巳' → '정사'"""
        if len(hj_pillar) >= 2:
            return PrecisionManse._kr(hj_pillar[0]) + PrecisionManse._kr(hj_pillar[1])
        return hj_pillar

    @staticmethod
    def calculate(year: int, month: int, day: int) -> dict:
        # ── 四柱 계산 ──────────────────────────────────────────
        if LUNAR_PYTHON_AVAILABLE:
            solar = Solar.fromYmd(year, month, day)
            ec = solar.getLunar().getEightChar()
            year_hj  = ec.getYear()   # e.g. "乙丑"
            month_hj = ec.getMonth()  # e.g. "癸未"
            day_hj   = ec.getDay()    # e.g. "丁巳"  ← 핵심 일주
        else:
            # fallback: 년주만 계산
            stems_fallback   = ["경","신","임","계","갑","을","병","정","무","기"]
            branches_fallback = ["신","유","술","해","자","축","인","묘","진","사","오","미"]
            year_hj  = stems_fallback[year % 10] + branches_fallback[year % 12]
            month_hj = "미상"
            day_hj   = "미상"

        # ── 일주 천간으로 오행 결정 ────────────────────────────
        day_stem  = day_hj[0] if day_hj and day_hj != "미상" else year_hj[0]
        ohaeng    = PrecisionManse.STEM_OHAENG.get(day_stem, "목")

        # ── 나이·대운 흐름 ────────────────────────────────────
        age = datetime.now().year - year
        if age < 35:
            cycle = "치열한 구축기 (폭발적으로 성장하며 내공을 다지는 시기)"
        elif age < 50:
            cycle = "도약과 확장의 정점기 (무기력을 깨고 에너지를 터뜨릴 시기)"
        else:
            cycle = "단단한 안정기 (내실을 다지고 여유를 즐기는 시기)"

        return {
            # 四柱 한자 + 한글
            "year_pillar":      year_hj,
            "year_pillar_kr":   PrecisionManse._pillar_kr(year_hj),
            "month_pillar":     month_hj,
            "month_pillar_kr":  PrecisionManse._pillar_kr(month_hj) if month_hj != "미상" else "미상",
            "day_pillar":       day_hj,
            "day_pillar_kr":    PrecisionManse._pillar_kr(day_hj) if day_hj != "미상" else "미상",
            # 오행
            "ohaeng":           ohaeng,
            "ohaeng_desc":      PrecisionManse.OHAENG_DESC[ohaeng],
            # 나이·흐름
            "age":              age,
            "cycle":            cycle,
        }


# ============================================================================
# 2단계: 하이엔드 멘탈 케어 AI (일주 중심 분석)
# ============================================================================
class MalgeumAI:
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("API 키가 없습니다. export ANTHROPIC_API_KEY='sk-...'를 입력하세요.")
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def get_prescription(self, saju: dict, mode: str = 'short') -> str:
        if mode == 'short':
            system_prompt = """당신은 사주 명리학 기반 하루 에너지 가이드입니다.
반드시 아래 형식을 정확히 그대로 지켜서, 빈칸만 채워 답하세요. 형식 외 말은 절대 추가하지 마세요.

🌅 오늘 [일주 오행 한 단어] 기운으로 미리 읽어봤어요.

오늘은 [에너지 상태 한 줄 — 구체적으로].
[오전/오후 몇 시] 이후에 움직이면 더 좋아요.

오늘 하나만 기억하세요.
👉 [행동 딱 하나 — 작고 쉽게]

오늘도 제가 옆에 있을게요. 🍃
👇 더 깊이 보고 싶으면 '상세분석' 을 입력하세요"""

            user_message = f"""사용자 일주: {saju['day_pillar']}({saju['day_pillar_kr']}), 오행: {saju['ohaeng']}
위 형식대로 오늘의 짧은 에너지 가이드를 작성해주세요."""

            max_tokens = 300

        else:  # detailed
            system_prompt = """당신은 사주 명리학과 세련된 라이프스타일 처방을 결합해 번아웃·무기력에 빠진 사람에게 에너지를 되찾아주는 최고급 심리 멘토입니다.

반드시 아래 3단계 구조로 답변하세요. 절대 유치하거나 뻔한 위로(책 읽기, 긍정적 생각)는 하지 마세요.

1. [당신의 진짜 저력]: 사용자의 일주(日柱) 오행 기운을 바탕으로, 이 사람이 원래 얼마나 단단하고 매력적인 사람인지 구체적으로 짚어주세요. 반드시 일주를 근거로 설명하세요.
2. [운의 휴지기 공감]: 지금의 무기력은 실패가 아니라 대운 흐름상 에너지를 비축하는 '운의 환절기'임을 명리학적으로 깊이 공감해주세요.
3. [하이엔드 감각 리셋 처방전]: 일주의 오행 기운에 맞는 감각 리셋 액션 플랜 3가지를 구체적이고 세련되게 제안하세요.
   (예시 활용: 묵직한 우디 향수로 후각적 긴장감 주기, 핏이 완벽한 하이엔드 수트로 시각적 자신감 되찾기, 코트에서 땀 흘리는 동적 루틴, 풍수적 공간 정돈, 새 외국어 소리 내어 읽기 등)

단호하지만 깊은 애정이 담긴 존댓말로, "당신의 사이클은 이미 다시 올라갈 준비를 마쳤습니다"라는 메시지로 마무리하세요."""

            user_message = f"""사용자 사주 명식:
- 나이: {saju['age']}세
- 년주(年柱): {saju['year_pillar']} ({saju['year_pillar_kr']})
- 월주(月柱): {saju['month_pillar']} ({saju['month_pillar_kr']})
- 일주(日柱): {saju['day_pillar']} ({saju['day_pillar_kr']}) ← 이 사람의 핵심 기운
- 일주 오행: {saju['ohaeng']} ({saju['ohaeng_desc']})
- 현재 대운 흐름: {saju['cycle']}

⚠️ 중요: 이 사람의 핵심 기운(일주)은 [{saju['day_pillar']} {saju['day_pillar_kr']}]입니다.
반드시 이 일주를 중심으로 사주를 분석하고 처방전을 내려주세요.

이 사람의 정체된 에너지를 다시 폭발하게 만들 강력한 처방전을 내려주세요."""

            max_tokens = 1024

        response = self.client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": user_message}],
            system=system_prompt
        )
        return response.content[0].text


# ============================================================================
# 3단계: 터미널 실행 인터페이스
# ============================================================================
def run():
    print("\n" + "="*65)
    print(" 🏛️  맑음 : 당신의 무기력을 박살 낼 사주 & 심리 멘토")
    print("="*65 + "\n")

    try:
        year  = int(input("📅 출생년도 (예: 1985): "))
        month = int(input("📅 출생월 (1-12): "))
        day   = int(input("📅 출생일 (1-31): "))
    except ValueError:
        print("❌ 숫자를 올바르게 입력해주세요.")
        return

    print("\n⏳ 사주 四柱를 정밀 계산 중입니다...")
    saju = PrecisionManse.calculate(year, month, day)
    print(f"  년주: {saju['year_pillar']}({saju['year_pillar_kr']})  "
          f"월주: {saju['month_pillar']}({saju['month_pillar_kr']})  "
          f"일주: {saju['day_pillar']}({saju['day_pillar_kr']})")

    print("\n💭 일주 중심으로 처방전 작성 중...\n")
    try:
        ai = MalgeumAI()
        prescription = ai.get_prescription(saju)
        print("="*65)
        print(" 🌟 맑음 처방전 도착")
        print("="*65)
        print(prescription)
        print("\n" + "="*65)
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    run()
