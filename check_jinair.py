#!/usr/bin/env python3
"""진에어 취소표 모니터링 — KAYAK 경유, Mac 로컬 실행"""

import asyncio
import os
import smtplib
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

FLIGHTS = [
    {
        "id": "GMP_HIN_0924",
        "departure": "GMP",
        "arrival": "HIN",
        "date": "2026-09-24",
        "departure_name": "김포",
        "arrival_name": "사천",
    },
    {
        "id": "HIN_GMP_0926",
        "departure": "HIN",
        "arrival": "GMP",
        "date": "2026-09-26",
        "departure_name": "사천",
        "arrival_name": "김포",
    },
]

SENDER_EMAIL = os.environ["SENDER_EMAIL"]
SENDER_PASSWORD = os.environ["SENDER_PASSWORD"]
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "ljh0196@naver.com")

LOG_FILE = os.path.join(os.path.dirname(__file__), "monitor.log")


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def get_smtp(email: str) -> tuple[str, int]:
    domain = email.split("@")[-1].lower()
    if domain == "naver.com":
        return "smtp.naver.com", 587
    return "smtp.gmail.com", 587


def send_email(flight: dict, seats: list) -> None:
    subject = (
        f"✈️ [진에어] 취소표 발생! "
        f"{flight['departure_name']}→{flight['arrival_name']} ({flight['date']})"
    )
    items_html = "".join(f"<li>{s}</li>" for s in seats)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    kayak_url = (
        f"https://www.kayak.co.kr/flights/"
        f"{flight['departure']}-{flight['arrival']}/{flight['date']}/1adults"
        f"?airlines=LJ&sort=price_a"
    )
    body = f"""
<html><body style="font-family:sans-serif;max-width:600px;margin:0 auto">
<div style="background:#1a56db;color:white;padding:20px;border-radius:8px 8px 0 0">
  <h2 style="margin:0">✈️ 진에어 취소표 알림</h2>
</div>
<div style="border:1px solid #ddd;border-top:none;padding:20px;border-radius:0 0 8px 8px">
  <p>아래 항공편에 <strong>진에어 좌석이 생겼습니다!</strong> 빠르게 예매하세요.</p>
  <table style="width:100%;border-collapse:collapse;margin:16px 0">
    <tr style="background:#f3f4f6">
      <td style="padding:10px;font-weight:bold;width:30%">노선</td>
      <td style="padding:10px">{flight['departure_name']}({flight['departure']}) → {flight['arrival_name']}({flight['arrival']})</td>
    </tr>
    <tr>
      <td style="padding:10px;font-weight:bold">날짜</td>
      <td style="padding:10px">{flight['date']}</td>
    </tr>
    <tr style="background:#f3f4f6">
      <td style="padding:10px;font-weight:bold">발견 시각</td>
      <td style="padding:10px">{now}</td>
    </tr>
  </table>
  <p><strong>확인된 항공편:</strong></p>
  <ul>{items_html}</ul>
  <div style="text-align:center;margin:24px 0">
    <a href="https://www.jinair.com/booking/index"
       style="background:#1a56db;color:white;padding:14px 32px;text-decoration:none;
              border-radius:6px;font-size:16px;font-weight:bold;margin-right:8px">
      진에어 바로 예매 →
    </a>
    <a href="{kayak_url}"
       style="background:#ff690f;color:white;padding:14px 32px;text-decoration:none;
              border-radius:6px;font-size:16px;font-weight:bold">
      KAYAK에서 확인
    </a>
  </div>
  <p style="color:#9ca3af;font-size:12px;border-top:1px solid #e5e7eb;padding-top:12px">
    진에어 취소표 모니터링 자동 발송 | 데이터 출처: KAYAK
  </p>
</div>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(body, "html", "utf-8"))

    host, port = get_smtp(SENDER_EMAIL)
    with smtplib.SMTP(host, port) as server:
        server.ehlo()
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
    log(f"  ✅ 이메일 발송 → {RECIPIENT_EMAIL}")


async def check_flight(page, flight: dict) -> list:
    """KAYAK에서 진에어 직항 좌석 확인. 가용 항공편 정보 리스트 반환."""
    dep, arr, date = flight["departure"], flight["arrival"], flight["date"]
    url = (
        f"https://www.kayak.co.kr/flights/{dep}-{arr}/{date}/1adults"
        f"?airlines=LJ&stops=0&sort=price_a"
    )
    log(f"  🔍 {flight['departure_name']}({dep}) → {flight['arrival_name']}({arr}) | {date}")

    try:
        await page.goto(url, wait_until="load", timeout=30000)
    except PlaywrightTimeout:
        log("  ⚠️  페이지 로드 타임아웃")

    # 항공권 결과 로딩 대기
    try:
        await page.wait_for_selector("[class*='nrc6'], [class*='resultWrapper'], [class*='flight']",
                                     timeout=15000)
    except PlaywrightTimeout:
        pass
    await page.wait_for_timeout(5000)

    body_text = await page.inner_text("body")

    # ── 진에어 항공편 찾기 ────────────────────────────
    available = []

    # 페이지에 진에어 언급 여부
    has_jinair = "진에어" in body_text
    has_price = any(kw in body_text for kw in ["원", "KRW"])
    sold_out = any(kw in body_text for kw in ["예약 불가", "매진", "결과 없음", "항공편 없음", "검색 결과가 없습니다"])

    if sold_out or not has_jinair:
        log("  ❌ 진에어 좌석 없음")
        return []

    if has_jinair and has_price:
        # 가격 라인 파싱
        lines = [l.strip() for l in body_text.split("\n") if l.strip()]
        jinair_idx = [i for i, l in enumerate(lines) if "진에어" in l]

        for idx in jinair_idx:
            # 진에어 주변 라인에서 시간/가격 추출
            context_lines = lines[max(0, idx-5):idx+8]
            time_info = ""
            price_info = ""
            for l in context_lines:
                if "–" in l and (":" in l or "시" in l):
                    time_info = l
                if "원" in l and any(c.isdigit() for c in l):
                    price_info = l
            if time_info or price_info:
                info = f"진에어 직항 {time_info} {price_info}".strip()
                if info not in available:
                    available.append(info)

        if not available:
            available.append("진에어 직항 좌석 확인됨 — 가격 직접 확인 필요")

    return available


async def main() -> None:
    log(f"\n{'═'*52}")
    log(f"🚀 진에어 모니터링 시작")

    found: list[tuple] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="ko-KR",
        )
        # webdriver 플래그 숨기기 (KAYAK 봇 탐지 완화)
        await ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = await ctx.new_page()

        for flight in FLIGHTS:
            try:
                seats = await check_flight(page, flight)
                if seats:
                    log(f"  🎉 좌석 발견: {seats}")
                    found.append((flight, seats))
                else:
                    log("  — 매진 상태 유지")
            except Exception as exc:
                log(f"  ❌ 오류: {exc}")
            await page.wait_for_timeout(3000)

        await ctx.close()
        await browser.close()

    for flight, seats in found:
        try:
            send_email(flight, seats)
        except Exception as exc:
            log(f"  ❌ 이메일 실패: {exc}")

    if not found:
        log("ℹ️  가용 좌석 없음 — 알림 없음")
    log("✅ 완료")


if __name__ == "__main__":
    asyncio.run(main())
