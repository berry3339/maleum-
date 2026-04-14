#!/bin/zsh
# 맑음 서버 시작 스크립트
# 사용법: 터미널에서 ./start_maleum.sh

source ~/.zshrc

echo "🔄 기존 서버/ngrok 종료 중..."
pkill -f "python3.*app.py" 2>/dev/null
kill $(lsof -ti:5001) 2>/dev/null
pkill -f "ngrok" 2>/dev/null
sleep 1

echo "🚀 맑음 서버 시작 중..."
python3 /Users/minki/app.py > /tmp/maleum_server.log 2>&1 &
sleep 2

if ! lsof -i:5001 -sTCP:LISTEN > /dev/null 2>&1; then
    echo "❌ 서버 시작 실패. 로그 확인:"
    cat /tmp/maleum_server.log
    exit 1
fi
echo "✅ Flask 서버 실행 중 (포트 5001)"

echo "🌐 ngrok 터널 연결 중..."
ngrok http 5001 --log=stdout > /tmp/ngrok.log 2>&1 &
sleep 4

NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['tunnels'][0]['public_url'])" 2>/dev/null)

if [ -z "$NGROK_URL" ]; then
    echo "❌ ngrok 연결 실패. 로그 확인:"
    cat /tmp/ngrok.log
    exit 1
fi

echo ""
echo "======================================"
echo "✅ 맑음 서버 완전 가동!"
echo "======================================"
echo ""
echo "📋 카카오 스킬 URL (복사해서 붙여넣기):"
echo ""
echo "  ${NGROK_URL}/kakao"
echo ""
echo "======================================"
echo "⚠️  이 터미널 창을 닫으면 서버가 꺼집니다."
echo "======================================"
