import os
import json
import re
import random
import string
import time
import threading
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify
from mind_pillar import PrecisionManse, MindPillarAI
from mind_pillar_line import PrecisionManse as LineManse, MalgeumLineAI, split_message, send_long_message, build_prescription_cards, build_kyoumei_card, build_kyoumei_chemistry_card, build_kyoumei_mission_card, build_kyoumei_preview_card, build_mystery_kyoumei_card, build_mystery_fukuen_card, build_fukuen_omamori_card, build_payment_ticket_card, build_fukuen_payment_ticket_card
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

def generate_payment_code():
    return 'MARU-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

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
    today = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y年%m月%d日")
    users = load_users()
    if not users:
        return
    print(f"⏰ [朝のメッセージ] {today} | {len(users)}명에게 발송 시작")
    for uid, data in users.items():
        try:
            saju          = LineManse.calculate(data['year'], data['month'], data['day'])
            ai            = MalgeumLineAI()
            result        = ai.get_prescription(saju, mode='preview')
            if isinstance(result, dict):
                msg_payload = {"type": "flex", "altText": "🌅 朝のエネルギーガイドをお届けします", "contents": result}
            else:
                msg_payload = {"type": "text", "text": "🌅 朝のメッセージ\n\n" + result}
            req.post(
                'https://api.line.me/v2/bot/message/push',
                headers={
                    'Authorization': f"Bearer {os.getenv('LINE_CHANNEL_ACCESS_TOKEN')}",
                    'Content-Type': 'application/json'
                },
                json={'to': uid, 'messages': [msg_payload]},
                timeout=30
            )
            follow_text = ("今日のあなたに、\n"
                           "まだ届いていないメッセージがあります🌙\n\n"
                           "詳しく知りたい方は\n"
                           "「運勢を見る」と入力してください🌸")
            req.post(
                'https://api.line.me/v2/bot/message/push',
                headers={
                    'Authorization': f"Bearer {os.getenv('LINE_CHANNEL_ACCESS_TOKEN')}",
                    'Content-Type': 'application/json'
                },
                json={'to': uid, 'messages': [{"type": "text", "text": follow_text}]},
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
def _build_line_message(payload):
    """str → textメッセージ, dict(type=text) → Quick Reply, dict → Flex Messageに変換"""
    if isinstance(payload, dict) and payload.get('type') == 'text':
        return payload
    if isinstance(payload, dict):
        return {"type": "flex", "altText": "今日の運勢をお届けします🌿", "contents": payload}
    return {"type": "text", "text": payload}

def build_quick_reply_message(text, labels):
    """Quick Reply 버튼이 달린 텍스트 메시지 dict 반환"""
    return {
        "type": "text",
        "text": text,
        "quickReply": {
            "items": [
                {"type": "action", "action": {"type": "message", "label": l, "text": l}}
                for l in labels
            ]
        }
    }

def line_reply_api(reply_token, payload):
    """LINE reply API 호출 (text str または Flex dict を受け付ける)"""
    import requests as req
    try:
        msg = _build_line_message(payload)
        print(f"📤 [LINE reply] type={msg['type']}")
        resp = req.post(
            'https://api.line.me/v2/bot/message/reply',
            headers={
                'Authorization': f"Bearer {os.getenv('LINE_CHANNEL_ACCESS_TOKEN')}",
                'Content-Type': 'application/json'
            },
            json={'replyToken': reply_token, 'messages': [msg]},
            timeout=15
        )
        if resp.status_code != 200:
            print(f"❌ [LINE reply] status={resp.status_code} body={resp.text[:200]}")
        else:
            print(f"✅ [LINE reply] status=200")
    except Exception as e:
        print(f"❌ [LINE reply 실패] {e}")

def line_push_api(user_id, payload):
    """LINE push API 호출 (text str または Flex dict を受け付ける)"""
    import requests as req
    try:
        resp = req.post(
            'https://api.line.me/v2/bot/message/push',
            headers={
                'Authorization': f"Bearer {os.getenv('LINE_CHANNEL_ACCESS_TOKEN')}",
                'Content-Type': 'application/json'
            },
            json={'to': user_id, 'messages': [_build_line_message(payload)]},
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
            # スコア計算（Flexカードと同じロジック）
            _GEN = {'木':'火','火':'土','土':'金','金':'水','水':'木'}
            _RES = {'木':'土','土':'水','水':'火','火':'金','金':'木'}
            _u = saju.get('ohaeng', '水')
            _today_s = LineManse.calculate(
                datetime.now(ZoneInfo("Asia/Tokyo")).year,
                datetime.now(ZoneInfo("Asia/Tokyo")).month,
                datetime.now(ZoneInfo("Asia/Tokyo")).day
            )
            _t = _today_s.get('ohaeng', '水')
            if _u == _t:             _base = 78
            elif _GEN.get(_t) == _u: _base = 90
            elif _GEN.get(_u) == _t: _base = 82
            elif _RES.get(_u) == _t: _base = 68
            else:                    _base = 55
            _dp = saju.get('day_pillar', '')
            _var = ord(_dp[1]) % 7 - 3 if len(_dp) >= 2 else 0
            score = max(50, min(95, _base + _var))

            payment_code = generate_payment_code()
            key = f'line_{user_id}'
            session = user_sessions.get(key, {})
            user_sessions[key] = {**session, 'payment_code': payment_code}
            line_push_api(user_id, result)
            line_push_api(user_id, "推しとの相性度が気になる？\n推しとの運命の処方せんを受け取ってね🌙")
            line_push_api(user_id, build_payment_ticket_card(
                1000,
                "https://www.paypal.com/ncp/payment/G7K49PXY32R2C",
                payment_code,
                "今日の運気処方箋"
            ))
            line_push_api(user_id, f"🔑 決済後にこのコードを送ってね：\n{payment_code}")
        else:  # prescription
            # score 계산 (short mode와 동일한 로직)
            _GEN = {'木':'火','火':'土','土':'金','金':'水','水':'木'}
            _RES = {'木':'土','土':'水','水':'火','火':'金','金':'木'}
            u = saju.get('day_ohaeng', '水')
            t = saju.get('today_ohaeng', '水')
            if u == t:             base = 78
            elif _GEN.get(t) == u: base = 90
            elif _GEN.get(u) == t: base = 82
            elif _RES.get(u) == t: base = 68
            else:                  base = 55
            dp = saju.get('day_pillar', '')
            variation = ord(dp[1]) % 7 - 3 if len(dp) >= 2 else 0
            score = max(50, min(95, base + variation))
            # ミッション導入部を挿入
            if '【運気ミッション】' in result:
                mission_intro = (
                    f"━━ 運気ミッション ━━\n"
                    f"今日の{score}点をさらに上げるチャンス。\n"
                    f"行動ひとつで、流れが変わります🌙\n\n"
                )
                result = result.replace('【運気ミッション】', mission_intro + '【運気ミッション】', 1)
            result = _filter_time_lines(result)
            # カード5枚（本質/エネルギー/ラッキー/ミッション/辛口）を先に発送
            try:
                cards = build_prescription_cards(result, saju)
                line_push_api(user_id, cards)
            except Exception as card_err:
                print(f"⚠️ [処方箋カード生成エラー] {card_err}")
            # テキスト処方箋: 全セクション発送
            retention_msg = (
                "\n\n━━━━━━━━━━━━━\n"
                "また気になったときは、\n"
                "いつでも話しかけてくださいね🌿"
            )
            line_push_api(user_id, result + retention_msg)
    except Exception as e:
        print(f"❌ [深層解読오류] {e}")
        line_push_api(user_id, "❌ エラーが発生しました。もう一度お試しください。")

def compatibility_analysis(user_id, year, month, day, p_year, p_month, p_day, mode='preview', partner_name=None):
    """궁합 분석 → push API — background thread에서 실행"""
    try:
        saju1  = LineManse.calculate(year, month, day)
        saju2  = LineManse.calculate(p_year, p_month, p_day)
        ai     = MalgeumLineAI()
        result = ai.get_compatibility(saju1, saju2, mode=mode)
        if mode == 'preview':
            kyoumei_code = 'KYOUMEI-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            s_key = f'line_{user_id}'
            user_sessions[s_key] = {**user_sessions.get(s_key, {}), 'kyoumei_code': kyoumei_code}
            # ①ミステリーカード
            line_push_api(user_id, build_mystery_kyoumei_card())
            # ②ケミ プレビューカード (APIテキストからケミ1行を抽出)
            import re as _re2
            _clean2 = result.replace('*','').replace('#','')
            _chemi = _re2.search(r'ケミ[：:]\s*(.+?)[\n]', _clean2)
            _chemi_text = _chemi.group(1).strip() if _chemi else "ふたりのシンクロ✨"
            line_push_api(user_id, build_kyoumei_preview_card(_chemi_text))
            # ③感性メッセージ
            line_push_api(user_id, "推しとの相性度が気になる？\n推しとの運命の処方せんを受け取ってね🌙")
            # ④決済チケットカード
            line_push_api(user_id, build_payment_ticket_card(
                590,
                "https://www.paypal.com/ncp/payment/DP7F3FT8NDW9E",
                kyoumei_code,
                "推しとの運命の処方箋"
            ))
            # ⑤コードテキスト
            line_push_api(user_id, f"🔑 決済後にこのコードを送ってね：\n{kyoumei_code}")
        else:
            # カード1: ケミ+役割
            try:
                line_push_api(user_id, build_kyoumei_chemistry_card(result))
            except Exception as e:
                print(f"⚠️ [ケミカード生成エラー] {e}")
            # カード2: ミッション+注意+シンクロ
            try:
                line_push_api(user_id, build_kyoumei_mission_card(result))
            except Exception as e:
                print(f"⚠️ [ミッションカード生成エラー] {e}")
            # テキスト: ラッキーアイテムのみ抽出
            import re as _re
            _clean = result.replace('*','').replace('#','')
            _header_m = _re.search(r'✨\s*今日の推し活ラッキー', _clean)
            if _header_m:
                _after = _clean[_header_m.start():]
                _color = _re.search(r'🎨[^\n]+', _after)
                _item  = _re.search(r'🌿[^\n]+', _after)
                _time  = _re.search(r'⏰[^\n]+', _after)
                _kw    = _re.search(r'💬[^\n]+', _after)
                _parts = ["✨ 今日の推し活ラッキー"]
                for _m in [_color, _item, _time, _kw]:
                    if _m:
                        _parts.append(_m.group(0).strip())
                if len(_parts) > 1:
                    line_push_api(user_id, '\n'.join(_parts))
            # カード3: 相性度
            try:
                line_push_api(user_id, build_kyoumei_card(result, partner_name=partner_name))
            except Exception as e:
                print(f"⚠️ [相性カード生成エラー] {e}")
            # 유료 리포트 후 추가 메시지 3개
            time.sleep(1.5)
            line_push_api(user_id,
                "この結果、推し友にも教えてあげない？🌙\n"
                "スクショしてストーリーに載せてみてね✨\n"
                "みんなの相性度も気になるでしょ💖"
            )
            time.sleep(1.5)
            line_push_api(user_id,
                "他の推しとの相性度も気になる？🌙\n"
                "もう一度「推しとの相性」って送ってみてね✨"
            )
            time.sleep(1.5)
            line_push_api(user_id,
                "🌙 明日、推しとの相性度がどう変わるかな？\n"
                "また気になったときに話しかけてね✨"
            )
            time.sleep(1.5)
            line_push_api(user_id,
                "🌙 恋の悩みがあったら「あの人」って送ってみてね\n"
                "復縁の可能性、調べてあげるよ✨"
            )
    except Exception as e:
        print(f"❌ [궁합분석오류] {e}")
        line_push_api(user_id, "❌ エラーが発生しました。もう一度お試しください。")

def fukuen_analysis(user_id, year, month, day, p_year, p_month, p_day, mode='preview', partner_name=None):
    """재회 분석 → push API — background thread에서 실행"""
    try:
        saju1  = LineManse.calculate(year, month, day)
        saju2  = LineManse.calculate(p_year, p_month, p_day)
        ai     = MalgeumLineAI()
        result = ai.get_fukuen(saju1, saju2, partner_name=partner_name, mode=mode)
        if mode == 'preview':
            fukuen_code = 'FUKUEN-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            s_key = f'line_{user_id}'
            user_sessions[s_key] = {**user_sessions.get(s_key, {}), 'fukuen_code': fukuen_code}
            line_push_api(user_id, result)
            line_push_api(user_id,
                "🔮 あの人の性格、3つのキーワード\n\n"
                "・一度好きになったら忘れられない一途さ\n"
                "・プライドが高くて、自分から連絡できないタイプ\n"
                "・でも夜になると気持ちがゆるんで、あなたのSNSをこっそり見てるかも"
            )
            line_push_api(user_id,
                "⚠️ 今、連絡したらどうなる？\n\n"
                "今すぐ連絡すると、あの人は\n"
                "「嬉しいけど、素直になれない」状態。\n"
                "既読スルーされる可能性が高いけど、\n"
                "それは\"嫌い\"じゃなくて\"どうしていいかわからない\"だよ🌙"
            )
            line_push_api(user_id, build_fukuen_omamori_card())
            line_push_api(user_id, build_mystery_fukuen_card())
            line_push_api(user_id, build_fukuen_payment_ticket_card(
                890,
                "https://www.paypal.com/ncp/payment/R2LWTQ2NYKEX2"
            ))
            line_push_api(user_id, f"🔑 決済後にこのコードを送ってね：\n{fukuen_code}")
        else:
            # 유료 리포트를 섹션 헤더 기준으로 4개 메시지로 분할 전송
            def _extract(text, start_markers, end_markers):
                """start_markers 중 첫 번째 등장 위치 ~ end_markers 직전까지 추출"""
                s = len(text)
                for m in start_markers:
                    idx = text.find(m)
                    if idx != -1:
                        s = min(s, idx)
                e = len(text)
                for m in end_markers:
                    idx = text.find(m, s + 1)
                    if idx != -1:
                        e = min(e, idx)
                return text[s:e].strip()

            msg1 = _extract(result,
                ["💜", "🌙 あの人"],
                ["✨ ふたりの縁", "🔋"])
            msg2 = _extract(result,
                ["✨ ふたりの縁", "🔋"],
                ["🎯"])
            msg3 = _extract(result,
                ["🎯"],
                ["📸"])
            msg4 = _extract(result,
                ["📸"],
                [])

            for msg in [msg1, msg2, msg3, msg4]:
                if msg:
                    line_push_api(user_id, msg)
                    time.sleep(1.5)

            line_push_api(user_id,
                "🌙 3日後、あの人の気持ちに\n"
                "もう一度変化がくるよ。\n\n"
                "そのとき、またここに来てね。\n"
                "新しい波動を読んであげる✨"
            )
            time.sleep(1.5)
            line_push_api(user_id,
                "💖 推しとの相性もやってみない？\n"
                "下のメニューから「推しとの相性」をタップしてね✨"
            )
            # TODO: LINE友だち追加URL取得後に有効化
            # line_push_api(user_id,
            #     "💌 もし周りに恋で悩んでる子がいたら\n"
            #     "このリンクを送ってあげてね。\n\n"
            #     "あなたと同じように\n"
            #     "救われるかもしれないから🌙\n\n"
            #     "👉 https://line.me/R/ti/p/@XXXXXXX"
            # )
    except Exception as e:
        print(f"❌ [재회분석오류] {e}")
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
                if message in ('魂の処方箋', '詳細レポート'):
                    key = f'line_{user_id}'
                    session = user_sessions.get(key, {})
                    if 'year' in session:
                        line_reply_api(reply_token,
                            "🌀 詳細レポートを準備します。\n"
                            "少し待っててね🌿"
                        )
                        threading.Thread(
                            target=deep_analysis,
                            args=(user_id, session['year'], session['month'], session['day'], 'preview', session.get('birth_time', '不明'), session.get('category')),
                            daemon=True
                        ).start()
                    else:
                        line_reply_api(reply_token, "まず「運勢を見る」と入力してください。🌿")
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

    # MARU- コード グローバル認識 (セッション状態に関係なく即実行)
    if message.strip().startswith('MARU-'):
        session = user_sessions.get(key, {})
        stored_code = session.get('payment_code', '')
        if stored_code and message.strip() == stored_code:
            if 'year' in session:
                new_session = {k: v for k, v in session.items() if k != 'payment_code'}
                new_session['step'] = 'done'
                user_sessions[key] = new_session
                threading.Thread(
                    target=deep_analysis,
                    args=(user_id, session['year'], session['month'], session['day'], 'prescription', session.get('birth_time', '不明'), session.get('category')),
                    daemon=True
                ).start()
                return ("🌀 決済を確認しました。\n\n"
                        "🔮 お客様の大切な一日に\n"
                        "完璧な答えをお届けするため、\n"
                        "誠心誠意、分析を深めております。\n\n"
                        "精緻な結果を導き出すため、\n"
                        "今しばらくお待ちくださいませ🌿")
            return "まず生年月日を入力してください🌿"
        return "コードが正しくありません。もう一度お試しください。🌿"

    # KYOUMEI- コード グローバル認識 (推し相性決済)
    if message.strip().startswith('KYOUMEI-'):
        session = user_sessions.get(key, {})
        stored_code = session.get('kyoumei_code', '')
        if stored_code and message.strip() == stored_code:
            partner = session.get('partner_birth')
            if 'year' in session and partner:
                user_sessions[key] = {k: v for k, v in session.items() if k != 'kyoumei_code'}
                threading.Thread(
                    target=compatibility_analysis,
                    args=(user_id, session['year'], session['month'], session['day'],
                          partner['year'], partner['month'], partner['day'], 'full',
                          session.get('partner_name')),
                    daemon=True
                ).start()
                return "🌀 決済を確認しました。\n推しとの運命の処方箋の封を切ります..."
            return "まず「推し相性」から始めてください🌿"
        return "コードが正しくありません。🌿"

    # FUKUEN- コード グローバル認識 (復縁決済)
    if message.strip().startswith('FUKUEN-'):
        session = user_sessions.get(key, {})
        stored_code = session.get('fukuen_code', '')
        if stored_code and message.strip() == stored_code:
            partner = session.get('fukuen_partner_birth')
            if 'year' in session and partner:
                user_sessions[key] = {k: v for k, v in session.items() if k != 'fukuen_code'}
                threading.Thread(
                    target=fukuen_analysis,
                    args=(user_id, session['year'], session['month'], session['day'],
                          partner['year'], partner['month'], partner['day'], 'full',
                          session.get('fukuen_partner_name')),
                    daemon=True
                ).start()
                return "🌀 決済を確認しました。\nあの人との運命の封を切ります..."
            return "まず「あの人」から始めてください🌿"
        return "コードが正しくありません。🌿"

    # 処方箋を開く / レポートを開く
    if message in ('処方箋を開く', 'レポートを開く'):
        session = user_sessions.get(key, {})
        if 'year' in session:
            user_sessions[key] = {**session, 'step': 'WAITING_PAYMENT_CODE'}
            return "🔑 決済コードを入力してください。"
        return "まず生年月日を入力してください🌿"

    # 相性を開く / 相性を見る (유료 전체 궁합, 포함되면 작동)
    if '相性を開く' in message or '相性を見る' in message:
        session = user_sessions.get(key, {})
        partner = session.get('partner_birth')
        if 'year' in session and partner:
            threading.Thread(
                target=compatibility_analysis,
                args=(user_id, session['year'], session['month'], session['day'],
                      partner['year'], partner['month'], partner['day'], 'full'),
                daemon=True
            ).start()
            return "🌀 決済を確認しました。\n相性レポートの封を切ります..."
        return "まず「推し相性」から始めてください🌿"

    # マルム → 처음으로 리셋
    if message == 'マルム':
        user_sessions[key] = {}
        return ("マルムへようこそ🌿\n\n"
                "韓国式四柱推命で、\n"
                "あなたの今日の流れを読み解きます。\n\n"
                "「今日の運勢」\n"
                "入力してください🌸")

    # あの人 / 復縁 → 재회 모드
    if 'あの人' in message or '復縁' in message:
        session = user_sessions.get(key, {})
        user_sessions[key] = {**session, 'step': 'FUKUEN_EMO_Q1'}
        return build_quick_reply_message(
            "あの人のこと、最後に思い出したのはいつ？🌙",
            ["さっき", "今日何回も", "ずっと頭から離れない"]
        )

    # 推しとの相性 / 推し相性 → 글로벌 트리거 (포함되면 작동)
    if '推しとの相性' in message or '推し相性' in message:
        session = user_sessions.get(key, {})
        if 'year' not in session:
            user_sessions[key] = {**session, 'step': 'WAITING_COMPAT_SELF'}
            return ("推し相性をチェックします。🌙\n"
                    "まず、あなた自身の生年月日を\n"
                    "8桁で入力してください。\n"
                    "例）19930616")
        user_sessions[key] = {**session, 'step': 'WAITING_PARTNER'}
        return ("推しのお名前と生年月日を教えてください✨\n"
                "例）カズハ 20010122\n"
                "お名前なしで生年月日だけでもOKです🌙")

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
    if message in ('運勢を見る', '四柱推命で見てみる', '今日の運勢を見る', '今日の運勢', '扉を開く'):
        user_sessions[key] = {'step': 'date'}
        return ("ありがとうございます🌿\n\n"
                "今日の流れ、少しだけ気になりませんか？🌸\n"
                "今のあなたの状態をもとに、\n"
                "やさしく読み解いていきます。\n\n"
                "生年月日を8桁で教えてください✨\n"
                "例）19930616")

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
                # Flex カード返信後、preview テキスト+決済案内をpushで非同期送信
                threading.Thread(
                    target=deep_analysis,
                    args=(user_id, session['year'], session['month'], session['day'],
                          'preview', session.get('birth_time', '不明'), category),
                    daemon=True
                ).start()
                return result
            except Exception as e:
                return f"❌ エラーが発生しました: {e}"
        return "1〜4の番号でお選びください。🌿"

    if step == 'WAITING_PAYMENT_CODE':
        stored_code = session.get('payment_code', '')
        if message.strip() == stored_code:
            new_session = {k: v for k, v in session.items() if k != 'payment_code'}
            new_session['step'] = 'done'
            user_sessions[key] = new_session
            threading.Thread(
                target=deep_analysis,
                args=(user_id, session['year'], session['month'], session['day'], 'prescription', session.get('birth_time', '不明'), session.get('category')),
                daemon=True
            ).start()
            return ("🌀 決済を確認しました。\n"
                    "あなただけの処方箋の封を切ります...\n\n"
                    "このカードを保存して、\n"
                    "今日のお守りにしてください🌿")
        return "コードが正しくありません。もう一度お試しください。🌿"

    if step == 'FUKUEN_EMO_Q1':
        emo_q1 = message
        user_sessions[key] = {**session, 'step': 'FUKUEN_EMO_Q2', 'fukuen_emo_q1': emo_q1}
        return build_quick_reply_message(
            "今の気持ちに近いのはどれ？",
            ["まだ好き。会いたい", "気になるけど、怖い", "忘れたいのに思い出す"]
        )

    if step == 'FUKUEN_EMO_Q2':
        emo_q2 = message
        q1 = session.get('fukuen_emo_q1', '')
        if 'ずっと頭から離れない' in q1:
            emo_reply = "ずっと想い続けてきたんだね。\nその気持ち、あの人に届いてるかもしれないよ。ちょっと調べてみるね🌙"
        elif '今日何回も' in q1:
            emo_reply = "今日もずっと考えてたんだね。\nその気持ち、あの人に届いてるかもしれないよ。ちょっと調べてみるね🌙"
        else:
            emo_reply = "さっきも思い出してたんだね。\nその気持ち、あの人に届いてるかもしれないよ。ちょっと調べてみるね🌙"
        user_sessions[key] = {**session, 'step': 'WAITING_FUKUEN_SELF', 'fukuen_emo_q2': emo_q2}
        return (f"{emo_reply}\n\n"
                "💔 あの人との運命を読み解きます🌙\n\n"
                "まず、あなたの生年月日を\n"
                "8桁で教えてください✨\n"
                "例）19930616")

    if step == 'WAITING_FUKUEN_SELF':
        normalized = message.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
        digits = ''.join(filter(str.isdigit, normalized))
        if len(digits) == 8:
            try:
                year  = int(digits[0:4])
                month = int(digits[4:6])
                day   = int(digits[6:8])
                if not (1920 <= year <= 2010) or not (1 <= month <= 12) or not (1 <= day <= 31):
                    return "❌ 正しい生年月日を入力してください。\n例）19930616"
                user_sessions[key] = {**session, 'step': 'WAITING_FUKUEN_PARTNER',
                                      'year': year, 'month': month, 'day': day}
                return ("相手のお名前と生年月日を教えてください💫\n"
                        "例）ユウタ 19950315\n"
                        "お名前なしで生年月日だけでもOKです🌙")
            except Exception:
                return "❌ 8桁の数字で入力してください。\n例）19930616"
        return "❌ 8桁の数字で入力してください。\n例）19930616"

    if step == 'WAITING_FUKUEN_PARTNER':
        normalized = message.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
        date_match = re.search(r'(\d{8})', normalized)
        if date_match:
            try:
                digits  = date_match.group(1)
                p_year  = int(digits[0:4])
                p_month = int(digits[4:6])
                p_day   = int(digits[6:8])
                if not (1920 <= p_year <= 2010) or not (1 <= p_month <= 12) or not (1 <= p_day <= 31):
                    return "❌ 正しい生年月日を入力してください。\n例）ユウタ 19950315"
                if 'year' not in session:
                    user_sessions[key] = {}
                    return "まず「あの人」と入力して、生年月日を教えてください🌿"
                partner_name = re.sub(r'\d{8}', '', message).strip() or None
                user_sessions[key] = {**session,
                    'fukuen_partner_birth': {'year': p_year, 'month': p_month, 'day': p_day},
                    'fukuen_partner_name': partner_name}
                threading.Thread(
                    target=fukuen_analysis,
                    args=(user_id, session['year'], session['month'], session['day'],
                          p_year, p_month, p_day, 'preview', partner_name),
                    daemon=True
                ).start()
                return "少し待っててね。\nふたりの縁の糸をたどってるから…🌙"
            except Exception:
                return "❌ お名前と生年月日を入力してください。\n例）ユウタ 19950315"
        return "❌ お名前と生年月日を入力してください。\n例）ユウタ 19950315"

    if step == 'WAITING_COMPAT_SELF':
        normalized = message.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
        digits = ''.join(filter(str.isdigit, normalized))
        if len(digits) == 8:
            try:
                year  = int(digits[0:4])
                month = int(digits[4:6])
                day   = int(digits[6:8])
                if not (1920 <= year <= 2010) or not (1 <= month <= 12) or not (1 <= day <= 31):
                    return "❌ 正しい生年月日を入力してください。\n例）19930616"
                user_sessions[key] = {**session, 'step': 'WAITING_PARTNER', 'year': year, 'month': month, 'day': day}
                return ("推しのお名前と生年月日を教えてください✨\n"
                        "例）カズハ 20010122\n"
                        "お名前なしで生年月日だけでもOKです🌙")
            except Exception:
                return "❌ 8桁の数字で入力してください。\n例）19930616"
        return "❌ 8桁の数字で入力してください。\n例）19930616"

    if step == 'WAITING_PARTNER':
        normalized = message.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
        date_match = re.search(r'(\d{8})', normalized)
        if date_match:
            try:
                digits  = date_match.group(1)
                p_year  = int(digits[0:4])
                p_month = int(digits[4:6])
                p_day   = int(digits[6:8])
                if not (1920 <= p_year <= 2010) or not (1 <= p_month <= 12) or not (1 <= p_day <= 31):
                    return "❌ 正しい生年月日を入力してください。\n例）カズハ 20010122"
                if 'year' not in session:
                    user_sessions[key] = {}
                    return ("まず「運勢を見る」と入力して、\n"
                            "生年月日を教えてください。🌿\n"
                            "その後、推し相性をお楽しみいただけます。")
                # 名前: 数字8桁を除いた残り
                partner_name = re.sub(r'\d{8}', '', message).strip() or None
                user_sessions[key] = {**session,
                    'partner_birth': {'year': p_year, 'month': p_month, 'day': p_day},
                    'partner_name': partner_name}
                threading.Thread(
                    target=compatibility_analysis,
                    args=(user_id, session['year'], session['month'], session['day'],
                          p_year, p_month, p_day, 'preview', partner_name),
                    daemon=True
                ).start()
                return "少し待っててね🌙"
            except Exception:
                return "❌ 名前と生年月日を入力してください。\n例）カズハ 20010122"
        return "❌ 名前と生年月日を入力してください。\n例）カズハ 20010122"

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
        return ("ご決済後は「レポートを開く」とご入力ください。✅\n"
                "最初に戻りたい方は「マルム」とご入力ください。🌿")

    FALLBACK_MSG = ("マルムへようこそ🌙\n\n"
                    "下のメニューからえらんでね✨\n\n"
                    "💖 推しとの相性\n"
                    "🌙 復縁占い\n"
                    "🔮 今日の運勢")
    if not step:
        return FALLBACK_MSG
    return FALLBACK_MSG

# ============================================================================
# 서버 실행
# ============================================================================
if __name__ == '__main__':
    print("\n🚀 マルム 서버 시작!")
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
