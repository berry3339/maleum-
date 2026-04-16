import os
import threading
from flask import Flask, request, jsonify
from mind_pillar import PrecisionManse, MalgeumAI
from mind_pillar_line import PrecisionManse as LineManse, MalgeumLineAI

app = Flask(__name__)
user_sessions = {}

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
            ai = MalgeumAI()
            prescription = ai.get_prescription(saju)
            user_sessions[f'kakao_{user_id}'] = {}
            return f"🌟 Mind-Pillar 처방전\n{'='*30}\n{prescription}\n\n다시 받으려면 '시작'을 입력하세요."
        except Exception as e:
            return f"❌ 오류: {e}"
    return "안녕하세요! '시작'을 입력해주세요. 🏛️"

# ============================================================================
# LINE 챗봇
# ============================================================================
@app.route('/line', methods=['POST'])
def line():
    try:
        import requests
        data = request.get_json()
        for event in data.get('events', []):
            if event['type'] == 'message' and event['message']['type'] == 'text':
                user_id = event['source']['userId']
                message = event['message']['text'].strip()
                reply_token = event['replyToken']
                response_text = process_line(user_id, message)
                requests.post(
                    'https://api.line.me/v2/bot/message/reply',
                    headers={
                        'Authorization': f"Bearer {os.getenv('LINE_CHANNEL_ACCESS_TOKEN')}",
                        'Content-Type': 'application/json'
                    },
                    json={'replyToken': reply_token, 'messages': [{'type': 'text', 'text': response_text}]}
                )
        return jsonify({'status': 'ok'})
    except Exception as e:
        print(f"LINE 오류: {e}")
        return jsonify({'status': 'error'})

def process_line(user_id, message):
    key = f'line_{user_id}'
    if message in ['start', 'はじめ', 'スタート', 'こんにちは', '안녕']:
        user_sessions[key] = {'step': 'date'}
        return "🌟 맑음へようこそ！\n\n生年月日を8桁の数字で送ってください。\n例）19930616"
    session = user_sessions.get(key, {})
    step = session.get('step')
    if step == 'date':
        normalized = message.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
        digits = ''.join(filter(str.isdigit, normalized))
        if len(digits) == 8:
            try:
                year = int(digits[0:4])
                month = int(digits[4:6])
                day = int(digits[6:8])
                if not (1920 <= year <= 2010):
                    return "❌ 正しい生年月日を入力してください。\n例）19930616"
                if not (1 <= month <= 12):
                    return "❌ 正しい生年月日を入力してください。\n例）19930616"
                if not (1 <= day <= 31):
                    return "❌ 正しい生年月日を入力してください。\n例）19930616"
                user_sessions[key] = {'step': 'waiting', 'year': year, 'month': month, 'day': day}
                def make_prescription():
                    try:
                        saju = LineManse.calculate(year, month, day)
                        ai = MalgeumLineAI()
                        result = ai.get_prescription(saju, mode='short')
                        user_sessions[key] = {}
                    except Exception as e:
                        print(f"처방전 오류: {e}")
                threading.Thread(target=make_prescription, daemon=True).start()
                saju = LineManse.calculate(year, month, day)
                ai = MalgeumLineAI()
                result = ai.get_prescription(saju, mode='short')
                user_sessions[key] = {}
                return result
            except Exception as e:
                return f"❌ エラーが発生しました: {e}"
        return "❌ 8桁の数字で入力してください。\n例）19930616"
    return "こんにちは！「start」と入力してください。🌿"

# ============================================================================
# 서버 실행
# ============================================================================
if __name__ == '__main__':
    print("\n🚀 맑음 서버 시작!")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
