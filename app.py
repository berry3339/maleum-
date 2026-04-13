import os, threading, re
from flask import Flask, request, jsonify
from mind_pillar import PrecisionManse, MalgeumAI

try:
    from korean_lunar_calendar import KoreanLunarCalendar
    LUNAR_AVAILABLE = True
except ImportError:
    LUNAR_AVAILABLE = False
    print("⚠️ korean-lunar-calendar 미설치 — 음력 변환 불가")

app = Flask(__name__)

# API 키는 터미널에서 환경변수로 설정하세요
# export ANTHROPIC_API_KEY='sk-ant-...'
if not os.getenv("ANTHROPIC_API_KEY"):
    print("❌ ANTHROPIC_API_KEY 환경변수가 없습니다. 터미널에 아래 명령어를 입력하세요:")
    print("   export ANTHROPIC_API_KEY='여기에_본인_API키_붙여넣기'")
    exit(1)

results = {}

def kakao_reply(text):
    return jsonify({"version":"2.0","template":{"outputs":[{"simpleText":{"text":text}}]}})

def lunar_to_solar(y, m, d):
    """음력 날짜를 양력으로 변환. 실패 시 None 반환."""
    if not LUNAR_AVAILABLE:
        return None
    try:
        cal = KoreanLunarCalendar()
        cal.setLunarDate(y, m, d, False)
        return cal.solarYear, cal.solarMonth, cal.solarDay
    except Exception as e:
        print(f"❌ [음력변환오류] {e}")
        return None

def parse_date_msg(msg):
    """
    '19930426 음력' 또는 '19930616 양력' 형식 파싱.
    반환: (year, month, day, is_lunar, error_code)
    error_code: None=성공, 'no_type'=음/양력 없음, 'bad_format'=형식오류, 'bad_date'=날짜범위오류
    """
    clean = msg.replace(" ", "")

    if '음력' in clean:
        cal_type = '음력'
        digits = clean.replace('음력', '')
    elif '양력' in clean:
        cal_type = '양력'
        digits = clean.replace('양력', '')
    else:
        return None, None, None, None, 'no_type'

    if not digits.isdigit() or len(digits) != 8:
        return None, None, None, None, 'bad_format'

    y, m, d = int(digits[:4]), int(digits[4:6]), int(digits[6:8])
    if not (1920 <= y <= 2010 and 1 <= m <= 12 and 1 <= d <= 31):
        return None, None, None, None, 'bad_date'

    return y, m, d, (cal_type == '음력'), None

def make_prescription(uid, y, m, d, label):
    try:
        print(f"🚀 [AI시작] {uid} {y}/{m}/{d} ({label})")
        saju = PrecisionManse.calculate(y, m, d)
        ai = MalgeumAI()
        text = ai.get_prescription(saju)
        results[uid] = (
            f"🌤️ {y}년생 분석완료 ({label})\n"
            f"일주: {saju['day_pillar']}({saju['day_pillar_kr']}) | "
            f"오행: {saju['ohaeng']}\n"
            f"{'─'*15}\n"
            f"{text}\n"
            f"{'─'*15}\n"
            f"⚠️ 오늘 피해야 할 타이밍 있어요\n"
            f"더 보려면 생년월일 재입력"
        )
        print(f"✅ [AI완료] {uid}")
    except Exception as e:
        print(f"❌ [AI오류] {e}")
        results[uid] = f"❌ 오류: {e}\n다시 입력해주세요"

WELCOME_MSG = (
    "🌤️ 오늘의 흐름을 분석해드립니다\n\n"
    "생년월일 8자리 + 음력/양력 입력\n\n"
    "예) 양력: 19930616 양력\n"
    "예) 음력: 19930426 음력"
)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "server": "maleum"})

@app.route('/kakao', methods=['POST', 'GET'])
def kakao():
    if request.method == 'GET':
        return jsonify({"status": "ok"})
    try:
        data = request.get_json()
        msg = data['userRequest']['utterance'].strip()
        uid = data['userRequest']['user']['id']
        print(f"📩 [수신] uid={uid[:16]} | msg={msg!r}")

        # '결과'라고 쳤을 때의 로직
        if msg in ['결과', '확인', '보여줘']:
            if uid in results:
                return kakao_reply(results.pop(uid))
            return kakao_reply("⏳ 아직 AI가 열심히 분석 중이에요!\n조금만 더 기다렸다가 '결과'를 입력해주세요.")

        # 날짜 + 음력/양력 파싱
        y, m, d, is_lunar, err = parse_date_msg(msg)

        if err == 'no_type':
            # 숫자 8자리만 입력한 경우 → 음/양력 선택 안내
            if re.fullmatch(r'\d{8}', msg.replace(' ', '')):
                return kakao_reply(
                    "📅 음력인가요, 양력인가요?\n\n"
                    "뒤에 꼭 붙여서 다시 입력해주세요!\n\n"
                    f"예) {msg.replace(' ','')} 양력\n"
                    f"예) {msg.replace(' ','')} 음력"
                )
            return kakao_reply(WELCOME_MSG)

        if err == 'bad_format':
            return kakao_reply("❌ 형식이 맞지 않아요.\n\n예) 19930616 양력\n예) 19930426 음력")

        if err == 'bad_date':
            return kakao_reply("❌ 올바른 생년월일이 아닙니다.\n1920년~2010년 사이로 입력해주세요.")

        # 음력이면 양력으로 변환
        label = '양력'
        if is_lunar:
            converted = lunar_to_solar(y, m, d)
            if converted is None:
                return kakao_reply("❌ 음력 변환에 실패했어요.\n날짜를 다시 확인하거나\n양력으로 입력해주세요.")
            orig_y = y
            y, m, d = converted
            label = f'음력→양력 변환'
            print(f"🔄 음력 {orig_y}/{m}/{d} → 양력 {y}/{m}/{d}")

        results.pop(uid, None)
        threading.Thread(target=make_prescription, args=(uid, y, m, d, label), daemon=True).start()
        return kakao_reply(
            f"⏳ {y}년생 분석 시작! ({label})\n\n"
            f"🌤️ 당신의 운, 흐름, 타이밍을\n정밀하게 계산하고 있습니다.\n\n"
            f"👉 약 10초 후 채팅창에\n'결과' 라고 입력해주세요!"
        )

    except Exception as e:
        print(f"🔥 [카카오오류] {e}")
        return kakao_reply("잠시 후 다시 시도해주세요")

if __name__ == '__main__':
    print("🚀 맑음 서버 시작!")
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
