#!/usr/bin/env bash
# 진에어 모니터링 — Mac 로컬 launchd 최종 설정
# 한 번만 실행하면 됩니다.

PLIST="$HOME/Library/LaunchAgents/com.jinair.monitor.plist"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   진에어 모니터링 - Mac 로컬 설정          ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  (GitHub Actions는 Cloudflare에 막혀 Mac 로컬로 전환합니다)"
echo ""
read -r -p "발신 이메일 주소: " SENDER_EMAIL
read -r -s -p "이메일 비밀번호 (화면에 표시 안 됨): " SENDER_PASSWORD
echo ""

# plist 파일에 실제 값 주입
sed -i '' \
    "s|REPLACE_SENDER_EMAIL|${SENDER_EMAIL}|g" \
    "$PLIST"
sed -i '' \
    "s|REPLACE_SENDER_PASSWORD|${SENDER_PASSWORD}|g" \
    "$PLIST"

# plist 파일 권한을 소유자만 읽을 수 있도록 설정
chmod 600 "$PLIST"

echo ""
echo "⏳ LaunchAgent 등록 중..."

# 기존 agent 제거 후 재등록
launchctl unload "$PLIST" 2>/dev/null
launchctl load "$PLIST"

echo ""
echo "✅ 완료! 5분마다 자동 실행됩니다."
echo ""
echo "📋 상태 확인:  launchctl list | grep jinair"
echo "📄 로그 확인:  tail -f ~/jinair-monitor/monitor.log"
echo "🛑 중지:       launchctl unload ~/Library/LaunchAgents/com.jinair.monitor.plist"
echo ""

# 즉시 한 번 테스트 실행
echo "🧪 지금 바로 테스트 실행합니다..."
SENDER_EMAIL="$SENDER_EMAIL" \
SENDER_PASSWORD="$SENDER_PASSWORD" \
RECIPIENT_EMAIL="ljh0196@naver.com" \
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 \
    ~/jinair-monitor/check_jinair.py

echo ""
echo "테스트 완료. 결과는 위 로그를 확인하세요."
