#!/usr/bin/env python3
"""Crawl swmaestro.ai 멘토링 / 특강 접수내역 (mentoring reception history).

Reads credentials from ASM_USERNAME and ASM_PASSWORD, logs in via Playwright,
walks every page of the reception-history list, and writes JSON to stdout.
Diagnostics go to stderr.

Usage:
    python crawl.py                 # JSON to stdout
    python crawl.py --headed        # show the browser (useful for debugging)
    python crawl.py --out file.json # write to file instead of stdout
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    sys.stderr.write(
        "playwright is not installed. Run:\n"
        "    pip install playwright && playwright install chromium\n"
    )
    sys.exit(2)

# Best-effort: load .env if python-dotenv is installed. Search from CWD
# upward and also next to this script, so running from anywhere works.
try:
    from dotenv import load_dotenv
    load_dotenv()  # CWD search
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))
except ImportError:
    pass

BASE = "https://swmaestro.ai"
LOGIN_URL = f"{BASE}/sw/member/user/forLogin.do?menuNo=200025"
HOME_URL = f"{BASE}/sw/main/main.do"

COLUMNS = [
    "no", "type", "title", "mentor", "session_datetime",
    "registered_at", "status", "approval", "action_slot", "note",
]


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def login(page, username: str, password: str) -> None:
    # The login form uses name="username" / name="password" and a
    # <button class="btn-login" onclick="actionLogin();"> that kicks off
    # a JS-driven POST to /sw/member/user/toLogin.do. On failure the site
    # typically shows a JS alert() and stays on the login page, so we
    # capture any dialog messages to surface in the error.
    dialog_messages: list[str] = []
    page.on("dialog", lambda d: (dialog_messages.append(d.message), d.accept()))

    page.goto(LOGIN_URL, wait_until="networkidle")
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    page.click('button.btn-login')

    # Wait for either a redirect off the login page, or the page to settle
    # while showing an alert/error. 15s is generous for the round trip.
    try:
        page.wait_for_url(lambda url: "forLogin" not in url, timeout=15000)
    except PWTimeout:
        pass  # stayed on login page — we'll diagnose below
    page.wait_for_load_state("networkidle", timeout=15000)

    if "로그아웃" not in page.content():
        reason = f"URL after click: {page.url}"
        if dialog_messages:
            reason += f" | JS alert: {' / '.join(dialog_messages)}"
        raise RuntimeError(
            f"Login failed — '로그아웃' not on page. {reason}\n"
            "Verify ASM_USERNAME / ASM_PASSWORD, or run with --headed to watch."
        )


def navigate_to_history(page) -> None:
    """Walk the UI path a human would take: home → MY PAGE → 멘토링/특강
    게시판 → 접수내역. Direct URLs like history.do?menuNo=N load with
    detached session state on this site, so even a logged-in page can
    show a default/wrong view. Clicking through the menus establishes
    whatever per-request state the server needs to return the real
    접수내역 list.
    """
    page.goto(HOME_URL, wait_until="networkidle")

    log("  > Click MY PAGE")
    page.get_by_role("link", name="MY PAGE").first.click()
    page.wait_for_load_state("networkidle", timeout=15000)

    log("  > Click 멘토링 / 특강 게시판")
    page.get_by_role("link", name="멘토링 / 특강 게시판").first.click()
    page.wait_for_load_state("networkidle", timeout=15000)

    log("  > Click 접수내역")
    # Use the Playwright locator API rather than page.evaluate+a.click():
    # this click triggers a navigation, which destroys the JS execution
    # context before evaluate() can return, producing a confusing
    # 'Execution context was destroyed' error. locator.click() is
    # navigation-aware and waits correctly.
    jeopsu_link = page.get_by_role("link", name="접수내역", exact=True)
    if jeopsu_link.count() == 0:
        raise RuntimeError(
            "Could not find '접수내역' link on the 멘토링/특강 게시판 page. "
            f"URL: {page.url}"
        )
    jeopsu_link.first.click()
    page.wait_for_load_state("networkidle", timeout=15000)

    # Sanity-check: the 접수내역 page must have a table whose header
    # contains '강의날짜'. The header text is rendered via a CSS
    # `::before { content: "강의날짜" }` rule, so `textContent` reads
    # empty — we have to fall back to the pseudo-element's content
    # value from getComputedStyle.
    has_table = page.evaluate(
        "() => {"
        "  const headerText = el => {"
        "    const direct = el.textContent.trim();"
        "    if (direct) return direct;"
        "    const before = window.getComputedStyle(el, '::before').content;"
        "    if (!before || before === 'none') return '';"
        "    return before.replace(/^[\"']|[\"']$/g, '').trim();"
        "  };"
        "  return Array.from(document.querySelectorAll('table')).some(t =>"
        "    Array.from(t.querySelectorAll('th')).some(th =>"
        "      headerText(th).includes('강의날짜')));"
        "}"
    )
    if not has_table:
        raise RuntimeError(
            f"Reached a page without a '강의날짜' table after clicking 접수내역. URL: {page.url}"
        )


def click_next_page(page, current_page_num: int) -> Optional[int]:
    """Click the pagination link for (current_page_num + 1). Falls back to
    '다음' / '다음 목록' when the target number is out of the visible
    batch. Returns the new page number on success, or None if no next
    page is reachable.

    Uses Playwright's locator API (not page.evaluate + element.click()),
    because pagination clicks trigger a navigation that destroys the JS
    execution context mid-call.
    """
    target = current_page_num + 1

    num_link = page.get_by_role("link", name=str(target), exact=True)
    if num_link.count() > 0:
        num_link.first.click()
        page.wait_for_load_state("networkidle", timeout=15000)
        return target

    for label in ("다음 목록", "다음"):
        next_link = page.get_by_role("link", name=label, exact=True)
        if next_link.count() == 0:
            continue
        cls = next_link.first.get_attribute("class") or ""
        if "disabled" in cls:
            continue
        next_link.first.click()
        page.wait_for_load_state("networkidle", timeout=15000)
        return target

    return None


def extract_rows(page) -> list[list[str]]:
    """Walk the page's tables via Playwright locators and pull cell text
    from the table with the most data rows.

    Why locators instead of page.evaluate(...)? On this site, evaluate()
    returning an array surfaces as None on the Python side (suspected
    serializer / polyfill clash). Single-value evaluates (boolean,
    string) work fine — that's why the sanity check and the diagnostic
    dump succeed. The locator API fetches each value over CDP, which
    sidesteps the broken array path.

    Header-text matching is also abandoned here: the labels are rendered
    via CSS `::before` and aren't in textContent, and we already
    discovered above that comparing them is unreliable. Instead we pick
    the table with the most td-containing rows — on the 접수내역 page
    the history table dominates (≈10 data rows) while sibling tables
    (profile / team summary) have at most 1–2 rows.
    """
    tables = page.locator("table").all()
    if not tables:
        return []

    # Rank by (data-row count, column count). Column count is the
    # tiebreaker: on the last page the history table may have only 1
    # data row — the same as the profile/team summary — but it always
    # has more columns (10 vs 8), so we pick it correctly.
    best = None
    best_key = (0, 0)
    for t in tables:
        row_count = t.locator("tr:has(td)").count()
        if row_count == 0:
            continue
        col_count = t.locator("tr:has(td)").first.locator("td").count()
        key = (row_count, col_count)
        if key > best_key:
            best, best_key = t, key
    if best is None:
        return []

    out: list[list[str]] = []
    for row in best.locator("tr:has(td)").all():
        cells = row.locator("td").all()
        if not cells:
            continue
        # inner_text picks up text rendered via CSS ::before too, which
        # matters for any cells that mirror the header pattern.
        out.append([" ".join(c.inner_text().split()) for c in cells])
    return out


def row_to_dict(row: list[str]) -> dict[str, str]:
    return {col: (row[i] if i < len(row) else "") for i, col in enumerate(COLUMNS)}


def crawl(username: str, password: str, headed: bool) -> list[dict[str, Any]]:
    all_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        context = browser.new_context()
        page = context.new_page()
        log("Logging in...")
        login(page, username, password)
        log("Login OK. Navigating to 접수내역 via menu clicks...")
        navigate_to_history(page)
        log("Reached 접수내역. Walking pages...")

        current_page = 1
        while True:
            rows = extract_rows(page)
            if not rows:
                log(f"Page {current_page}: 0 rows — stopping.")
                break
            new_on_page = 0
            for row in rows:
                if not row or not row[0]:
                    continue
                d = row_to_dict(row)
                if d["no"] in seen:
                    continue
                seen.add(d["no"])
                all_rows.append(d)
                new_on_page += 1
            log(f"Page {current_page}: {len(rows)} rows ({new_on_page} new, {len(all_rows)} total)")
            if new_on_page == 0:
                log("No new rows — pagination likely did not advance. Stopping.")
                break
            next_num = click_next_page(page, current_page)
            if next_num is None:
                log(f"No next-page link after page {current_page}. Done.")
                break
            current_page = next_num
            if current_page > 200:
                log("Hit safety cap of 200 pages — stopping.")
                break
        browser.close()
    return all_rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Crawl swmaestro.ai 접수내역")
    ap.add_argument("--out", help="write JSON to this file (default: stdout)")
    ap.add_argument("--headed", action="store_true", help="show the browser window")
    args = ap.parse_args()

    username = os.environ.get("ASM_USERNAME")
    password = os.environ.get("ASM_PASSWORD")
    if not username or not password:
        log("ERROR: set ASM_USERNAME and ASM_PASSWORD environment variables.")
        return 2

    rows = crawl(username, password, headed=args.headed)
    kst = timezone(timedelta(hours=9))
    payload = {
        "count": len(rows),
        "fetched_at": datetime.now(kst).isoformat(timespec="seconds"),
        "rows": rows,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        out_dir = os.path.dirname(os.path.abspath(args.out))
        os.makedirs(out_dir, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        log(f"Wrote {len(rows)} rows to {args.out}")
    else:
        sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
