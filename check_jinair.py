#!/usr/bin/env python3
"""진에어 취소표 모니터링 — GMP↔HIN"""

import asyncio
import os
import smtplib
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
    body = f"""
<html><body style="font-family:sans-serif;max-width:600px;margin:0 auto">
<div style="background:#1a56db;color:white;padding:20px;border-radius:8px 8px 0 0">
  <h2 style="margin:0">✈️ 진에어 취소표 알림</h2>
</div>
<div style="border:1px solid #ddd;border-top:none;padding:20px;border-radius:0 0 8px 8px">
  <p>아래 항공편에 <strong>좌석이 생겼습니다!</strong> 빠르게 예매하세요.</p>
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
  <p><strong>가용 좌석 정보:</strong></p>
  <ul>{items_html}</ul>
  <div style="text-align:center;margin:24px 0">
    <a href="https://www.jinair.com/booking/index"
       style="background:#1a56db;color:white;padding:14px 32px;text-decoration:none;
              border-radius:6px;font-size:16px;font-weight:bold">
      지금 바로 예매하기 →
    </a>
  </div>
  <p style="color:#9ca3af;font-size:12px;border-top:1px solid #e5e7eb;padding-top:12px">
    진에어 취소표 모니터링 시스템(GitHub Actions) 자동 발송
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
    print(f"  ✅ 이메일 발송 → {RECIPIENT_EMAIL}")


async def try_click(page, selectors: list, timeout: int = 3000) -> bool:
    for sel in selectors:
        try:
            await page.click(sel, timeout=timeout)
            return True
        except Exception:
            continue
    return False


async def try_fill(page, selectors: list, value: str, timeout: int = 3000) -> bool:
    for sel in selectors:
        try:
            await page.click(sel, timeout=timeout)
            await page.fill(sel, value, timeout=timeout)
            return True
        except Exception:
            continue
    return False


async def check_flight(page, flight: dict) -> list:
    print(f"\n{'─'*52}")
    print(f"🔍 {flight['departure_name']}({flight['departure']}) → "
          f"{flight['arrival_name']}({flight['arrival']}) | {flight['date']}")

    api_responses: list[dict] = []

    async def on_response(response):
        if any(k in response.url for k in ["avail", "flight", "schedule", "fare", "lowfare"]):
            try:
                api_responses.append({"url": response.url, "data": await response.json()})
            except Exception:
                pass

    page.on("response", on_response)

    # ── 1) 페이지 로드 ────────────────────────────────
    try:
        await page.goto(
            "https://www.jinair.com/booking/index?snsLang=ko_KR&ctrCd=KOR",
            wait_until="networkidle",
            timeout=30000,
        )
    except PlaywrightTimeout:
        print("  ⚠️  로드 타임아웃, 계속 진행")
    await page.wait_for_timeout(2000)

    # ── 2) 편도 선택 ──────────────────────────────────
    await try_click(page, [
        "text=편도", 'input[value="OW"]',
        'label:has-text("편도")', '[data-value="OW"]',
    ])
    await page.wait_for_timeout(500)

    # ── 3) 출발지 입력 ────────────────────────────────
    dep = flight["departure"]
    for sel in [
        "#dep_airport", "#departureAirport", 'input[name="depAirport"]',
        'input[placeholder*="출발"]', '[aria-label*="출발"]',
        ".departure input", '[class*="departure"] input',
    ]:
        try:
            await page.click(sel, timeout=2000)
            await page.fill(sel, dep, timeout=2000)
            await page.wait_for_timeout(800)
            for ac in [f"text={dep}", f'[data-code="{dep}"]', f'li:has-text("{dep}")']:
                try:
                    await page.click(ac, timeout=2000)
                    print(f"  ✓ 출발지: {dep}")
                    break
                except Exception:
                    continue
            break
        except Exception:
            continue
    await page.wait_for_timeout(500)

    # ── 4) 도착지 입력 ────────────────────────────────
    arr = flight["arrival"]
    for sel in [
        "#arr_airport", "#arrivalAirport", 'input[name="arrAirport"]',
        'input[placeholder*="도착"]', '[aria-label*="도착"]',
        ".arrival input", '[class*="arrival"] input',
    ]:
        try:
            await page.click(sel, timeout=2000)
            await page.fill(sel, arr, timeout=2000)
            await page.wait_for_timeout(800)
            for ac in [f"text={arr}", f'[data-code="{arr}"]', f'li:has-text("{arr}")']:
                try:
                    await page.click(ac, timeout=2000)
                    print(f"  ✓ 도착지: {arr}")
                    break
                except Exception:
                    continue
            break
        except Exception:
            continue
    await page.wait_for_timeout(500)

    # ── 5) 날짜 선택 ──────────────────────────────────
    date_str = flight["date"]
    day_only = str(int(date_str.split("-")[2]))
    await try_fill(page, [
        "#dep_date", "#departureDate", 'input[name="depDate"]',
        'input[type="date"]', '[aria-label*="출발일"]', ".departure-date input",
    ], date_str)
    try:
        await page.click(f'button:has-text("{day_only}")', timeout=2000)
    except Exception:
        pass
    await page.wait_for_timeout(500)

    # ── 6) 검색 실행 ──────────────────────────────────
    clicked = await try_click(page, [
        'button:has-text("항공권 검색")', 'button:has-text("검색")',
        'button:has-text("조회")', "#btnSearch", ".btn-search",
        'button[type="submit"]', 'input[type="submit"]',
    ], timeout=4000)
    if clicked:
        print("  ✓ 검색 실행")

    try:
        await page.wait_for_load_state("networkidle", timeout=30000)
    except PlaywrightTimeout:
        pass
    await page.wait_for_timeout(3000)

    # ── 7) 스크린샷 (디버깅) ──────────────────────────
    os.makedirs("screenshots", exist_ok=True)
    shot = f"screenshots/{flight['id']}_{datetime.now().strftime('%H%M%S')}.png"
    await page.screenshot(path=shot, full_page=True)
    print(f"  📸 {shot}")

    # ── 8) 가용 좌석 파싱 ─────────────────────────────
    available: list[str] = []

    # API 응답 우선 파싱 (Navitaire 스타일)
    for resp in api_responses:
        data = resp["data"]
        if not isinstance(data, dict):
            continue
        root = data.get("data", data)
        for jk in ["journeys", "Journeys", "flights", "Flights"]:
            for journey in root.get(jk, []):
                for sk in ["segments", "Segments"]:
                    for seg in journey.get(sk, []):
                        for fk in ["fares", "Fares"]:
                            for fare in seg.get(fk, []):
                                count = int(
                                    fare.get("availableSeats")
                                    or fare.get("AvailabilityCount")
                                    or 0
                                )
                                if count > 0:
                                    cls = fare.get("class") or fare.get("ClassOfService") or ""
                                    price = fare.get("price") or fare.get("FareAmount") or ""
                                    available.append(f"클래스: {cls} | 잔여 {count}석 | {price}원")

    # 페이지 텍스트 fallback
    if not available:
        body_text = await page.inner_text("body")
        sold_out = any(kw in body_text for kw in ["매진", "SOLD OUT", "좌석없음", "잔여좌석 0"])
        has_select = any(kw in body_text for kw in ["선택", "원"])

        if not sold_out and has_select:
            price_lines = [
                ln.strip() for ln in body_text.split("\n")
                if "원" in ln and any(c.isdigit() for c in ln)
            ]
            if price_lines:
                available.extend(price_lines[:5])
            else:
                available.append("좌석 있음 — 스크린샷 확인 후 직접 예매하세요")
        elif sold_out:
            print("  ❌ 매진 확인")
        else:
            print("  ⚠️  판단 불가 — 스크린샷을 확인하세요")

    page.remove_listener("response", on_response)
    return available


async def main() -> None:
    print(f"\n{'═'*52}")
    print(f"🚀 진에어 모니터링 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═'*52}")

    found: list[tuple] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="ko-KR",
        )
        page = await ctx.new_page()

        for flight in FLIGHTS:
            try:
                seats = await check_flight(page, flight)
                if seats:
                    print(f"  🎉 좌석 발견!")
                    found.append((flight, seats))
            except Exception as exc:
                print(f"  ❌ 오류: {exc}")
            await page.wait_for_timeout(2000)

        await ctx.close()
        await browser.close()

    for flight, seats in found:
        try:
            send_email(flight, seats)
        except Exception as exc:
            print(f"  ❌ 이메일 실패: {exc}")

    if not found:
        print("\nℹ️  모든 노선 매진 — 알림 없음")
    print(f"\n✅ 완료 | {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    asyncio.run(main())
