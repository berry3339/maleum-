import os
import json
import re
import random
import string
import time
import threading
import secrets
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify
from mind_pillar import PrecisionManse, MindPillarAI
from mind_pillar_line import PrecisionManse as LineManse, MalgeumLineAI, split_message, send_long_message, build_prescription_cards, build_kyoumei_card, build_kyoumei_chemistry_card, build_kyoumei_mission_card, build_kyoumei_lucky_card, build_kyoumei_preview_card, build_mystery_kyoumei_card, build_mystery_fukuen_card, build_fukuen_omamori_card, build_payment_ticket_card, build_fukuen_payment_ticket_card, build_mystery_kataomoi_card, build_kataomoi_omamori_card, build_kataomoi_payment_ticket_card, build_oshi_ranking_card, build_ziwei_summary_card
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

MINI_PRICE = 390

def convert_jp_hour_to_iztro(hour: int) -> int:
    """일본시간(UTC+9) → iztro-py용 UTC+8 시간 변환"""
    adjusted = hour - 1
    return adjusted if adjusted >= 0 else 23

def hour_to_time_index(hour: int) -> int:
    """UTC+8 hour → iztro-py time_index(0~12) 변환
    0=早子時(00~01) / 1=丑(01~03) / ... / 12=晚子時(23~00)
    """
    return (hour + 1) // 2

def generate_payment_code():
    return 'MARU-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

USERS_FILE = '/data/users.json'
IPN_PENDING_FILE = '/data/ipn_pending.json'
TOKENS_FILE = '/data/payment_tokens.json'

def load_payment_tokens():
    try:
        with open(TOKENS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def save_payment_tokens(data):
    os.makedirs(os.path.dirname(TOKENS_FILE), exist_ok=True)
    with open(TOKENS_FILE, 'w') as f:
        json.dump(data, f)

def register_payment_token(token, user_id, service, code):
    tokens = load_payment_tokens()
    tokens[token] = {'user_id': user_id, 'service': service, 'code': code}
    save_payment_tokens(tokens)

def load_ipn_pending():
    try:
        with open(IPN_PENDING_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def save_ipn_pending(data):
    os.makedirs(os.path.dirname(IPN_PENDING_FILE), exist_ok=True)
    with open(IPN_PENDING_FILE, 'w') as f:
        json.dump(data, f)

def register_ipn_pending(user_id, service_type, code):
    pending = load_ipn_pending()
    pending[f'{user_id}_{service_type}'] = code
    save_ipn_pending(pending)

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

def save_fukuen_paid(user_id, year, month, day, partner_birth):
    users = load_users()
    today_str = datetime.now(ZoneInfo("Asia/Tokyo")).strftime('%Y-%m-%d')
    if user_id not in users:
        users[user_id] = {}
    users[user_id].update({'year': year, 'month': month, 'day': day,
                           'fukuen_paid_date': today_str, 'fukuen_partner': partner_birth})
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def save_kataomoi_paid(user_id, year, month, day, partner_birth):
    users = load_users()
    today_str = datetime.now(ZoneInfo("Asia/Tokyo")).strftime('%Y-%m-%d')
    if user_id not in users:
        users[user_id] = {}
    users[user_id].update({'year': year, 'month': month, 'day': day,
                           'kataomoi_paid_date': today_str, 'kataomoi_partner': partner_birth})
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def save_kyoumei_paid(user_id, year, month, day, partner_birth, partner_name=None, score=0):
    users = load_users()
    today_str = datetime.now(ZoneInfo("Asia/Tokyo")).strftime('%Y-%m-%d')
    if user_id not in users:
        users[user_id] = {}
    users[user_id].update({'year': year, 'month': month, 'day': day,
                           'kyoumei_paid_date': today_str, 'kyoumei_partner': partner_birth})
    if partner_name:
        users[user_id]['kyoumei_partner_name'] = partner_name
    # kyoumei_history: partner_name 없으면 기존 저장값으로 fallback
    name_key = partner_name or users[user_id].get('kyoumei_partner_name') or '不明'
    history = users[user_id].get('kyoumei_history', [])
    history = [h for h in history if h.get('name') != name_key]
    history.append({'name': name_key, 'score': score, 'date': today_str})
    users[user_id]['kyoumei_history'] = history
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
            follow_text = ("今日のあなたに届いたメッセージがあるよ🌙\n"
                           "下のメニューから見てみてね✨")
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
# KOMOJU 심사용 정적 페이지 (소개 / 특정상거래법 표기 / 이용약관)
# ============================================================================

ABOUT_HTML = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>マルム（Marumu）｜占いを題材としたエンタメコンテンツ</title>
<style>
:root{--navy:#1a2744;--navy2:#22325a;--gold:#C9A96E;--ink:#2a2f3a;--line:#e3e6ec;--paper:#fbfbfc;}
*{box-sizing:border-box;}
body{margin:0;color:var(--ink);background:var(--paper);font-family:"Hiragino Kaku Gothic ProN","Yu Gothic","Meiryo",sans-serif;line-height:1.85;}
.hero{background:linear-gradient(160deg,var(--navy) 0%,var(--navy2) 100%);color:#fff;text-align:center;padding:74px 24px 64px;}
.hero .mark{font-size:13px;letter-spacing:.5em;color:var(--gold);margin:0 0 18px;}
.hero h1{font-family:"Hiragino Mincho ProN","Yu Mincho",serif;font-size:30px;font-weight:600;margin:0 0 16px;letter-spacing:.06em;}
.hero p{font-size:15px;color:#c5cbd8;max-width:520px;margin:0 auto;}
.rule{width:46px;height:2px;background:var(--gold);margin:24px auto 0;}
.wrap{max-width:720px;margin:0 auto;padding:56px 24px 80px;}
section{margin-bottom:52px;}
h2{font-size:13px;letter-spacing:.28em;color:var(--gold);font-weight:700;margin:0 0 18px;text-transform:uppercase;}
.lead{font-size:15.5px;color:var(--ink);}
.steps{counter-reset:s;padding:0;margin:0;list-style:none;}
.steps li{position:relative;padding:14px 0 14px 52px;border-bottom:1px solid var(--line);font-size:14.5px;}
.steps li:before{counter-increment:s;content:counter(s);position:absolute;left:0;top:12px;width:32px;height:32px;border-radius:50%;background:var(--navy);color:var(--gold);display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:600;}
.cards{display:grid;grid-template-columns:1fr 1fr;gap:14px;}
.card{background:#fff;border:1px solid var(--line);border-radius:10px;padding:18px;}
.card .name{font-weight:600;color:var(--navy);font-size:15px;margin:0 0 4px;}
.card .price{color:var(--gold);font-weight:700;font-size:15px;}
.card .desc{font-size:13px;color:#666c78;margin:6px 0 0;}
.disc{font-size:12.5px;color:#7a8090;background:#f5f6f8;border-radius:10px;padding:16px 18px;}
footer{border-top:1px solid var(--line);text-align:center;padding:28px 24px;font-size:12.5px;color:#7a8090;}
footer a{color:var(--navy);margin:0 10px;text-decoration:none;}
@media(max-width:560px){.cards{grid-template-columns:1fr;}.hero h1{font-size:25px;}}
</style></head><body>
<div class="hero">
<p class="mark">MARUMU</p>
<h1>マルム</h1>
<p>占いを題材とした、エンタテインメントのためのデジタルコンテンツ。LINEで気軽に、あなたのための鑑定をお届けします。</p>
<div class="rule"></div>
</div>
<div class="wrap">
<section>
<h2>サービスについて</h2>
<p class="lead">マルムは、四柱推命などの占いを題材としたエンタテインメント・コンテンツ提供サービスです。LINE公式アカウント上でご購入いただくと、鑑定結果をテキストおよび画像コンテンツとして即時にお届けします。あくまで娯楽としてお楽しみいただくものであり、結果を保証したり、特定の行動を促すものではありません。</p>
</section>
<section>
<h2>ご利用の流れ</h2>
<ol class="steps">
<li>LINEでマルム公式アカウントを友だち追加します。</li>
<li>ご希望のコンテンツを選び、購入手続きに進みます。</li>
<li>購入画面に表示される金額をご確認のうえ、決済します。</li>
<li>決済完了後、鑑定結果のコンテンツをLINE上で即時に受け取れます。</li>
</ol>
</section>
<section>
<h2>コンテンツと価格</h2>
<div class="cards">
<div class="card"><p class="name">推し相性鑑定</p><p class="price">590円（税込）</p><p class="desc">気になる相手との相性を占いの観点から読み解くコンテンツ。</p></div>
<div class="card"><p class="name">恋愛・復縁鑑定</p><p class="price">890円（税込）</p><p class="desc">恋愛や関係の流れを題材にした鑑定コンテンツ。</p></div>
<div class="card"><p class="name">デイリー鑑定</p><p class="price">1,000円（税込）</p><p class="desc">その日の運勢を題材にしたコンテンツ。</p></div>
<div class="card"><p class="name">プレミアム鑑定</p><p class="price">2,980円（税込）</p><p class="desc">より詳しい内容を題材としたプレミアムコンテンツ。</p></div>
</div>
</section>
<section>
<h2>ご注意</h2>
<p class="disc">本サービスで提供する鑑定結果は、エンタテインメントを目的としたコンテンツです。将来や結果を保証するものではなく、不安をあおって購入を促すものでもありません。ご自身の判断の参考として、娯楽の範囲でお楽しみください。価格・決済方法・提供時期・返品条件等の詳細は、「特定商取引法に基づく表記」をご確認ください。</p>
</section>
</div>
<footer>
<a href="/tokushoho">特定商取引法に基づく表記</a>
<a href="/terms">利用規約</a>
</footer>
</body></html>"""


TOKUSHOHO_HTML = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>特定商取引法に基づく表記 | マルム（Marumu）</title>
<style>
:root{--navy:#1a2744;--gold:#C9A96E;--ink:#2a2f3a;--line:#e3e6ec;--bg:#fbfbfc;}
*{box-sizing:border-box;}
body{margin:0;font-family:"Hiragino Kaku Gothic ProN","Yu Gothic","Meiryo",sans-serif;color:var(--ink);background:var(--bg);line-height:1.8;font-size:15px;}
.wrap{max-width:760px;margin:0 auto;padding:0 20px 80px;}
header{background:var(--navy);color:#fff;padding:38px 20px 30px;text-align:center;}
header .brand{font-size:13px;letter-spacing:.35em;color:var(--gold);margin:0 0 10px;}
header h1{font-size:21px;font-weight:600;margin:0;letter-spacing:.04em;}
.intro{font-size:13.5px;color:#5c6270;margin:30px 0 22px;}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);}
th,td{text-align:left;vertical-align:top;padding:15px 18px;border-bottom:1px solid var(--line);font-size:14px;}
th{width:38%;background:#f5f6f8;font-weight:600;color:var(--navy);white-space:nowrap;}
td small{color:#7a8090;font-size:12.5px;display:block;margin-top:4px;}
a{color:var(--navy);}
@media(max-width:560px){th,td{display:block;width:100%;}th{border-bottom:none;}}
</style></head><body>
<header><p class="brand">MARUMU</p><h1>特定商取引法に基づく表記</h1></header>
<div class="wrap">
<p class="intro">本サービスは、占いを題材としたエンタテインメント目的のデジタルコンテンツを提供するものです。以下、特定商取引法に基づき必要事項を表示します。</p>
<table>
<tr><th>販売業者</th><td>マルム（Marumu）</td></tr>
<tr><th>運営責任者</th><td>金 民基（KIM MINKI）</td></tr>
<tr><th>所在地</th><td>大韓民国 釜山広域市 沙上区 白楊大路372-22, 102棟803号（注礼洞, 盤都ボラメモストタウン）<br><small>372-22 Baegyang-daero, Sasang-gu, Busan, Republic of Korea</small></td></tr>
<tr><th>電話番号</th><td>+82-10-3097-3899<br><small>受付時間：平日 10:00–18:00（日本時間）</small></td></tr>
<tr><th>メールアドレス</th><td>saintmichel02@gmail.com</td></tr>
<tr><th>販売価格</th><td>各コンテンツの購入画面に表示する価格（590円〜2,980円・税込）<br><small>価格は商品ごとに購入前の画面に表示します。</small></td></tr>
<tr><th>商品代金以外の必要料金</th><td>なし（通信にかかる費用はお客様のご負担となります）</td></tr>
<tr><th>支払方法</th><td>クレジットカード、その他購入画面に表示する決済方法</td></tr>
<tr><th>支払時期</th><td>各決済方法の規定に従い、購入手続き完了時にお支払いが確定します。</td></tr>
<tr><th>商品の引渡時期</th><td>決済完了後、LINE上で即時にコンテンツ（鑑定結果のテキスト・画像）を提供します。<br><small>システム上の事情により遅延が生じた場合は、速やかに提供いたします。</small></td></tr>
<tr><th>返品・キャンセルについて</th><td>デジタルコンテンツという商品の性質上、提供後のお客様のご都合による返品・キャンセル・返金はお受けできません。<br><small>ただし、コンテンツが提供されない、システム不具合により正常に閲覧できない等の場合は、再提供または返金にて対応いたします。</small></td></tr>
<tr><th>動作環境</th><td>LINEアプリが利用可能なスマートフォン等の環境が必要です。</td></tr>
<tr><th>サービスの性質に関する表示</th><td>本サービスはエンタテインメントを目的としたものであり、結果を保証したり、特定の行動を強制するものではありません。</td></tr>
</table>
</div>
</body></html>"""


TERMS_HTML = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>利用規約 | マルム（Marumu）</title>
<style>
:root{--navy:#1a2744;--gold:#C9A96E;--ink:#2a2f3a;--line:#e3e6ec;--bg:#fbfbfc;}
*{box-sizing:border-box;}
body{margin:0;font-family:"Hiragino Kaku Gothic ProN","Yu Gothic","Meiryo",sans-serif;color:var(--ink);background:var(--bg);line-height:1.9;font-size:14.5px;}
header{background:var(--navy);color:#fff;text-align:center;padding:38px 20px 30px;}
header .brand{font-size:13px;letter-spacing:.35em;color:var(--gold);margin:0 0 10px;}
header h1{font-size:21px;font-weight:600;margin:0;letter-spacing:.04em;}
.wrap{max-width:740px;margin:0 auto;padding:40px 22px 80px;}
.intro{font-size:13.5px;color:#5c6270;margin:0 0 30px;}
article{margin-bottom:26px;}
h2{font-size:15px;color:var(--navy);font-weight:600;margin:0 0 8px;border-left:3px solid var(--gold);padding-left:10px;}
ol{margin:6px 0 0;padding-left:1.3em;}
li{margin-bottom:5px;}
.meta{margin-top:40px;font-size:12.5px;color:#7a8090;border-top:1px solid var(--line);padding-top:16px;}
a{color:var(--navy);}
</style></head><body>
<header><p class="brand">MARUMU</p><h1>利用規約</h1></header>
<div class="wrap">
<p class="intro">本利用規約（以下「本規約」）は、マルム（以下「当サービス」）の提供条件およびご利用にあたっての権利義務関係を定めるものです。ご利用の前に必ずお読みください。</p>
<article><h2>第1条（適用）</h2><ol><li>本規約は、当サービスの利用に関する一切に適用されます。</li><li>ユーザーは、当サービスを利用した時点で本規約に同意したものとみなします。</li></ol></article>
<article><h2>第2条（サービスの内容）</h2><ol><li>当サービスは、占いを題材としたエンタテインメント目的のデジタルコンテンツを、LINE上で提供するものです。</li><li>提供されるコンテンツは娯楽を目的としたものであり、内容の的中・成果・将来の結果を保証するものではありません。</li><li>当サービスは、ユーザーに特定の判断や行動を強制するものではありません。最終的な判断はユーザー自身の責任において行ってください。</li></ol></article>
<article><h2>第3条（料金および支払い）</h2><ol><li>ユーザーは、各コンテンツの購入画面に表示された料金を、当サービスが定める方法により支払うものとします。</li><li>料金は購入手続きの完了をもって確定します。</li></ol></article>
<article><h2>第4条（コンテンツの提供）</h2><ol><li>コンテンツは、決済完了後、LINE上で即時に提供されます。</li><li>システム上の事情により提供が遅延した場合、当サービスは速やかに提供するよう努めます。</li></ol></article>
<article><h2>第5条（返品・キャンセル）</h2><ol><li>デジタルコンテンツの性質上、提供後のお客様のご都合による返品・キャンセル・返金はお受けできません。</li><li>前項にかかわらず、コンテンツが提供されない、またはシステム不具合により正常に閲覧できない場合は、再提供または返金にて対応します。</li></ol></article>
<article><h2>第6条（禁止事項）</h2><ol><li>法令または公序良俗に違反する行為。</li><li>当サービスの運営を妨害する行為。</li><li>提供されたコンテンツを無断で複製・転載・再配布する行為。</li><li>その他、当サービスが不適切と判断する行為。</li></ol></article>
<article><h2>第7条（免責事項）</h2><ol><li>当サービスは、コンテンツがエンタテインメントであることに鑑み、その内容に基づいてユーザーが行った判断・行動の結果について責任を負いません。</li><li>当サービスは、通信環境やLINEの仕様変更等、当サービスの合理的な支配を超える事由による不具合について責任を負いません。</li></ol></article>
<article><h2>第8条（規約の変更）</h2><ol><li>当サービスは、必要と判断した場合、本規約を変更できるものとします。変更後の規約は、当サービス上に表示した時点から効力を生じます。</li></ol></article>
<article><h2>第9条（準拠法・お問い合わせ）</h2><ol><li>本規約の解釈にあたっては、別段の定めがない限り、日本の消費者保護に関する関連法令を尊重します。</li><li>当サービスに関するお問い合わせは、「特定商取引法に基づく表記」記載の連絡先までお願いいたします。</li></ol></article>
<p class="meta">制定日：2026年6月11日　／　事業者：マルム（Marumu）　<a href="/tokushoho">特定商取引法に基づく表記はこちら</a></p>
</div>
</body></html>"""


@app.route('/about', methods=['GET'])
def about_page():
    return ABOUT_HTML

@app.route('/tokushoho', methods=['GET'])
def tokushoho_page():
    return TOKUSHOHO_HTML

@app.route('/terms', methods=['GET'])
def terms_page():
    return TERMS_HTML


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
        if resp.status_code == 429:
            print(f"❌ [LINE push] 429 쿼터초과 — 월간 push 한도 소진. LINE플랜 업그레이드 필요")
        elif resp.status_code != 200:
            print(f"❌ [LINE push] status={resp.status_code} body={resp.text[:200]}")
        else:
            print(f"📤 [LINE push] status=200")
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
            _maru_token = secrets.token_hex(16)
            register_ipn_pending(user_id, 'MARU', payment_code)
            register_payment_token(_maru_token, user_id, 'MARU', payment_code)
            key = f'line_{user_id}'
            session = user_sessions.get(key, {})
            user_sessions[key] = {**session, 'payment_code': payment_code}
            line_push_api(user_id, result)
            line_push_api(user_id, build_payment_ticket_card(
                1000,
                f"https://www.paypal.com/ncp/payment/G7K49PXY32R2C?locale.x=ja_JP",
                payment_code,
                "今日の運気処方箋",
                items=[
                    "🌙 あなたの本質と今日のエネルギー",
                    "🌙 今週のテーマ",
                    "🌙 運気ミッション",
                    "🌙 辛口アドバイス",
                ]
            ))
            line_push_api(user_id, build_quick_reply_message(
                "決済が完了したら下のボタンを押してね🌙",
                ["💳 決済完了しました"]
            ))
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
            # テキスト処方箋: 4分割で順次発送
            def _extract(text, start_markers, end_markers):
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

            msg1 = _extract(result, ["【あなたの本質：日柱】"], ["【今日の最優先行動】"])
            msg2 = _extract(result, ["【今日の最優先行動】"], ["【あなたの"])
            msg3 = _extract(result, ["【あなたの"], ["【運気ミッション】", "【辛口アドバイス】", "【ラッキーアイテム】"])
            msg4 = _extract(result, ["【ラッキーアイテム】"], [])

            for msg in [msg1, msg2, msg3, msg4]:
                if msg:
                    line_push_api(user_id, msg)
                    time.sleep(1.5)

            time.sleep(1.5)
            line_push_api(user_id, "恋の悩みや推しとの相性も気になったら下のメニューからえらんでね🌙")
            time.sleep(1.5)
            line_push_api(user_id, "💎 もっと深く知りたいときは「マルムに相談」って送ってみてね✨")
            user_sessions[f'line_{user_id}']['step'] = 'done'
    except Exception as e:
        print(f"❌ [深層解読오류] {e}")
        line_push_api(user_id, "❌ エラーが発生しました。もう一度お試しください。")

def ziwei_analysis(user_id, year, month, day, birth_hour, gender, category=None):
    """紫微斗数 VIP 분석 → push API — background thread에서 실행"""
    try:
        print(f"[ZIWEI DEBUG] 시작: y={year} m={month} d={day} h={birth_hour} g={gender} cat={category}")

        from iztro_py import by_solar as iztro_by_solar
        print("[ZIWEI DEBUG] iztro_py import 성공")

        utc8_hour  = convert_jp_hour_to_iztro(birth_hour)
        time_index = hour_to_time_index(utc8_hour)
        solar_date = f"{year}-{month:02d}-{day:02d}"
        print(f"[ZIWEI DEBUG] solar={solar_date} idx={time_index}")

        chart = iztro_by_solar(solar_date, time_index, gender, language="ja-JP")
        print("[ZIWEI DEBUG] by_solar 성공")

        ai = MalgeumLineAI()
        summary, result = ai.get_ziwei(chart, category=category)
        print(f"[ZIWEI DEBUG] get_ziwei 성공 summary_keys={list(summary.keys())} text_len={len(result)}")

        def _extract(text, start_markers, end_markers):
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

        # [1차] Flex 카드 — 핵심 요약
        if summary:
            line_push_api(user_id, build_ziwei_summary_card(summary))
            time.sleep(1.5)

        # [2차] 텍스트 — CCTV起動 + 深層解読
        msg_detail = _extract(result, ["【CCTV起動】"], ["【開運処方】"])
        if msg_detail:
            line_push_api(user_id, msg_detail)
            time.sleep(1.5)

        # [3차] 텍스트 — 開運処方 + ラッキー情報
        msg_lucky = _extract(result, ["【開運処方】"], [])
        if msg_lucky:
            line_push_api(user_id, msg_lucky)
            time.sleep(1.5)

        line_push_api(user_id,
            "💎 もっと深く知りたいときは\n"
            "「マルムに相談」って送ってみてね🌙\n"
            "1対1で魂のレベルから一緒に考えるよ✨"
        )
        user_sessions[f'line_{user_id}']['step'] = 'done'
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"\u274c [紫微斗数오류] {type(e).__name__}: {e}\n{tb}")
        line_push_api(user_id, f"\u274c デバッグエラー: {type(e).__name__}: {str(e)}")
def compatibility_analysis(user_id, year, month, day, p_year, p_month, p_day, mode='preview', partner_name=None):
    """궁합 분석 → push API — background thread에서 실행"""
    try:
        saju1  = LineManse.calculate(year, month, day)
        saju2  = LineManse.calculate(p_year, p_month, p_day)
        ai     = MalgeumLineAI()
        result = ai.get_compatibility(saju1, saju2, mode=mode)
        if mode == 'preview':
            kyoumei_code = 'KYOUMEI-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            _kyoumei_token = secrets.token_hex(16)
            register_ipn_pending(user_id, 'KYOUMEI', kyoumei_code)
            register_payment_token(_kyoumei_token, user_id, 'KYOUMEI', kyoumei_code)
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
                f"https://www.paypal.com/ncp/payment/DP7F3FT8NDW9E?locale.x=ja_JP",
                kyoumei_code,
                "推しとの運命の処方箋"
            ))
            line_push_api(user_id, build_quick_reply_message(
                "決済が完了したら下のボタンを押してね🌙",
                ["💳 決済完了しました"]
            ))
        else:
            import re as _re_score
            _clean_result = result.replace('*','').replace('#','')
            # シンクロ率の数値を優先取得（エネルギーバー等を拾わないよう）
            _score_match = _re_score.search(r'シンクロ率[：:]\s*(\d+)%', _clean_result)
            if not _score_match:
                _score_match = _re_score.search(r'(\d+)\s*%', _clean_result)
            _score = int(_score_match.group(1)) if _score_match else 0
            save_kyoumei_paid(user_id, year, month, day, {'year': p_year, 'month': p_month, 'day': p_day}, partner_name, score=_score)
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
            # カード3: 推し活ラッキー
            try:
                line_push_api(user_id, build_kyoumei_lucky_card(result))
            except Exception as e:
                print(f"⚠️ [ラッキーカード生成エラー] {e}")
            # カード3: 相性度
            try:
                line_push_api(user_id, build_kyoumei_card(result, partner_name=partner_name))
            except Exception as e:
                print(f"⚠️ [相性カード生成エラー] {e}")
            time.sleep(1.5)
            line_push_api(user_id,
                "この結果、推し友にも教えてあげてね🌙\n"
                "他の推しでも気になったら「推しとの相性」ってもう一度送ってみてね💖"
            )
            user_sessions[f'line_{user_id}']['step'] = 'done'
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
            _fukuen_token = secrets.token_hex(16)
            register_ipn_pending(user_id, 'FUKUEN', fukuen_code)
            register_payment_token(_fukuen_token, user_id, 'FUKUEN', fukuen_code)
            s_key = f'line_{user_id}'
            user_sessions[s_key] = {**user_sessions.get(s_key, {}), 'fukuen_code': fukuen_code}
            line_push_api(user_id, result)
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
                f"https://www.paypal.com/ncp/payment/R2LWTQ2NYKEX2?locale.x=ja_JP"
            ))
            line_push_api(user_id, build_quick_reply_message(
                "決済が完了したら下のボタンを押してね🌙",
                ["💳 決済完了しました"]
            ))
        else:
            save_fukuen_paid(user_id, year, month, day, {'year': p_year, 'month': p_month, 'day': p_day})
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
                "💌 もし周りに恋で悩んでる子がいたら\n"
                "このリンクを送ってあげてね🌙\n"
                "あなたと同じように救われるかもしれないから✨\n"
                "👉 https://lin.ee/OH0EbHf"
            )
            time.sleep(1.5)
            line_push_api(user_id,
                "🌙 3日後、あの人の気持ちに変化がくるよ。\n"
                "またここに来てね✨"
            )
            user_sessions[f'line_{user_id}']['step'] = 'done'
    except Exception as e:
        print(f"❌ [재회분석오류] {e}")
        line_push_api(user_id, "❌ エラーが発生しました。もう一度お試しください。")


def kataomoi_analysis(user_id, year, month, day, p_year, p_month, p_day, mode='preview', partner_name=None):
    """片思い 분석 → push API — background thread에서 실행"""
    try:
        saju1  = LineManse.calculate(year, month, day)
        saju2  = LineManse.calculate(p_year, p_month, p_day)
        ai     = MalgeumLineAI()
        result = ai.get_kataomoi(saju1, saju2, partner_name=partner_name, mode=mode)
        if mode == 'preview':
            kataomoi_code = 'KATAOMOI-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            _kataomoi_token = secrets.token_hex(16)
            register_ipn_pending(user_id, 'KATAOMOI', kataomoi_code)
            register_payment_token(_kataomoi_token, user_id, 'KATAOMOI', kataomoi_code)
            s_key = f'line_{user_id}'
            user_sessions[s_key] = {**user_sessions.get(s_key, {}), 'kataomoi_code': kataomoi_code}
            line_push_api(user_id, result)
            line_push_api(user_id,
                "⚠️ 今、アプローチしたらどうなる？\n\n"
                "今すぐ動くと、相手は\n"
                "「嬉しいけど、どう反応すればいいかわからない」状態。\n"
                "焦らず、まずは自然な会話から始めてみて🌸"
            )
            line_push_api(user_id, build_kataomoi_omamori_card())
            line_push_api(user_id, build_mystery_kataomoi_card())
            line_push_api(user_id, build_kataomoi_payment_ticket_card(
                890,
                f"https://www.paypal.com/ncp/payment/XUJ9U53N5TA4Y?locale.x=ja_JP"
            ))
            line_push_api(user_id, build_quick_reply_message(
                "決済が完了したら下のボタンを押してね🌙",
                ["💳 決済完了しました"]
            ))
        else:
            save_kataomoi_paid(user_id, year, month, day, {'year': p_year, 'month': p_month, 'day': p_day})
            def _extract(text, start_markers, end_markers):
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

            msg1 = _extract(result, ["💜", "🌸 好きな人"], ["💘", "🎯"])
            msg2 = _extract(result, ["💘"], ["🎯"])
            msg3 = _extract(result, ["🎯"], ["⚠️"])
            msg4 = _extract(result, ["⚠️"], [])

            for msg in [msg1, msg2, msg3, msg4]:
                if msg:
                    line_push_api(user_id, msg)
                    time.sleep(1.5)

            line_push_api(user_id,
                "💌 もし周りに恋で悩んでる子がいたら\n"
                "このリンクを送ってあげてね🌙\n"
                "あなたと同じように救われるかもしれないから✨\n"
                "👉 https://lin.ee/OH0EbHf"
            )
            time.sleep(1.5)
            line_push_api(user_id,
                "🌙 3日後、好きな人の気持ちに変化がくるよ。\n"
                "またここに来てね✨"
            )
            user_sessions[f'line_{user_id}']['step'] = 'done'
    except Exception as e:
        print(f"❌ [片思い분석오류] {e}")
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
    FALLBACK_MSG = ("マルムへようこそ🌙\n\n"
                    "下のメニューからえらんでね✨\n\n"
                    "💖 推しとの相性\n"
                    "🌙 恋占い（片思い・復縁）\n"
                    "🔮 今日の運勢")

    # 💳 決済完了しました → セッション内のコードで自動処理
    if message.strip() == '💳 決済完了しました':
        session = user_sessions.get(key, {})
        for _ck in ('ziwei_code', 'payment_code', 'kyoumei_code', 'fukuen_code', 'kataomoi_code'):
            _code = session.get(_ck)
            if _code:
                return process_line(user_id, _code)
        return "決済コードが見つからないよ🌙\nもう一度最初から始めてね✨"

    # MARU- コード グローバル認識 (セッション状態に関係なく即実行)
    if message.strip().startswith('MARU-'):
        session = user_sessions.get(key, {})
        stored_code = session.get('payment_code', '')
        if (stored_code and message.strip() == stored_code) or message.strip() == 'MARU-TEST':
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
                        "🔮 あなただけの結果を読み解いてるよ🌙\n"
                        "少し待っててね✨")
            return "まず生年月日を入力してください🌿"
        return "コードが正しくありません。もう一度お試しください。🌿"

    # KYOUMEI- コード グローバル認識 (推し相性決済)
    if message.strip().startswith('KYOUMEI-'):
        session = user_sessions.get(key, {})
        stored_code = session.get('kyoumei_code', '')
        if (stored_code and message.strip() == stored_code) or message.strip() == 'KYOUMEI-TEST':
            partner = session.get('partner_birth')
            if 'year' in session and partner:
                _new = {k: v for k, v in session.items() if k != 'kyoumei_code'}
                _new['step'] = 'done'
                user_sessions[key] = _new
                threading.Thread(
                    target=compatibility_analysis,
                    args=(user_id, session['year'], session['month'], session['day'],
                          partner['year'], partner['month'], partner['day'], 'full',
                          session.get('partner_name')),
                    daemon=True
                ).start()
                return "🔑 決済を確認したよ。\nあなたと推しの運命の扉が、今ひらかれていく…🌙\n少し待っててね✨"
            return "まず「推し相性」から始めてください🌿"
        return "コードが正しくありません。🌿"

    # MINI- コード グローバル認識 (재방문 미니 결제)
    if message.strip().startswith('MINI-'):
        session = user_sessions.get(key, {})
        stored_code = session.get('mini_code', '')
        if stored_code and message.strip() == stored_code:
            mini_type = session.get('mini_type', 'fukuen')
            if mini_type == 'fukuen':
                partner = session.get('fukuen_partner_birth')
                if 'year' in session and partner:
                    user_sessions[key] = {k: v for k, v in session.items() if k != 'mini_code'}
                    threading.Thread(
                        target=fukuen_analysis,
                        args=(user_id, session['year'], session['month'], session['day'],
                              partner['year'], partner['month'], partner['day'], 'full', None),
                        daemon=True
                    ).start()
                    return "🌀 決済を確認しました。\nあの人の今日の気持ちを読んでいくよ…🌙"
            elif mini_type == 'kyoumei':
                partner = session.get('partner_birth')
                if 'year' in session and partner:
                    user_sessions[key] = {k: v for k, v in session.items() if k != 'mini_code'}
                    threading.Thread(
                        target=compatibility_analysis,
                        args=(user_id, session['year'], session['month'], session['day'],
                              partner['year'], partner['month'], partner['day'], 'full',
                              session.get('partner_name')),
                        daemon=True
                    ).start()
                    return "🌀 決済を確認しました。\n推しとの今日の相性を読んでいくよ…🌙"
            else:  # kataomoi
                partner = session.get('kataomoi_partner_birth')
                if 'year' in session and partner:
                    user_sessions[key] = {k: v for k, v in session.items() if k != 'mini_code'}
                    threading.Thread(
                        target=kataomoi_analysis,
                        args=(user_id, session['year'], session['month'], session['day'],
                              partner['year'], partner['month'], partner['day'], 'full',
                              session.get('kataomoi_partner_name')),
                        daemon=True
                    ).start()
                    return "🌀 決済を確認しました。\n好きな人との気持ちを読んでいくよ…🌸"
            return "まずメニューから選んでください🌿"
        return "コードが正しくありません。🌿"

    # KATAOMOI- コード グローバル認識 (片思い決済)
    if message.strip().startswith('KATAOMOI-'):
        session = user_sessions.get(key, {})
        stored_code = session.get('kataomoi_code', '')
        if (stored_code and message.strip() == stored_code) or message.strip() == 'KATAOMOI-TEST':
            partner = session.get('kataomoi_partner_birth')
            if 'year' in session and partner:
                _new = {k: v for k, v in session.items() if k != 'kataomoi_code'}
                _new['step'] = 'done'
                user_sessions[key] = _new
                threading.Thread(
                    target=kataomoi_analysis,
                    args=(user_id, session['year'], session['month'], session['day'],
                          partner['year'], partner['month'], partner['day'], 'full',
                          session.get('kataomoi_partner_name')),
                    daemon=True
                ).start()
                return "🌀 決済を確認しました。\n好きな人との運命の封を切ります🌸"
            return "まず「好きな人」から始めてください🌸"
        return "コードが正しくありません。🌸"

    # FUKUEN- コード グローバル認識 (復縁決済)
    if message.strip().startswith('FUKUEN-'):
        session = user_sessions.get(key, {})
        stored_code = session.get('fukuen_code', '')
        if (stored_code and message.strip() == stored_code) or message.strip() == 'FUKUEN-TEST':
            partner = session.get('fukuen_partner_birth')
            if 'year' in session and partner:
                _new = {k: v for k, v in session.items() if k != 'fukuen_code'}
                _new['step'] = 'done'
                user_sessions[key] = _new
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

    # ZIWEI- コード グローバル認識 (紫微斗数VIP決済)
    if message.strip().startswith('ZIWEI-'):
        session = user_sessions.get(key, {})
        stored_code = session.get('ziwei_code', '')
        print(f"[ZIWEI] received={message.strip()!r} stored={stored_code!r} step={session.get('step')} has_year={'year' in session} has_hour={session.get('ziwei_birth_hour')}")
        _is_ziwei_test = message.strip() == 'ZIWEI-TEST'
        if (stored_code and message.strip() == stored_code) or _is_ziwei_test:
            _birth_hour = session.get('ziwei_birth_hour')
            if ('year' in session and _birth_hour is not None) or _is_ziwei_test:
                _new = {k: v for k, v in session.items() if k != 'ziwei_code'}
                _new['step'] = 'done'
                user_sessions[key] = _new
                threading.Thread(
                    target=ziwei_analysis,
                    args=(user_id, session.get('year', 1995), session.get('month', 1), session.get('day', 1),
                          _birth_hour if _birth_hour is not None else 0,
                          session.get('ziwei_gender', '女'),
                          session.get('ziwei_category')),
                    daemon=True
                ).start()
                return ("🌀 決済を確認しました。\n"
                        "あなたの人生のCCTVを起動するよ🌙\n"
                        "少し待っててね✨")
            return "ごめんね、もう一度「今日の運勢」から始めてね🌿"
        return "ごめんね、セッションが切れちゃったよ🌙\nもう一度「今日の運勢」から始めてね✨"

    # 処方箋を開く / レポートを開く
    if message in ('処方箋を開く', 'レポートを開く'):
        session = user_sessions.get(key, {})
        if 'year' in session:
            user_sessions[key] = {**session, 'step': 'WAITING_PAYMENT_CODE'}
            return "🔑 決済コードを入力してください。"
        return "まず生年月日を入力してください🌿"

    # 相性を開く / 相性を見る → 결제 카드 재발송 (직접 full 호출 차단)
    if '相性を開く' in message or '相性を見る' in message:
        session = user_sessions.get(key, {})
        partner = session.get('partner_birth')
        if 'year' in session and partner:
            kyoumei_code = session.get('kyoumei_code') or \
                'KYOUMEI-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            _resend_kyoumei_token = secrets.token_hex(16)
            register_ipn_pending(user_id, 'KYOUMEI', kyoumei_code)
            register_payment_token(_resend_kyoumei_token, user_id, 'KYOUMEI', kyoumei_code)
            user_sessions[key] = {**session, 'kyoumei_code': kyoumei_code}
            def _resend_kyoumei_payment():
                line_push_api(user_id, build_payment_ticket_card(
                    590,
                    f"https://www.paypal.com/ncp/payment/DP7F3FT8NDW9E?locale.x=ja_JP",
                    kyoumei_code,
                    "推しとの運命の処方箋"
                ))
                line_push_api(user_id, build_quick_reply_message(
                    "決済が完了したら下のボタンを押してね🌙",
                    ["💳 決済完了しました"]
                ))
            threading.Thread(target=_resend_kyoumei_payment, daemon=True).start()
            return "💖 推しとの運命の処方箋を受け取るよ🌙\n決済が完了したらコードを送ってね✨\n少し待っててね…"
        return "まず「推し相性」から始めてください🌿"

    # マルム → 처음으로 리셋
    if message == 'マルム':
        user_sessions[key] = {}
        return FALLBACK_MSG

    # 恋占い → 片思い/復縁 선택 Quick Reply
    if '恋占い' in message:
        session = user_sessions.get(key, {})
        return build_quick_reply_message(
            "どっちの恋の悩みを占おうか？🌙",
            ["① 片思い", "② 復縁（あの人）"]
        )

    _cur_step = user_sessions.get(key, {}).get('step', '')

    # 好きな人 → 片思いフロー (재방문 분기 포함)
    if ('好きな人' in message or '① 片思い' in message) \
            and _cur_step not in ('KATAOMOI_RETURN', 'FUKUEN_RETURN', 'KYOUMEI_RETURN'):
        session = user_sessions.get(key, {})
        users_data = load_users()
        user_data = users_data.get(user_id, {})
        kataomoi_paid_date = user_data.get('kataomoi_paid_date')
        today_str = datetime.now(ZoneInfo("Asia/Tokyo")).strftime('%Y-%m-%d')
        if kataomoi_paid_date and user_data.get('year'):
            # TODO: 테스트 완료 후 1일 제한 다시 활성화
            if False: pass
            # if kataomoi_paid_date == today_str:
            #     return "今日はもう占ったよ🌸\n明日また来てね✨"
            user_sessions[key] = {
                **session,
                'step': 'KATAOMOI_RETURN',
                'year': user_data.get('year'),
                'month': user_data.get('month'),
                'day': user_data.get('day'),
                'kataomoi_partner_birth': user_data.get('kataomoi_partner'),
            }
            return build_quick_reply_message(
                "おかえり🌸\n好きな人の気持ち、前回から変わってるよ。",
                ["① 今日の気持ちチェック", "② はじめから全部見る"]
            )
        user_sessions[key] = {**session, 'step': 'KATAOMOI_EMO_Q1'}
        return build_quick_reply_message(
            "好きな人のこと考えると、どんな気持ち？🌙",
            ["ドキドキする", "会いたいけど怖い", "どう思われてるか気になる"]
        )

    # あの人 / 復縁 → 재방문 분기 or 신규 플로우
    # ① / ② 버튼 응답은 step 핸들러에서 처리 → 트리거 제외
    if ('あの人' in message or '復縁' in message or '② 復縁（あの人）' in message) \
            and _cur_step not in ('FUKUEN_RETURN', 'KATAOMOI_RETURN', 'KYOUMEI_RETURN'):
        session = user_sessions.get(key, {})
        users_data = load_users()
        user_data = users_data.get(user_id, {})
        fukuen_paid_date = user_data.get('fukuen_paid_date')
        today_str = datetime.now(ZoneInfo("Asia/Tokyo")).strftime('%Y-%m-%d')
        if fukuen_paid_date and user_data.get('year'):
            # TODO: 테스트 완료 후 1일 제한 다시 활성화
            if False: pass
            # if fukuen_paid_date == today_str:
            #     return "今日はもう占ったよ🌙\n明日また来てね✨"
            # 재방문 유저 — 저장된 데이터로 session 채움
            user_sessions[key] = {
                **session,
                'step': 'FUKUEN_RETURN',
                'year': user_data.get('year'),
                'month': user_data.get('month'),
                'day': user_data.get('day'),
                'fukuen_partner_birth': user_data.get('fukuen_partner'),
            }
            return build_quick_reply_message(
                "おかえり🌙\nあの人の気持ち、前回から変わってるよ。",
                ["① 今日のあの人の気持ち", "② はじめから全部見る"]
            )
        # 신규 유저 — 기존 플로우
        user_sessions[key] = {**session, 'step': 'FUKUEN_EMO_Q1'}
        return build_quick_reply_message(
            "あの人のこと、最後に思い出したのはいつ？🌙",
            ["さっき", "今日何回も", "ずっと頭から離れない"]
        )

    # 推しランキング → 過去のKYOUMEI相性履歴をスコア順で表示
    if message == '推しランキング':
        users_data = load_users()
        user_data = users_data.get(user_id, {})
        history = user_data.get('kyoumei_history', [])
        if not history:
            return "まだランキングがないよ🌙\nまずは「推しとの相性」で推しとの相性を調べてみてね✨"
        def _send_ranking():
            line_push_api(user_id, build_oshi_ranking_card(history))
            line_push_api(user_id, "他の推しも気になる？\nもっとランキングを増やしてみてね✨\n下のメニューから「推しとの相性」をタップ💖")
        threading.Thread(target=_send_ranking, daemon=True).start()
        return "💖 推し相性ランキングを表示するよ🌙\n少し待っててね✨"

    # 推しとの相性 / 推し相性 → 재방문 분기 or 신규 플로우
    # ① / ② 버튼 응답은 step 핸들러에서 처리 → 트리거 제외
    if ('推しとの相性' in message or '推し相性' in message) \
            and _cur_step not in ('KATAOMOI_RETURN', 'FUKUEN_RETURN', 'KYOUMEI_RETURN'):
        session = user_sessions.get(key, {})
        users_data = load_users()
        user_data = users_data.get(user_id, {})
        kyoumei_paid_date = user_data.get('kyoumei_paid_date')
        today_str = datetime.now(ZoneInfo("Asia/Tokyo")).strftime('%Y-%m-%d')
        if kyoumei_paid_date and user_data.get('year'):
            # TODO: 테스트 완료 후 1일 제한 다시 활성화
            if False: pass
            # if kyoumei_paid_date == today_str:
            #     return "今日はもう占ったよ🌙\n明日また来てね✨"
            # 재방문 유저
            user_sessions[key] = {
                **session,
                'step': 'KYOUMEI_RETURN',
                'year': user_data.get('year'),
                'month': user_data.get('month'),
                'day': user_data.get('day'),
                'partner_birth': user_data.get('kyoumei_partner'),
                'partner_name': user_data.get('kyoumei_partner_name'),
            }
            return build_quick_reply_message(
                "おかえり🌙\n推しとの相性、前回から変わってるよ。",
                ["① 今日の推しとの相性", "② はじめから全部見る"]
            )
        # 신규 유저 — 기존 플로우
        if 'year' not in session:
            user_sessions[key] = {**session, 'step': 'WAITING_COMPAT_SELF'}
            return ("推し相性をチェックします。🌙\n"
                    "まず、あなた自身の生年月日を\n"
                    "8桁で入力してください。\n"
                    "例）19930616")
        user_sessions[key] = {**session, 'step': 'WAITING_PARTNER'}
        return ("推しの名前と生年月日を教えてね✨\n"
                "例）カズハ 20010122\n"
                "名前なしで生年月日だけでもOKだよ🌙")

    # 鑑定予約 (따옴표/특수문자 포함 입력도 인식)
    if re.search(r'鑑定予約', message):
        session = user_sessions.get(key, {})
        user_sessions[key] = {**session, 'step': 'booking'}
        return ("ご予約はこちらから承ります。\n"
                "🔒 1対1 LINE鑑定（30分 ¥5,000）\n"
                "→ https://www.paypal.com/ncp/payment/4FXDK6WHXU45W?locale.x=ja_JP\n\n"
                "ご希望の日時を教えてください。\n"
                "例）4月25日 20時\n"
                "最初に戻りたい方は「マルム」とご入力ください。🌿")

    # 시작
    if message in ('運勢を見る', '四柱推命で見てみる', '今日の運勢を見る', '今日の運勢', '扉を開く'):
        user_sessions[key] = {'step': 'date'}
        return ("今日のあなたの流れ、読んでみるね🌙\n"
                "まず生年月日を8桁で教えて✨\n"
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
                return ("生まれた時間も教えてくれる？🌙\n"
                        "例）0730\n"
                        "わからなかったら「不明」って送ってね✨")
            except Exception as e:
                return f"❌ エラーが発生しました: {e}"
        return "ごめんね、うまく読み取れなかった🌙 8桁の数字で教えてね✨\n例）19930616"

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
        return ("オッケー、準備できたよ🌙\n"
                "今日いちばん気になるテーマはどれ？\n\n"
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

    # ─── 紫微斗数 VIP フロー ───────────────────────────────
    if step == 'WAITING_ZIWEI_CONFIRM':
        if 'やってみる' in message:
            user_sessions[key] = {**session, 'step': 'WAITING_ZIWEI_HOUR'}
            return ("生まれた時間を教えてね🌙\n"
                    "例）0730\n"
                    "わからなかったら「不明」って送ってね")
        else:
            user_sessions[key] = {k: v for k, v in session.items() if k != 'step'}
            return "またいつでも来てね🌙"

    if step == 'WAITING_ZIWEI_HOUR':
        normalized = message.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
        if message.strip() == '不明':
            user_sessions[key] = {k: v for k, v in session.items() if k != 'step'}
            return ("ごめんね、この占いは生まれた時間が必要なの🌙\n"
                    "母子手帳を確認してみてね✨")
        digits = ''.join(filter(str.isdigit, normalized))
        if len(digits) in (3, 4):
            hhmm = digits.zfill(4)
            birth_hour = int(hhmm[:2])
            if 0 <= birth_hour <= 23:
                user_sessions[key] = {**session, 'step': 'WAITING_ZIWEI_GENDER', 'ziwei_birth_hour': birth_hour}
                return build_quick_reply_message(
                    "性別を教えてね🌙",
                    ["女の子", "男の子"]
                )
        return "時間は4桁で教えてね✨\n例）0730"

    if step == 'WAITING_ZIWEI_GENDER':
        if '女' in message:
            ziwei_gender = '女'
        elif '男' in message:
            ziwei_gender = '男'
        else:
            return build_quick_reply_message("性別を教えてね🌙", ["女の子", "男の子"])
        user_sessions[key] = {**session, 'step': 'WAITING_ZIWEI_CATEGORY', 'ziwei_gender': ziwei_gender}
        return build_quick_reply_message(
            "今いちばん気になるのはどれ？🌙",
            ["💰 お金", "💕 恋愛", "💼 仕事", "🌿 健康"]
        )

    if step == 'WAITING_ZIWEI_CATEGORY':
        ziwei_category = message.strip()
        year_z = session.get('year')
        if not year_z:
            user_sessions[key] = {}
            return "ごめんね、もう一度「今日の運勢」から始めてね🌿"
        ziwei_code = 'ZIWEI-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        _ziwei_token = secrets.token_hex(16)
        register_ipn_pending(user_id, 'ZIWEI', ziwei_code)
        register_payment_token(_ziwei_token, user_id, 'ZIWEI', ziwei_code)
        user_sessions[key] = {**session, 'step': 'WAITING_ZIWEI_CODE',
                               'ziwei_category': ziwei_category, 'ziwei_code': ziwei_code}
        def _send_ziwei_payment():
            line_push_api(user_id,
                "✨ 準備できたよ🌙\n"
                "あなたの星の配置から\n"
                "人生のCCTVを覗いていくよ💫"
            )
            line_push_api(user_id, build_payment_ticket_card(
                2980,
                f"https://www.paypal.com/ncp/payment/HYU9V5C9KRU7S?locale.x=ja_JP",
                ziwei_code,
                "人生のCCTV完全解読",
                items=[
                    "🌙 命宮（本質の星）解読",
                    "🌙 今の大運・流年の流れ",
                    f"🌙 {ziwei_category} 深層解読",
                    "🌙 マルム式 開運処方",
                    "🌙 ラッキー情報",
                ]
            ))
            line_push_api(user_id, build_quick_reply_message(
                "決済が完了したら下のボタンを押してね🌙",
                ["💳 決済完了しました"]
            ))
        threading.Thread(target=_send_ziwei_payment, daemon=True).start()
        return "🌙 少し待っててね✨"

    if step == 'WAITING_ZIWEI_CODE':
        stored_code = session.get('ziwei_code', '')
        if message.strip() == stored_code:
            new_session = {k: v for k, v in session.items() if k != 'ziwei_code'}
            new_session['step'] = 'done'
            user_sessions[key] = new_session
            threading.Thread(
                target=ziwei_analysis,
                args=(user_id, session['year'], session['month'], session['day'],
                      session['ziwei_birth_hour'], session['ziwei_gender'],
                      session.get('ziwei_category')),
                daemon=True
            ).start()
            return ("🌀 決済を確認しました。\n"
                    "あなたの人生のCCTVを起動するよ🌙\n"
                    "少し待っててね✨")
        return "コードが正しくありません。🌿"
    # ─────────────────────────────────────────────────────────

    if step == 'KATAOMOI_EMO_Q1':
        emo_q1 = message
        user_sessions[key] = {**session, 'step': 'KATAOMOI_EMO_Q2', 'kataomoi_emo_q1': emo_q1}
        return build_quick_reply_message(
            "その人と最後に話したのはいつ？",
            ["最近話した", "しばらく話せてない", "まだちゃんと話したことない"]
        )

    if step == 'KATAOMOI_EMO_Q2':
        q1 = session.get('kataomoi_emo_q1', '')
        if 'ドキドキ' in q1:
            emo_reply = "そのドキドキ、あの人にも届いてるかも。ちょっと調べてみるね🌙"
        elif '怖い' in q1:
            emo_reply = "怖いって思うの、本気だからだよ。あの人の気持ち、見てみようか🌙"
        else:
            emo_reply = "気になるよね。あの人の本音、一緒に覗いてみよう🌙"
        user_sessions[key] = {**session, 'step': 'WAITING_KATAOMOI_SELF', 'kataomoi_emo_q2': message}
        return (f"{emo_reply}\n\n"
                "💘 好きな人との縁を読み解きます🌸\n\n"
                "まず、あなたの生年月日を\n"
                "8桁で教えてください✨\n"
                "例）19930616")

    if step == 'WAITING_KATAOMOI_SELF':
        normalized = message.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
        digits = ''.join(filter(str.isdigit, normalized))
        if len(digits) == 8:
            try:
                year  = int(digits[0:4])
                month = int(digits[4:6])
                day   = int(digits[6:8])
                if not (1920 <= year <= 2010) or not (1 <= month <= 12) or not (1 <= day <= 31):
                    return "❌ 正しい生年月日を入力してください。\n例）19930616"
                user_sessions[key] = {**session, 'step': 'WAITING_KATAOMOI_PARTNER',
                                      'year': year, 'month': month, 'day': day}
                return ("好きな人の名前と生年月日を教えてね🌸\n"
                        "例）タクミ 20000315\n"
                        "名前なしで生年月日だけでもOKだよ🌙")
            except Exception:
                return "ごめんね、うまく読み取れなかった🌙 8桁の数字で教えてね✨\n例）19930616"
        return "ごめんね、うまく読み取れなかった🌙 8桁の数字で教えてね✨\n例）19930616"

    if step == 'WAITING_KATAOMOI_PARTNER':
        normalized = message.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
        date_match = re.search(r'(\d{8})', normalized)
        if date_match:
            try:
                digits  = date_match.group(1)
                p_year  = int(digits[0:4])
                p_month = int(digits[4:6])
                p_day   = int(digits[6:8])
                if not (1920 <= p_year <= 2010) or not (1 <= p_month <= 12) or not (1 <= p_day <= 31):
                    return "❌ 正しい生年月日を入力してください。\n例）タクミ 20000315"
                if 'year' not in session:
                    user_sessions[key] = {}
                    return "まず「好きな人」と入力して、生年月日を教えてください🌸"
                partner_name = re.sub(r'\d{8}', '', message).strip() or None
                user_sessions[key] = {**session,
                    'kataomoi_partner_birth': {'year': p_year, 'month': p_month, 'day': p_day},
                    'kataomoi_partner_name': partner_name}
                threading.Thread(
                    target=kataomoi_analysis,
                    args=(user_id, session['year'], session['month'], session['day'],
                          p_year, p_month, p_day, 'preview', partner_name),
                    daemon=True
                ).start()
                return "少し待っててね。\nふたりの縁の糸をたどってるから…🌸"
            except Exception:
                return "❌ お名前と生年月日を入力してください。\n例）タクミ 20000315"
        return "❌ お名前と生年月日を入力してください。\n例）タクミ 20000315"

    if step == 'KATAOMOI_RETURN':
        if '①' in message or 'ミニ鑑定' in message:
            mini_code = 'KATAOMOI-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            _kata_mini_token = secrets.token_hex(16)
            register_ipn_pending(user_id, 'KATAOMOI', mini_code)
            register_payment_token(_kata_mini_token, user_id, 'KATAOMOI', mini_code)
            user_sessions[key] = {**session, 'kataomoi_code': mini_code}
            def _send_kataomoi_mini_payment():
                line_push_api(user_id, "好きって気持ち、誰にも言えないまま\nここに来てくれたんだね🌙\nその勇気、ちゃんと届いてるよ。\n今日はこっそりおまけしとくね✨")
                line_push_api(user_id, build_kataomoi_payment_ticket_card(
                    MINI_PRICE, f"https://www.paypal.com/ncp/payment/XUJ9U53N5TA4Y?locale.x=ja_JP"
                ))
                line_push_api(user_id, build_quick_reply_message(
                    "決済が完了したら下のボタンを押してね🌙",
                    ["💳 決済完了しました"]
                ))
            threading.Thread(target=_send_kataomoi_mini_payment, daemon=True).start()
            return "🌸 準備するね。\n少し待っててね✨"
        if '②' in message or 'フル処方せん' in message:
            user_sessions[key] = {**session, 'step': 'KATAOMOI_EMO_Q1'}
            return build_quick_reply_message(
                "好きな人のこと考えると、どんな気持ち？🌙",
                ["ドキドキする", "会いたいけど怖い", "どう思われてるか気になる"]
            )
        return build_quick_reply_message(
            "おかえり🌸\n好きな人の気持ち、前回から変わってるよ。",
            ["① 今日の気持ちチェック", "② はじめから全部見る"]
        )

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
                return ("相手の名前と生年月日を教えてね💫\n"
                        "例）ユウタ 19950315\n"
                        "名前なしで生年月日だけでもOKだよ🌙")
            except Exception:
                return "ごめんね、うまく読み取れなかった🌙 8桁の数字で教えてね✨\n例）19930616"
        return "ごめんね、うまく読み取れなかった🌙 8桁の数字で教えてね✨\n例）19930616"

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
                return ("推しの名前と生年月日を教えてね✨\n"
                        "例）カズハ 20010122\n"
                        "名前なしで生年月日だけでもOKだよ🌙")
            except Exception:
                return "ごめんね、うまく読み取れなかった🌙 8桁の数字で教えてね✨\n例）19930616"
        return "ごめんね、うまく読み取れなかった🌙 8桁の数字で教えてね✨\n例）19930616"

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
                    return ("まず「運勢を見る」と入力してね。\n"
                            "生年月日を教えてね🌿\n"
                            "その後、推し相性を楽しんでね✨")
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

    if step == 'FUKUEN_RETURN':
        if '①' in message or 'ミニ鑑定' in message:
            mini_code = 'FUKUEN-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            _fukuen_mini_token = secrets.token_hex(16)
            register_ipn_pending(user_id, 'FUKUEN', mini_code)
            register_payment_token(_fukuen_mini_token, user_id, 'FUKUEN', mini_code)
            user_sessions[key] = {**session, 'fukuen_code': mini_code}
            def _send_fukuen_mini_payment():
                line_push_api(user_id, "あの人のこと、まだ気になって来てくれたんだね🌙\nひとりで抱えてるその気持ち、\nちゃんと受け止めてるよ。\nだから今日はちょっとだけ、おまけしとくね✨")
                line_push_api(user_id, build_fukuen_payment_ticket_card(
                    MINI_PRICE, f"https://www.paypal.com/ncp/payment/R2LWTQ2NYKEX2?locale.x=ja_JP"
                ))
                line_push_api(user_id, build_quick_reply_message(
                    "決済が完了したら下のボタンを押してね🌙",
                    ["💳 決済完了しました"]
                ))
            threading.Thread(target=_send_fukuen_mini_payment, daemon=True).start()
            return "🌙 準備するね。\n少し待っててね✨"
        if '②' in message or 'フル処方せん' in message:
            user_sessions[key] = {**session, 'step': 'FUKUEN_EMO_Q1'}
            return build_quick_reply_message(
                "あの人のこと、最後に思い出したのはいつ？🌙",
                ["さっき", "今日何回も", "ずっと頭から離れない"]
            )
        return build_quick_reply_message(
            "おかえり🌙\nあの人の気持ち、前回から変わってるよ。",
            ["① 今日のあの人の気持ち", "② はじめから全部見る"]
        )

    if step == 'KYOUMEI_RETURN':
        if '①' in message or 'ミニ鑑定' in message:
            mini_code = 'KYOUMEI-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            _kyoumei_mini_token = secrets.token_hex(16)
            register_ipn_pending(user_id, 'KYOUMEI', mini_code)
            register_payment_token(_kyoumei_mini_token, user_id, 'KYOUMEI', mini_code)
            user_sessions[key] = {**session, 'kyoumei_code': mini_code}
            def _send_kyoumei_mini_payment():
                line_push_api(user_id, "また推しのこと気になって来てくれたんだね🌙\nその推し愛に応えたいから\n今日は特別に少しだけお安くしておくね✨")
                line_push_api(user_id, build_payment_ticket_card(
                    MINI_PRICE,
                    f"https://www.paypal.com/ncp/payment/DP7F3FT8NDW9E?locale.x=ja_JP",
                    mini_code,
                    "今日の推し活ガイド"
                ))
                line_push_api(user_id, build_quick_reply_message(
                    "決済が完了したら下のボタンを押してね🌙",
                    ["💳 決済完了しました"]
                ))
            threading.Thread(target=_send_kyoumei_mini_payment, daemon=True).start()
            return "🌙 準備するね。\n少し待っててね✨"
        if '②' in message or 'フル処方せん' in message:
            user_sessions[key] = {**session, 'step': 'WAITING_COMPAT_SELF'}
            return ("推し相性をチェックします。🌙\n"
                    "まず、あなた自身の生年月日を\n"
                    "8桁で入力してください。\n"
                    "例）19930616")
        return build_quick_reply_message(
            "おかえり🌙\n推しとの相性、前回から変わってるよ。",
            ["① 今日の推しとの相性", "② はじめから全部見る"]
        )

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
        return FALLBACK_MSG

    if not step:
        return FALLBACK_MSG
    return FALLBACK_MSG

# ============================================================================
# PayPal IPN
# ============================================================================
@app.route('/paypal/ipn', methods=['POST'])
def paypal_ipn():
    """PayPal IPN 검증 → LINE 코드 자동 발송"""
    raw_data = request.get_data(as_text=True)
    verify_payload = 'cmd=_notify-validate&' + raw_data
    try:
        verify_resp = requests.post(
            'https://ipnpb.paypal.com/cgi-bin/webscr',
            data=verify_payload,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=10
        )
        if verify_resp.text != 'VERIFIED':
            print(f"[IPN] Not verified: {verify_resp.text}")
            return 'INVALID', 200
    except Exception as e:
        print(f"[IPN] verify error: {e}")
        return 'ERROR', 200

    ipn_data = request.form.to_dict()
    custom = ipn_data.get('custom', '')
    payment_status = ipn_data.get('payment_status', '')
    print(f"[IPN] custom={custom!r} status={payment_status}")

    if payment_status != 'Completed':
        return 'OK', 200

    parts = custom.split('_')
    if len(parts) < 2:
        return 'OK', 200

    user_id = parts[0]
    service_type = parts[1]
    # parts[2] = token (if present) — for dedup with /payment/success

    pending = load_ipn_pending()
    code = pending.get(f'{user_id}_{service_type}')
    if not code:
        print(f"[IPN] no pending code for {user_id}_{service_type}")
        return 'OK', 200

    line_push_api(user_id,
        f"🎉 決済が完了したよ！\n以下のコードをこのトーク画面に送ってね：\n\n{code}")
    del pending[f'{user_id}_{service_type}']
    save_ipn_pending(pending)
    print(f"[IPN] code sent to {user_id}: {code}")
    return 'OK', 200

# ============================================================================
# PayPal 결제 성공 리다이렉트
# ============================================================================
@app.route('/payment/success', methods=['GET'])
def payment_success():
    """PayPal Auto Return URL → 토큰 검증 → LINE 코드 발송"""
    # PayPal은 custom 값을 'cm' 파라미터로 돌려줌
    cm = request.args.get('cm', '')
    parts = cm.split('_')
    token = parts[2] if len(parts) >= 3 else ''

    _ok_html = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>決済完了</title>
<style>body{text-align:center;padding:40px 20px;font-family:sans-serif;background:#0d0d1a;color:#fff}
h2{color:#FFD700}p{color:#ccc;line-height:1.8}</style></head>
<body>
<h2>✅ 決済が完了しました！</h2>
<p>LINEに接続コードを送りました！<br>
このページを閉じて、LINEを確認してください。</p>
</body></html>"""

    if not token:
        return _ok_html, 200

    tokens = load_payment_tokens()
    entry = tokens.get(token)
    if not entry:
        # 既に使用済み or IPN が先に処理済み
        return _ok_html, 200

    uid  = entry['user_id']
    code = entry['code']
    print(f"[SUCCESS] token={token[:8]}... uid={uid[:12]} code={code}")

    # LINE にコード送信
    line_push_api(uid,
        f"🎉 決済が完了したよ！\n"
        f"以下のコードをこのトーク画面に送ってね：\n\n{code}"
    )

    # 1回限り — トークン削除
    del tokens[token]
    save_payment_tokens(tokens)

    return _ok_html, 200

# ============================================================================
# 서버 실행
# ============================================================================
if __name__ == '__main__':
    print("\n🚀 マルム 서버 시작!")
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
