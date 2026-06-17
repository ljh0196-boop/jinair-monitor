#!/usr/bin/env bash
# 진에어 모니터링 - GitHub Secrets 설정 스크립트
# 한 번만 실행하면 됩니다.

GH=~/bin/gh
REPO="ljh0196-boop/jinair-monitor"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   진에어 모니터링 - Secrets 설정          ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "📧 알림을 보낼 이메일 주소를 입력하세요."
echo "   (받는 사람: ljh0196@naver.com 은 이미 설정됨)"
echo ""
echo "  Gmail 사용 예: yourname@gmail.com"
echo "  Naver 사용 예: yourname@naver.com"
echo ""
read -r -p "보내는 이메일 주소: " SENDER_EMAIL

echo ""
if [[ "$SENDER_EMAIL" == *"@gmail.com" ]]; then
    echo "📌 Gmail 앱 비밀번호 필요:"
    echo "   1. https://myaccount.google.com/apppasswords 접속"
    echo "   2. 앱: '메일', 기기: '기타(이름 직접 입력)' → '진에어모니터'"
    echo "   3. 생성된 16자리 비밀번호 복사"
elif [[ "$SENDER_EMAIL" == *"@naver.com" ]]; then
    echo "📌 네이버 SMTP 설정 필요:"
    echo "   1. 네이버 메일 → 환경설정 → POP3/IMAP → SMTP 사용함 체크"
    echo "   2. 비밀번호: 네이버 로그인 비밀번호 그대로 입력"
fi

echo ""
read -r -s -p "이메일 비밀번호 (입력해도 화면에 안 보임): " SENDER_PASSWORD
echo ""

# Secrets 설정
echo ""
echo "⏳ GitHub Secrets 설정 중..."
echo "$SENDER_EMAIL" | $GH secret set SENDER_EMAIL --repo "$REPO"
echo "$SENDER_PASSWORD" | $GH secret set SENDER_PASSWORD --repo "$REPO"

echo ""
echo "✅ 완료! 설정된 Secrets:"
$GH secret list --repo "$REPO"

echo ""
echo "🚀 Actions 탭에서 'Run workflow' 버튼으로 테스트해보세요:"
echo "   https://github.com/$REPO/actions"
echo ""
