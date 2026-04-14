import os, threading, re
from flask import Flask, request, jsonify, abort
from mind_pillar import PrecisionManse, MalgeumAI

try:
    from korean_lunar_calendar import KoreanLunarCalendar
    LUNAR_AVAILABLE = True
except ImportError:
    LUNAR_AVAILABLE = False
    print("⚠️ korean-lunar-calendar 미설치 — 음력 변환 불가")

# ── LINE SDK ──────────────────────────────────────────────────────────────────
try:
    from linebot.v3 import WebhookHandler as LineHandler
    from linebot.v3.exceptions import InvalidSignatureError
    from linebot.v3.webhooks import MessageEvent, TextMessageContent
    from linebot.v3.messaging import (
        Configuration as LineConfig,
        ApiClient as LineApiClient,
        MessagingApi,
        ReplyMessageRequest,
        PushMessageRequest,
        TextMessage as LineTextMsg,
    )
    LINE_SDK_OK = True
except ImportError:
    LINE_SDK_OK = False
    print("⚠️ line-bot-sdk 미설치 — LINE 웹훅 비활성화")

LINE_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_SECRET       = os.getenv("LINE_CHANNEL_SECRET")

if LINE_SDK_OK and LINE_ACCESS_TOKEN and LINE_SECRET:
    line_handler = LineHandler(LINE_SECRET)
    line_config  = LineConfig(access_token=LINE_ACCESS_TOKEN)
    LINE_AVAILABLE = True
    print("✅ LINE 웹훅 활성화")
else:
    LINE_AVAILABLE = False
    print("⚠️ LINE 환경변수 없음 (LINE_CHANNEL_ACCESS_TOKEN / LINE_CHANNEL_SECRET)")

# ── Flask ─────────────────────────────────────────────────────────────────────
app = Flask(__name__)

if not os.getenv("ANTHROPIC_API_KEY"):
    print("❌ ANTHROPIC_API_KEY 환경변수가 없습니다.")
    print("   export ANTHROPIC_API_KEY='sk-ant-...'")
    exit(1)

results    = {}  # uid → AI 결과 텍스트
saju_cache = {}  # uid → (y, m, d, label)  상세분석 재요청용

# ── 공통 유틸 ─────────────────────────────────────────────────────────────────
def kakao_reply(text):
    return jsonify({"version":"2.0","template":{"outputs":[{"simpleText":{"text":text}}]}})

def line_reply(reply_token, text):
    """LINE reply_token으로 즉시 답장"""
    with LineApiClient(line_config) as client:
        MessagingApi(client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[LineTextMsg(text=text)]
            )
        )

def line_push(user_id, text):
    """LINE user_id로 푸시 메시지 (AI 결과 전달용)"""
    with LineApiClient(line_config) as client:
        MessagingApi(client).push_message(
            PushMessageRequest(
                to=user_id,
                messages=[LineTextMsg(text=text)]
            )
        )

def lunar_to_solar(y, m, d):
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
    """
    clean = msg.replace(" ", "")
    if '음력' in clean:
        cal_type, digits = '음력', clean.replace('음력', '')
    elif '양력' in clean:
        cal_type, digits = '양력', clean.replace('양력', '')
    else:
        return None, None, None, None, 'no_type'

    if not digits.isdigit() or len(digits) != 8:
        return None, None, None, None, 'bad_format'

    y, m, d = int(digits[:4]), int(digits[4:6]), int(digits[6:8])
    if not (1920 <= y <= 2010 and 1 <= m <= 12 and 1 <= d <= 31):
        return None, None, None, None, 'bad_date'

    return y, m, d, (cal_type == '음력'), None

def make_prescription(uid, y, m, d, label, mode='short', push_fn=None):
    """AI 분석 실행 (별도 스레드). push_fn 있으면 완료 시 자동 전송 (LINE용)."""
    try:
        print(f"🚀 [AI시작] uid={uid[:16]} {y}/{m}/{d} ({label}) mode={mode}")
        saju = PrecisionManse.calculate(y, m, d)
        ai   = MalgeumAI()
        text = ai.get_prescription(saju, mode=mode)

        if mode == 'short':
            result_text = text
        else:
            result_text = (
                f"🌤️ {y}년생 상세분석\n"
                f"일주: {saju['day_pillar']}({saju['day_pillar_kr']}) | "
                f"오행: {saju['ohaeng']}\n"
                f"{'─'*15}\n"
                f"{text}\n"
                f"{'─'*15}\n"
                f"더 보려면 생년월일 재입력"
            )

        if push_fn:
            push_fn(uid, result_text)   # LINE: 완료되면 자동으로 push
        else:
            results[uid] = result_text  # 카카오: results dict에 저장

        print(f"✅ [AI완료] uid={uid[:16]} mode={mode}")
    except Exception as e:
        print(f"❌ [AI오류] {e}")
        err_text = f"❌ 오류: {e}\n다시 입력해주세요"
        if push_fn:
            try: push_fn(uid, err_text)
            except: pass
        else:
            results[uid] = err_text

WELCOME_MSG = (
    "🌤️ 오늘의 흐름을 분석해드립니다\n\n"
    "생년월일 8자리 + 음력/양력 입력\n\n"
    "예) 양력: 19930616 양력\n"
    "예) 음력: 19930426 음력"
)

# ── 카카오 웹훅 ───────────────────────────────────────────────────────────────
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "server": "maleum"})

@app.route('/kakao', methods=['POST', 'GET'])
def kakao():
    if request.method == 'GET':
        return jsonify({"status": "ok"})
    try:
        data = request.get_json()
        msg  = data['userRequest']['utterance'].strip()
        uid  = data['userRequest']['user']['id']
        print(f"📩 [카카오] uid={uid[:16]} | msg={msg!r}")

        if msg in ['결과', '확인', '보여줘']:
            if uid in results:
                return kakao_reply(results.pop(uid))
            return kakao_reply("⏳ 아직 분석 중이에요!\n조금 후 '결과'를 입력해주세요.")

        if msg == '상세분석':
            if uid not in saju_cache:
                return kakao_reply("먼저 생년월일을 입력해주세요.\n예) 19930616 양력")
            y, m, d, label = saju_cache[uid]
            results.pop(uid, None)
            threading.Thread(target=make_prescription,
                             args=(uid, y, m, d, label, 'detailed'),
                             daemon=True).start()
            return kakao_reply("🔍 상세분석 중입니다...\n\n약 15초 후\n'결과' 를 입력해주세요!")

        y, m, d, is_lunar, err = parse_date_msg(msg)

        if err == 'no_type':
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

        label = '양력'
        if is_lunar:
            converted = lunar_to_solar(y, m, d)
            if converted is None:
                return kakao_reply("❌ 음력 변환 실패.\n양력으로 다시 입력해주세요.")
            orig_y = y
            y, m, d = converted
            label = '음력→양력 변환'
            print(f"🔄 음력 {orig_y}/{m}/{d} → 양력 {y}/{m}/{d}")

        results.pop(uid, None)
        saju_cache[uid] = (y, m, d, label)
        threading.Thread(target=make_prescription,
                         args=(uid, y, m, d, label, 'short'),
                         daemon=True).start()
        return kakao_reply(
            f"⏳ {y}년생 분석 시작! ({label})\n\n"
            f"🌤️ 당신의 운, 흐름, 타이밍을\n정밀하게 계산하고 있습니다.\n\n"
            f"👉 약 10초 후 채팅창에\n'결과' 라고 입력해주세요!"
        )

    except Exception as e:
        print(f"🔥 [카카오오류] {e}")
        return kakao_reply("잠시 후 다시 시도해주세요")

# ── LINE 웹훅 ─────────────────────────────────────────────────────────────────
@app.route('/line', methods=['POST'])
def line_webhook():
    if not LINE_AVAILABLE:
        abort(503)

    signature = request.headers.get('X-Line-Signature', '')
    body      = request.get_data(as_text=True)
    print(f"📩 [LINE] signature={signature[:10]}...")

    try:
        line_handler.handle(body, signature)
    except InvalidSignatureError:
        print("❌ [LINE] 서명 검증 실패")
        abort(400)

    return 'OK'

if LINE_AVAILABLE:
    @line_handler.add(MessageEvent, message=TextMessageContent)
    def handle_line_message(event):
        msg      = event.message.text.strip()
        uid      = event.source.user_id
        r_token  = event.reply_token
        print(f"📩 [LINE] uid={uid[:16]} | msg={msg!r}")

        # ── 결과 확인 ──
        if msg in ['결과', '확인', '보여줘']:
            if uid in results:
                line_reply(r_token, results.pop(uid))
            else:
                line_reply(r_token, "⏳ 아직 분석 중이에요!\n잠시 후 다시 보내주세요.")
            return

        # ── 상세분석 ──
        if msg == '상세분석':
            if uid not in saju_cache:
                line_reply(r_token, "먼저 생년월일을 입력해주세요.\n예) 19930616 양력")
                return
            y, m, d, label = saju_cache[uid]
            results.pop(uid, None)
            line_reply(r_token, "🔍 상세분석 중입니다...\n결과가 도착하면 자동으로 전송됩니다!")
            threading.Thread(
                target=make_prescription,
                args=(uid, y, m, d, label, 'detailed', line_push),
                daemon=True
            ).start()
            return

        # ── 날짜 파싱 ──
        y, m, d, is_lunar, err = parse_date_msg(msg)

        if err == 'no_type':
            if re.fullmatch(r'\d{8}', msg.replace(' ', '')):
                line_reply(r_token,
                    "📅 음력인가요, 양력인가요?\n\n"
                    f"예) {msg.replace(' ','')} 양력\n"
                    f"예) {msg.replace(' ','')} 음력")
            else:
                line_reply(r_token, WELCOME_MSG)
            return

        if err == 'bad_format':
            line_reply(r_token, "❌ 형식이 맞지 않아요.\n예) 19930616 양력")
            return
        if err == 'bad_date':
            line_reply(r_token, "❌ 올바른 생년월일이 아닙니다.\n1920년~2010년 사이로 입력해주세요.")
            return

        label = '양력'
        if is_lunar:
            converted = lunar_to_solar(y, m, d)
            if converted is None:
                line_reply(r_token, "❌ 음력 변환 실패.\n양력으로 다시 입력해주세요.")
                return
            orig_y = y
            y, m, d = converted
            label = '음력→양력 변환'
            print(f"🔄 음력 {orig_y}/{m}/{d} → 양력 {y}/{m}/{d}")

        saju_cache[uid] = (y, m, d, label)
        line_reply(r_token,
            f"⏳ {y}년생 분석 시작! ({label})\n\n"
            f"🌤️ 당신의 운, 흐름, 타이밍을\n정밀하게 계산하고 있습니다.\n\n"
            f"결과가 도착하면 자동으로 전송됩니다! 🍃"
        )
        threading.Thread(
            target=make_prescription,
            args=(uid, y, m, d, label, 'short', line_push),
            daemon=True
        ).start()

if __name__ == '__main__':
    print("🚀 맑음 서버 시작!")
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
