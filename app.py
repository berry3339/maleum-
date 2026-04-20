import os
import json
import re
import threading
from datetime import datetime
from flask import Flask, request, jsonify
from mind_pillar import PrecisionManse, MindPillarAI
from mind_pillar_line import PrecisionManse as LineManse, MalgeumLineAI
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

app = Flask(__name__)
user_sessions = {}

CATEGORY_LABELS = {
    '1': '🌸 恋愛とご縁',
    '2': '💼 仕事と使命',
    '3': '💰 金運と豊かさ',
    '4': '🌿 心身の健やかさ',
}

USERS_FILE = '/data/users.json'

def load_users():
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def save_user(user_id, year, month, day):
    users = load_users()
    users[user_id] = {'year': year, 'month': month, 'day': day}
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def send_daily_messages():
    """매일 오전 7시(JST) 등록된 모든 유저에게 오늘의 처방전 push"""
    import requests as req
    users = load_users()
    if not users:
        return
    print(f"⏰ [暁の処方箋] {len(users)}명에게 발송 시작")
    for uid, data in users.items():
        try:
            saju = LineManse.calculate(data['year'], data['month'], data['day'])
            ai   = MalgeumLineAI()
            text = "🌅 暁の処方箋\n\n" + ai.get_prescription(saju, mode='short')
            req.post(
                'https://api.line.me/v2/bot/message/push',
                headers={
                    'Authorization': f"Bearer {os.getenv('LINE_CHANNEL_ACCESS_TOKEN')}",
                    'Content-Type': 'application/json'
                },
                json={'to': uid, 'messages': [{'type': 'text', 'text': text}]},
                timeout=30
            )
            print(f"✅ [暁push] {uid[:16]}")
        except Exception as e:
            print(f"❌ [暁push오류] {uid[:16]}: {e}")

# 매일 오전 7시(JST) 스케줄러 시작
jst = pytz.timezone('Asia/Tokyo')
scheduler = BackgroundScheduler(timezone=jst)
scheduler.add_job(send_daily_messages, CronTrigger(hour=7, minute=0, timezone=jst))
scheduler.start()

# ============================================================================
# 헬스체크
# ============================================================================
@app.route('/', methods=['GET'])
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

# ============================================================================
# 카카오톡 챗봇
# ============================================================================
@app.route('/kakao', methods=['POST'])
def kakao():
    try:
        data = request.get_json()
        user_message = data['userRequest']['utterance'].strip()
        user_id = data['userRequest']['user']['id']
        response_text = process_kakao(user_id, user_message)
        return jsonify({"version": "2.0", "template": {"outputs": [{"simpleText": {"text": response_text}}]}})
    except Exception as e:
        return jsonify({"version": "2.0", "template": {"outputs": [{"simpleText": {"text": f"오류: {e}"}}]}})

def process_kakao(user_id, message):
    if message in ['시작', '안녕', '처방전', '사주', 'start', '다시']:
        user_sessions[f'kakao_{user_id}'] = {'step': 'year'}
        return "🏛️ Mind-Pillar에 오신 것을 환영합니다!\n\n📅 출생년도를 입력해주세요.\n예) 1985"
    session = user_sessions.get(f'kakao_{user_id}', {})
    step = session.get('step')
    if step == 'year':
        try:
            year = int(message)
            if not (1920 <= year <= 2010):
                return "❌ 올바른 출생년도를 입력해주세요. (예: 1985)"
            user_sessions[f'kakao_{user_id}'] = {'step': 'month', 'year': year}
            return "📅 출생월을 입력해주세요. (1~12)"
        except:
            return "❌ 숫자만 입력해주세요. (예: 1985)"
    elif step == 'month':
        try:
            month = int(message)
            if not (1 <= month <= 12):
                return "❌ 1~12 사이의 숫자를 입력해주세요."
            user_sessions[f'kakao_{user_id}']['step'] = 'day'
            user_sessions[f'kakao_{user_id}']['month'] = month
            return "📅 출생일을 입력해주세요. (1~31)"
        except:
            return "❌ 숫자만 입력해주세요. (예: 7)"
    elif step == 'day':
        try:
            day = int(message)
            if not (1 <= day <= 31):
                return "❌ 1~31 사이의 숫자를 입력해주세요."
            year = user_sessions[f'kakao_{user_id}']['year']
            month = user_sessions[f'kakao_{user_id}']['month']
            saju = PrecisionManse.calculate(year, month, day)
            ai = MindPillarAI()
            prescription = ai.get_prescription(saju)
            user_sessions[f'kakao_{user_id}'] = {}
            return f"🌟 Mind-Pillar 처방전\n{'='*30}\n{prescription}\n\n다시 받으려면 '시작'을 입력하세요."
        except Exception as e:
            return f"❌ 오류: {e}"
    return "안녕하세요! '시작'을 입력해주세요. 🏛️"

# ============================================================================
# LINE 챗봇
# ============================================================================
def line_reply_api(reply_token, text):
    """LINE reply API 호출"""
    import requests as req
    try:
        resp = req.post(
            'https://api.line.me/v2/bot/message/reply',
            headers={
                'Authorization': f"Bearer {os.getenv('LINE_CHANNEL_ACCESS_TOKEN')}",
                'Content-Type': 'application/json'
            },
            json={'replyToken': reply_token, 'messages': [{'type': 'text', 'text': text}]},
            timeout=10
        )
        print(f"📤 [LINE reply] status={resp.status_code}")
    except Exception as e:
        print(f"❌ [LINE reply 실패] {e}")

def line_push_api(user_id, text):
    """LINE push API 호출"""
    import requests as req
    try:
        resp = req.post(
            'https://api.line.me/v2/bot/message/push',
            headers={
                'Authorization': f"Bearer {os.getenv('LINE_CHANNEL_ACCESS_TOKEN')}",
                'Content-Type': 'application/json'
            },
            json={'to': user_id, 'messages': [{'type': 'text', 'text': text}]},
            timeout=30
        )
        print(f"📤 [LINE push] status={resp.status_code}")
    except Exception as e:
        print(f"❌ [LINE push 실패] {e}")

def _filter_time_lines(text: str) -> str:
    """현재 시간 기준으로 부적절한 시간대 표현이 포함된 줄 제거"""
    now_hour = datetime.now().hour
    if now_hour < 12:
        return text

    forbidden = ["朝のうちに", "午前中に", "朝起きたら", "今から午前", "朝一番に"]
    if now_hour >= 18:
        forbidden += ["午後から", "夕方に"]

    lines = text.split('\n')
    filtered = [line for line in lines if not any(w in line for w in forbidden)]
    return '\n'.join(filtered)

def deep_analysis(user_id, year, month, day, mode='preview', birth_time='不明', category=None):
    """深層解読 AI 처리 → push API — background thread에서 실행"""
    try:
        saju   = LineManse.calculate(year, month, day)
        ai     = MalgeumLineAI()
        result = ai.get_prescription(saju, mode=mode, birth_time=birth_time, category=category)

        if mode == 'preview':
            payment_msg = (
                "\n\n今、あなたの中にある迷いは——\n"
                "偶然ではありません。\n\n"
                "命式はすでに、その答えを持っています。\n"
                "あなたに必要なのは、\n"
                "あなただけの「処方箋」を受け取ること。\n\n"
                "──────────────\n"
                "🔒 魂の処方箋を受け取る\n"
                "→ https://www.paypal.com/ncp/payment/G7K49PXY32R2C\n\n"
                "✅ ご決済後は「処方箋を開く」とご入力ください。\n"
                "最初に戻りたい方は「マルム」とご入力ください。🌿"
            )
            line_push_api(user_id, result + payment_msg)
        else:  # prescription
            result = _filter_time_lines(result)
            line_push_api(user_id, result)
    except Exception as e:
        print(f"❌ [深層解読오류] {e}")
        line_push_api(user_id, "❌ エラーが発生しました。もう一度お試しください。")

def compatibility_analysis(user_id, year, month, day, p_year, p_month, p_day, mode='preview'):
    """궁합 분석 → push API — background thread에서 실행"""
    try:
        saju1  = LineManse.calculate(year, month, day)
        saju2  = LineManse.calculate(p_year, p_month, p_day)
        ai     = MalgeumLineAI()
        result = ai.get_compatibility(saju1, saju2, mode=mode)
        if mode == 'preview':
            payment_msg = (
                "\n\n──────────────\n"
                "🔒 運命の処方箋を受け取る\n"
                "→ https://www.paypal.com/ncp/payment/G7K49PXY32R2C\n\n"
                "✅ ご決済後は「共鳴を開く」とご入力ください。\n"
                "最初に戻りたい方は「マルム」とご入力ください。🌿"
            )
            line_push_api(user_id, result + payment_msg)
        else:
            line_push_api(user_id, result)
    except Exception as e:
        print(f"❌ [궁합분석오류] {e}")
        line_push_api(user_id, "❌ エラーが発生しました。もう一度お試しください。")

def handle_line_event(user_id, message, reply_token):
    """일반 메시지: process_line → reply — background thread에서 실행"""
    try:
        text = process_line(user_id, message)
        line_reply_api(reply_token, text)
    except Exception as e:
        print(f"❌ [LINE 처리오류] {e}")
        try:
            line_reply_api(reply_token, "❌ エラーが発生しました。もう一度お試しください。")
        except:
            pass

@app.route('/line', methods=['POST'])
def line():
    try:
        data = request.get_json()
        for event in data.get('events', []):
            if event['type'] == 'message' and event['message']['type'] == 'text':
                user_id     = event['source']['userId']
                message     = event['message']['text'].strip()
                reply_token = event['replyToken']
                print(f"📩 [LINE] uid={user_id[:16]} | msg={message!r}")

                # 深層解読: 라우트에서 즉시 처리
                if message == '魂の処方箋':
                    key = f'line_{user_id}'
                    session = user_sessions.get(key, {})
                    if 'year' in session:
                        line_reply_api(reply_token,
                            "🌀 魂の処方箋を準備します。\n"
                            "少々お待ちくださいませ。"
                        )
                        threading.Thread(
                            target=deep_analysis,
                            args=(user_id, session['year'], session['month'], session['day'], 'preview', session.get('birth_time', '不明'), session.get('category')),
                            daemon=True
                        ).start()
                    else:
                        line_reply_api(reply_token, "まず生年月日を入力してください🌿")
                    continue

                # 일반 메시지: background thread
                threading.Thread(
                    target=handle_line_event,
                    args=(user_id, message, reply_token),
                    daemon=True
                ).start()
    except Exception as e:
        print(f"❌ [LINE 웹훅오류] {e}")
    return jsonify({'status': 'ok'})  # 항상 즉시 200 반환

def process_line(user_id, message):
    key = f'line_{user_id}'

    # 処方箋を開く
    if message == '処方箋を開く':
        session = user_sessions.get(key, {})
        if 'year' in session:
            threading.Thread(
                target=deep_analysis,
                args=(user_id, session['year'], session['month'], session['day'], 'prescription', session.get('birth_time', '不明'), session.get('category')),
                daemon=True
            ).start()
            return ("🌀 決済を確認しました。\n"
                    "あなただけの処方箋の封を切ります...")
        return "まず生年月日を入力してください🌿"

    # 共鳴を開く (유료 전체 궁합)
    if message == '共鳴を開く':
        session = user_sessions.get(key, {})
        partner = session.get('partner_birth')
        if 'year' in session and partner:
            threading.Thread(
                target=compatibility_analysis,
                args=(user_id, session['year'], session['month'], session['day'],
                      partner['year'], partner['month'], partner['day'], 'full'),
                daemon=True
            ).start()
            return "🌀 決済を確認しました。\n運命の処方箋の封を切ります..."
        return "まず「魂の共鳴」から始めてください🌿"

    # マルム → 처음으로 리셋
    if message == 'マルム':
        user_sessions[key] = {}
        return "こんにちは！「扉を開く」と入力してください。🌿"

    # 魂の共鳴 → 어떤 세션 상태에서도 상대방 생년월일 입력 대기
    if message == '魂の共鳴':
        session = user_sessions.get(key, {})
        user_sessions[key] = {**session, 'step': 'WAITING_PARTNER'}
        return ("秘密の扉を叩きましたね。🌙\n"
                "あなたの心に宿るあの人の\n"
                "生年月日を8桁で、静かに入力してください。\n"
                "例）19970901\n"
                "※お名前は不要です。")

    # 鑑定予約 (따옴표/특수문자 포함 입력도 인식)
    if re.search(r'鑑定予約', message):
        session = user_sessions.get(key, {})
        user_sessions[key] = {**session, 'step': 'booking'}
        return ("ご予約はこちらから承ります。\n"
                "🔒 1対1 LINE鑑定（30分 ¥5,000）\n"
                "→ https://www.paypal.com/ncp/payment/4FXDK6WHXU45W\n\n"
                "ご希望の日時を教えてください。\n"
                "例）4月25日 20時\n"
                "最初に戻りたい方は「マルム」とご入力ください。🌿")

    # 시작
    if message in ['start', 'はじめ', 'スタート', 'こんにちは', '안녕', '扉を開く']:
        user_sessions[key] = {'step': 'date'}
        return "🌟 맑음(マルム)へようこそ！\n\n生年月日を8桁の数字で送ってください。\n例）19930616"

    session = user_sessions.get(key, {})
    step = session.get('step')

    if step == 'date':
        normalized = message.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
        digits = ''.join(filter(str.isdigit, normalized))
        if len(digits) == 8:
            try:
                year  = int(digits[0:4])
                month = int(digits[4:6])
                day   = int(digits[6:8])
                if not (1920 <= year <= 2010):
                    return "❌ 正しい生年月日を入力してください。\n例）19930616"
                if not (1 <= month <= 12):
                    return "❌ 正しい生年月日を入力してください。\n例）19930616"
                if not (1 <= day <= 31):
                    return "❌ 正しい生年月日を入力してください。\n例）19930616"
                user_sessions[key] = {'step': 'time', 'year': year, 'month': month, 'day': day}
                return ("時間がわからなくても大丈夫です。🌿\n"
                        "生まれた時間を教えてください。\n"
                        "例）0730\n"
                        "わからない方は「不明」と送ってください。")
            except Exception as e:
                return f"❌ エラーが発生しました: {e}"
        return "❌ 8桁の数字で入力してください。\n例）19930616"

    if step == 'time':
        year  = session['year']
        month = session['month']
        day   = session['day']
        normalized = message.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
        if message.strip() == '不明':
            birth_time = '不明'
        else:
            digits = ''.join(filter(str.isdigit, normalized))
            if len(digits) in (3, 4):
                birth_time = digits.zfill(4)
            else:
                return "❌ 時間は4桁（例：0730）か\n「不明」で送ってください。"
        user_sessions[key] = {'step': 'WAITING_CATEGORY', 'year': year, 'month': month, 'day': day, 'birth_time': birth_time}
        save_user(user_id, year, month, day)
        return ("命式を確認いたしました。🌿\n"
                "今日、最も導きを求めているテーマを\n"
                "番号でお知らせください。\n\n"
                "1. 🌸 恋愛とご縁\n"
                "2. 💼 仕事と使命\n"
                "3. 💰 金運と豊かさ\n"
                "4. 🌿 心身の健やかさ")

    if step == 'WAITING_CATEGORY':
        normalized = message.translate(str.maketrans('１２３４', '1234'))
        num = normalized.strip()
        if num in ('1', '2', '3', '4'):
            category = CATEGORY_LABELS[num]
            user_sessions[key] = {**session, 'step': 'done', 'category': category}
            try:
                saju   = LineManse.calculate(session['year'], session['month'], session['day'])
                ai     = MalgeumLineAI()
                result = ai.get_prescription(saju, mode='short', birth_time=session.get('birth_time', '不明'), category=category)
                return result
            except Exception as e:
                return f"❌ エラーが発生しました: {e}"
        return "1〜4の番号でお選びください。🌿"

    if step == 'WAITING_PARTNER':
        normalized = message.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
        digits = ''.join(filter(str.isdigit, normalized))
        if len(digits) == 8:
            try:
                p_year  = int(digits[0:4])
                p_month = int(digits[4:6])
                p_day   = int(digits[6:8])
                if not (1920 <= p_year <= 2010) or not (1 <= p_month <= 12) or not (1 <= p_day <= 31):
                    return "❌ 正しい生年月日を入力してください。\n例）19970901"
                if 'year' not in session:
                    user_sessions[key] = {}
                    return ("まず「扉を開く」と入力して、\n"
                            "生年月日を教えてください。🌿\n"
                            "その後、魂の共鳴をお楽しみいただけます。")
                user_sessions[key] = {**session, 'partner_birth': {'year': p_year, 'month': p_month, 'day': p_day}}
                threading.Thread(
                    target=compatibility_analysis,
                    args=(user_id, session['year'], session['month'], session['day'],
                          p_year, p_month, p_day, 'preview'),
                    daemon=True
                ).start()
                return "少々お待ちくださいませ。🌙"
            except Exception:
                return "❌ 8桁の数字で入力してください。\n例）19970901"
        return "❌ 8桁の数字で入力してください。\n例）19970901"

    if step == 'booking':
        if re.search(r'\d+[月日時分]|[月日時]\d+', message):
            session['step'] = 'done'
            user_sessions[key] = session
            return (f"ご予約を承りました。✨\n"
                    f"日時：{message}\n"
                    "当日の時間に合わせてご連絡いたします。🌿\n"
                    "最初に戻りたい方は「マルム」とご入力ください。🌿")
        return ("ご希望の日時を入力してください。\n"
                "例）4月25日 20時\n"
                "最初に戻りたい方は「マルム」とご入力ください。🌿")

    if step == 'done':
        return ("ご決済後は「処方箋を開く」とご入力ください。✅\n"
                "最初に戻りたい方は「マルム」とご入力ください。🌿")

    return "こんにちは！「扉を開く」と入力してください。🌿"

# ============================================================================
# 서버 실행
# ============================================================================
if __name__ == '__main__':
    print("\n🚀 맑음(マルム) 서버 시작!")
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
