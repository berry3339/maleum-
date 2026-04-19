import os
import json
import re
import threading
from flask import Flask, request, jsonify
from mind_pillar import PrecisionManse, MindPillarAI
from mind_pillar_line import PrecisionManse as LineManse, MalgeumLineAI
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

app = Flask(__name__)
user_sessions = {}

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

def deep_analysis(user_id, year, month, day):
    """深層解読 AI 처리 → push API — background thread에서 실행"""
    try:
        saju   = LineManse.calculate(year, month, day)
        ai     = MalgeumLineAI()
        result = ai.get_prescription(saju, mode='long')

        # 4번 섹션 직전에서 절단 (AI가 쓰는 다양한 표記に対応)
        cut_markers = [
            '4.【覚醒への処方箋】',
            '4．【覚醒への処方箋】',
            '4.【魂の処方箋】',
            '4．【魂の処方箋】',
            '【魂の処方箋】',
            '【覚醒への処方箋】',
        ]
        # 위 마커 우선 탐색
        cut_pos = None
        for marker in cut_markers:
            idx = result.find(marker)
            if idx != -1:
                if cut_pos is None or idx < cut_pos:
                    cut_pos = idx

        # 마커 없으면 줄 단위로 '4.'로 시작하는 줄 탐색
        if cut_pos is None:
            for i, line in enumerate(result.splitlines(keepends=True)):
                if line.lstrip().startswith('4.') or line.lstrip().startswith('4．'):
                    cut_pos = result.index(line)
                    break

        if cut_pos is not None:
            result = result[:cut_pos].rstrip()

        payment_msg = (
            "\n\nあなたが今感じている\u300cもやもや\u300dには、実は名前があります。\n"
            "その名前を知ると、動き方が変わります。\n\n"
            "気づいた人だけが使えます。\n"
            "🔒 魂の処方箋を受け取る\n→ https://www.paypal.com/ncp/payment/G7K49PXY32R2C\n"
            "さらに深く話したい方は「鑑定予約」と入力してください。🌙"
        )
        line_push_api(user_id, result + payment_msg)
    except Exception as e:
        print(f"❌ [深層解読오류] {e}")
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
                            "🌀 魂の処方箋を準備します。\n\n"
                            "四柱の深層を紐解くのに少々お時間をいただきます。\n"
                            "今しばらくお待ちくださいませ。"
                        )
                        threading.Thread(
                            target=deep_analysis,
                            args=(user_id, session['year'], session['month'], session['day']),
                            daemon=True
                        ).start()
                    else:
                        line_reply_api(reply_token, "まず生年月日を入力してください。\n例）19930616")
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

    # 鑑定予約
    if message == '鑑定予約':
        session = user_sessions.get(key, {})
        user_sessions[key] = {**session, 'step': 'booking'}
        return ("ご予約はこちらから承ります。\n"
                "🔒 1対1 LINE鑑定（30分 ¥5,000）\n"
                "→ https://www.paypal.com/ncp/payment/4FXDK6WHXU45W\n\n"
                "ご希望の日時を教えてください。\n"
                "例）4月25日 20時")

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
        try:
            saju   = LineManse.calculate(year, month, day)
            ai     = MalgeumLineAI()
            result = ai.get_prescription(saju, mode='short')
            user_sessions[key] = {'step': 'done', 'year': year, 'month': month, 'day': day, 'birth_time': birth_time}
            save_user(user_id, year, month, day)
            return result
        except Exception as e:
            return f"❌ エラーが発生しました: {e}"

    if step == 'booking':
        if re.search(r'\d+[月日時分]|[月日時]\d+', message):
            session['step'] = 'done'
            user_sessions[key] = session
            return (f"ご予約を承りました。✨\n"
                    f"日時：{message}\n"
                    "当日の時間に合わせてご連絡いたします。🌿")
        return "ご希望の日時を教えてください。\n例）4月25日 20時"

    return "こんにちは！「扉を開く」と入力してください。🌿"

# ============================================================================
# 서버 실행
# ============================================================================
if __name__ == '__main__':
    print("\n🚀 맑음(マルム) 서버 시작!")
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
