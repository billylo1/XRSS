#!/usr/bin/env python3
"""
Export X/Twitter cookies as JSON for twikit/XRSS (flat name -> value).

Setup:
  pip install ".[cookies]"
  playwright install chromium
  playwright install chrome    # for --browser chrome (install Google Chrome too)
  playwright install firefox   # optional; for --browser firefox

Why Playwright gets blocked: bundled Chromium is easy for X to fingerprint. Prefer:
  --browser chrome     use your installed Chrome (much less "bot" looking)
  --browser firefox      sometimes works when Chromium does not
  --profile DIR          reuse a real profile directory across runs (warmer trust)

If automation is impossible, export cookies from normal Chrome and convert:
  python scripts/generate_cookies_playwright.py --from-export cookies-export.json

Cookie-export.json can be a JSON array from extensions like "Cookie-Editor" / EditThisCookie,
or an object already in twikit format.

Environment (automated mode): TWITTER_USERNAME, TWITTER_EMAIL, TWITTER_PASSWORD,
optional TWITTER_TOTP_SECRET. COOKIES_FILE is the default output path.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


DEFAULT_PROFILE_DIR = Path(".xrss-playwright-profile")


def _relevant_domain(domain: str) -> bool:
    d = domain.lower().removeprefix(".").removeprefix("www.")
    return d == "x.com" or d.endswith(".x.com") or "twitter.com" in d


def playwright_cookies_to_twikit(cookies: list[dict]) -> dict[str, str]:
    """Merge Playwright cookies into one dict (twikit load_cookies format)."""
    out: dict[str, str] = {}
    sorted_cookies = sorted(cookies, key=lambda c: len(c.get("domain", "")))
    for c in sorted_cookies:
        if not _relevant_domain(str(c.get("domain", ""))):
            continue
        out[str(c["name"])] = str(c["value"])
    return out


def save_cookies(path: Path, cookie_dict: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(cookie_dict, f, indent=2, sort_keys=True)
    print(f"Wrote {len(cookie_dict)} cookies to {path.resolve()}")


def export_array_to_twikit(raw: list[dict[str, Any]]) -> dict[str, str]:
    """Convert [{name, value, domain}, ...] from browser extensions to twikit dict."""
    out: dict[str, str] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        domain = str(item.get("domain", ""))
        if not _relevant_domain(domain):
            continue
        name, value = item.get("name"), item.get("value")
        if name is None or value is None:
            continue
        out[str(name)] = str(value)
    return out


def run_from_export(export_path: Path, output: Path) -> None:
    with export_path.open(encoding="utf-8") as f:
        raw: Any = json.load(f)

    if isinstance(raw, dict):
        # Already twikit-style?
        if raw and all(isinstance(v, str) for v in raw.values()):
            save_cookies(output, raw)
            return
        raise SystemExit(
            "JSON object is not a flat name->value cookie map. "
            "Export from Cookie-Editor as JSON array, or pass that array."
        )

    if isinstance(raw, list):
        data = export_array_to_twikit(raw)
        if not data:
            raise SystemExit(
                "No cookies for x.com / twitter.com domains in that file. "
                "Export while logged in on x.com and include domain cookies."
            )
        save_cookies(output, data)
        return

    raise SystemExit("Unsupported JSON shape; use a list of cookie objects or a flat dict.")


def _create_context(
    p: Any,
    *,
    headed: bool,
    profile_dir: Path | None,
    browser: str,
):
    """
    Returns (context, browser_to_close).
    browser_to_close is None when using launch_persistent_context (close context only).
    """
    viewport = {"width": 1280, "height": 880}
    locale = "en-US"

    chromium_args = [
        "--disable-blink-features=AutomationControlled",
    ]

    if profile_dir is not None:
        profile_dir.mkdir(parents=True, exist_ok=True)
        ud = str(profile_dir.resolve())

        if browser == "firefox":
            ctx = p.firefox.launch_persistent_context(
                user_data_dir=ud,
                headless=not headed,
                viewport=viewport,
                locale=locale,
            )
            return ctx, None

        launch_kw: dict[str, Any] = dict(
            user_data_dir=ud,
            headless=not headed,
            viewport=viewport,
            locale=locale,
            ignore_default_args=["--enable-automation"],
            args=chromium_args,
        )

        if browser == "chrome":
            launch_kw["channel"] = "chrome"
            try:
                ctx = p.chromium.launch_persistent_context(**launch_kw)
                return ctx, None
            except Exception as exc:
                print(
                    f"Could not start Chrome channel ({exc}); retrying with bundled Chromium.\n",
                    file=sys.stderr,
                )
                launch_kw.pop("channel", None)
                ctx = p.chromium.launch_persistent_context(**launch_kw)
                return ctx, None

        # chromium (bundled)
        ctx = p.chromium.launch_persistent_context(**launch_kw)
        return ctx, None

    # Ephemeral (no profile)
    if browser == "firefox":
        browser_handle = p.firefox.launch(headless=not headed)
        ctx = browser_handle.new_context(viewport=viewport, locale=locale)
        return ctx, browser_handle

    launch_kw = dict(
        headless=not headed,
        args=chromium_args,
        ignore_default_args=["--enable-automation"],
    )
    if browser == "chrome":
        launch_kw["channel"] = "chrome"
    try:
        browser_handle = p.chromium.launch(**launch_kw)
    except Exception as exc:
        print(f"Chrome launch failed ({exc}); using Chromium.\n", file=sys.stderr)
        launch_kw.pop("channel", None)
        browser_handle = p.chromium.launch(**launch_kw)

    ctx = browser_handle.new_context(viewport=viewport, locale=locale)
    return ctx, browser_handle


def run_manual(
    output: Path,
    headed: bool,
    profile_dir: Path | None,
    browser: str,
) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        context, browser_handle = _create_context(
            p, headed=headed, profile_dir=profile_dir, browser=browser
        )
        try:
            page = context.new_page()
            # Land on the main site first (sometimes flows login better than /i/flow/login cold)
            page.goto("https://x.com", wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            try:
                page.goto("https://x.com/i/flow/login", wait_until="domcontentloaded")
            except Exception:
                page.goto("https://twitter.com/i/flow/login", wait_until="domcontentloaded")

            print(
                "\n---\n"
                "Complete login in the browser window (including 2FA / Cloudflare if shown).\n"
                "Tip: if the page stays blank, try another --browser (chrome or firefox) "
                "or run again with a persistent --profile.\n"
                "When you see the home timeline, return here.\n"
                "---\n"
            )
            input("Press Enter to save cookies… ")
            cookies = context.cookies()
        finally:
            context.close()
            if browser_handle is not None:
                browser_handle.close()

    save_cookies(output, playwright_cookies_to_twikit(cookies))


def run_auto(
    output: Path,
    headed: bool,
    timeout_ms: int,
    profile_dir: Path | None,
    browser: str,
) -> None:
    username = os.getenv("TWITTER_USERNAME")
    email = os.getenv("TWITTER_EMAIL")
    password = os.getenv("TWITTER_PASSWORD")
    totp_secret = os.getenv("TWITTER_TOTP_SECRET")

    if not username or not password:
        print(
            "TWITTER_USERNAME and TWITTER_PASSWORD must be set for automated login.",
            file=sys.stderr,
        )
        sys.exit(1)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        context, browser_handle = _create_context(
            p, headed=headed, profile_dir=profile_dir, browser=browser
        )
        try:
            page = context.new_page()
            page.goto("https://x.com", wait_until="domcontentloaded")
            page.wait_for_timeout(1200)
            page.goto("https://x.com/i/flow/login", wait_until="domcontentloaded")

            for pattern in (
                r"accept all cookies",
                r"accept optional cookies",
                r"allow all cookies",
            ):
                try:
                    page.get_by_role("button", name=re.compile(pattern, re.I)).click(timeout=4000)
                    break
                except Exception:
                    continue

            user_input = page.locator('input[autocomplete="username"]').first
            user_input.wait_for(state="visible", timeout=timeout_ms)
            user_input.fill(username)

            try:
                page.get_by_role("button", name=re.compile(r"^next$", re.I)).first.click(
                    timeout=8000
                )
            except Exception:
                page.keyboard.press("Enter")

            page.wait_for_timeout(800)

            alt = page.locator('[data-testid="ocfEnterTextTextInput"]')
            if alt.count() > 0 and email:
                try:
                    alt.first.wait_for(state="visible", timeout=5000)
                    alt.first.fill(email)
                    try:
                        page.get_by_role("button", name=re.compile(r"^next$", re.I)).first.click(
                            timeout=5000
                        )
                    except Exception:
                        page.keyboard.press("Enter")
                    page.wait_for_timeout(800)
                except Exception:
                    pass

            pwd = page.locator('input[type="password"]').first
            pwd.wait_for(state="visible", timeout=timeout_ms)
            pwd.fill(password)

            try:
                page.get_by_role("button", name=re.compile(r"log in", re.I)).first.click(
                    timeout=8000
                )
            except Exception:
                page.keyboard.press("Enter")

            page.wait_for_timeout(1500)

            tfa_input = page.locator('[data-testid="ocfEnterTextTextInput"]')
            if totp_secret and tfa_input.count() > 0:
                try:
                    import pyotp

                    tfa_input.first.wait_for(state="visible", timeout=8000)
                    tfa_input.first.fill(pyotp.TOTP(totp_secret).now())
                    try:
                        page.get_by_role("button", name=re.compile(r"next", re.I)).first.click(
                            timeout=8000
                        )
                    except Exception:
                        page.keyboard.press("Enter")
                except Exception:
                    print(
                        "Could not submit TOTP automatically; finish 2FA in the browser, "
                        "then press Enter here.",
                        file=sys.stderr,
                    )
                    input("Press Enter after 2FA succeeds… ")

            try:
                page.wait_for_url(re.compile(r"x\.com/home"), timeout=timeout_ms)
            except Exception:
                print(
                    "\nDid not reach /home automatically. If you are logged in, press Enter "
                    "to export cookies anyway; otherwise Ctrl+C and retry with --manual.\n",
                    file=sys.stderr,
                )
                input("Press Enter to save cookies… ")

            cookies = context.cookies()
        finally:
            context.close()
            if browser_handle is not None:
                browser_handle.close()

    data = playwright_cookies_to_twikit(cookies)
    if not data.get("auth_token") and not data.get("ct0"):
        print(
            "Warning: auth_token/ct0 missing; file may not work with twikit.",
            file=sys.stderr,
        )
    save_cookies(output, data)


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Generate twikit-compatible cookies.json using Playwright "
        "or convert a browser cookie export.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=os.getenv("COOKIES_FILE", "cookies.json"),
        help="Output path (default: COOKIES_FILE or cookies.json)",
    )
    parser.add_argument(
        "--from-export",
        metavar="FILE",
        help="Convert Cookie-Editor / similar JSON export to cookies.json (no browser).",
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Open browser for interactive login, then save cookies.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser headless (often blocked; default is headed).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120_000,
        metavar="MS",
        help="Playwright timeout for waits (default 120000 ms).",
    )
    parser.add_argument(
        "--browser",
        choices=("chrome", "chromium", "firefox"),
        default="chrome",
        help="chrome = installed Google Chrome (recommended). chromium = bundled. "
        "firefox = alternate fingerprint (default: chrome).",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=DEFAULT_PROFILE_DIR,
        metavar="DIR",
        help=f"Persistent browser profile directory (default: {DEFAULT_PROFILE_DIR}). "
        "Ignored when --ephemeral is set.",
    )
    parser.add_argument(
        "--ephemeral",
        action="store_true",
        help="Do not reuse a profile directory (easier to debug, easier for X to flag).",
    )
    args = parser.parse_args()
    output = Path(args.output)

    if args.from_export:
        run_from_export(Path(args.from_export), output)
        return

    headed = not args.headless
    profile_dir: Path | None = None if args.ephemeral else args.profile

    if args.manual:
        run_manual(output, headed=headed, profile_dir=profile_dir, browser=args.browser)
    else:
        run_auto(
            output,
            headed=headed,
            timeout_ms=args.timeout,
            profile_dir=profile_dir,
            browser=args.browser,
        )


if __name__ == "__main__":
    main()
