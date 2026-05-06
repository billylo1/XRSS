"""Utility functions for XRSS."""

import asyncio
import json
import logging
import os
import re
import sys
from typing import Any, Optional
from urllib.parse import urlparse

logger = logging.getLogger("xrss")


def is_redis_connection_error(exc: BaseException) -> bool:
    """Cache/backend unreachable (redis.asyncio client)."""
    try:
        from redis.exceptions import ConnectionError as RedisConnectionError

        return isinstance(exc, RedisConnectionError)
    except ImportError:
        return False


def is_cloudflare_block(message: str) -> bool:
    """Detect Cloudflare bot/HTML block pages embedded in exception messages."""
    m = message.lower()
    return (
        "cloudflare" in m
        or "cf-ray" in m
        or "attention required" in m
        or "sorry, you have been blocked" in m
    )


def is_connect_error(exc: BaseException) -> bool:
    """TCP/DNS/proxy failures before any HTTP response (e.g. bad TWITTER_PROXY)."""
    if is_redis_connection_error(exc):
        return False
    try:
        import httpx

        if isinstance(exc, (httpx.ConnectError, httpx.ProxyError)):
            return True
    except ImportError:
        pass
    low = str(exc).lower()
    return (
        "all connection attempts failed" in low
        or "connection refused" in low
        or "could not resolve host" in low
        or "name or service not known" in low
        or "network is unreachable" in low
        or "nodename nor servname" in low
    )


def summarize_twikit_error(exc: BaseException) -> str:
    """Short log/API message; avoids dumping multi-page HTML from X/Cloudflare."""
    msg = str(exc)
    if is_redis_connection_error(exc):
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        return (
            f"Redis is not reachable ({redis_url}). Start Redis "
            "(e.g. `brew services start redis` or `docker run -p 6379:6379 redis`), "
            "or set REDIS_URL to a running server."
        )
    if is_cloudflare_block(msg):
        return (
            "X.com returned a Cloudflare block (403) for this client or network. "
            "Try a cookies.json from a logged-in browser session, set TWITTER_PROXY to a proxy "
            "X accepts, or use a different network/IP."
        )
    if is_connect_error(exc):
        hint = (
            "Could not connect to x.com or your proxy (TCP/DNS). "
            "If TWITTER_PROXY is set, fix scheme (http:// or socks5://), host, port, and auth, "
            "or unset TWITTER_PROXY to try a direct connection."
        )
        if os.getenv("TWITTER_PROXY"):
            hint += " Verify the proxy is reachable from this machine."
        return hint
    if len(msg) > 1200:
        return msg[:1200] + "… [truncated]"
    return msg


def setup_logging(level: Optional[str] = None) -> logging.Logger:
    """
    Set up logging configuration.

    Args:
        level: Optional logging level (defaults to INFO if not specified)

    Returns:
        Configured logger instance
    """

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(handler)

    logger.setLevel(level or logging.INFO)
    return logger


def _is_internal_x_host(hostname: str) -> bool:
    h = hostname.lower()
    return h in ("twitter.com", "x.com", "mobile.twitter.com") or h.endswith(".twitter.com")


_TCO_HTTP_URL = re.compile(r"https?://t\.co/[A-Za-z0-9]+")
# Any http(s) URL token in tweet text (expanded links, pics, etc.)
_HTTP_URL_TOKEN = re.compile(r"https?://[^\s<]+")


def rss_title_from_description(description: str) -> str:
    """
    RSS <title>: same text as the item body/description but without URL tokens
    (short t.co links and expanded https URLs).
    """
    if not (description or "").strip():
        return ""
    out = _HTTP_URL_TOKEN.sub("", description)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def _normalize_scheme(url: str) -> str:
    u = url.strip().rstrip("/")
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    return u


def _expanded_if_external(exp: str | None) -> Optional[str]:
    if not exp or not exp.startswith(("http://", "https://")):
        return None
    try:
        host = urlparse(exp).hostname or ""
    except ValueError:
        return None
    if not host or _is_internal_x_host(host):
        return None
    return exp


def primary_external_article_url(url_entities: list | None) -> Optional[str]:
    """
    First expanded URL that points outside twitter.com / x.com (the linked article).
    """
    if not url_entities:
        return None
    for ent in url_entities:
        if not isinstance(ent, dict):
            continue
        exp = _expanded_if_external(ent.get("expanded_url") or ent.get("expanded_URL"))
        if exp:
            return exp
    return None


def last_external_article_url(url_entities: list | None) -> Optional[str]:
    """Last non-X expanded_url in entity order (often the trailing t.co target)."""
    if not url_entities:
        return None
    for ent in reversed(url_entities):
        if not isinstance(ent, dict):
            continue
        exp = _expanded_if_external(ent.get("expanded_url") or ent.get("expanded_URL"))
        if exp:
            return exp
    return None


def primary_article_url_for_rss(full_text: str, url_entities: list | None) -> Optional[str]:
    """
    RSS <link>: use expanded_url for the last https://t.co/... in the tweet text when possible.
    That is usually the article URL at the end of AP-style posts.
    """
    if not url_entities:
        return None

    if full_text:
        matches = list(_TCO_HTTP_URL.finditer(full_text))
        if matches:
            last_short = matches[-1].group(0)
            last_norm = _normalize_scheme(last_short)
            for ent in url_entities:
                if not isinstance(ent, dict):
                    continue
                su = (ent.get("url") or "").strip()
                if not su:
                    continue
                if _normalize_scheme(su) == last_norm:
                    exp = _expanded_if_external(
                        ent.get("expanded_url") or ent.get("expanded_URL")
                    )
                    if exp:
                        return exp

    found = last_external_article_url(url_entities)
    if found:
        return found
    return primary_external_article_url(url_entities)


def merge_url_entities_for_display(tweet: Any) -> list:
    """URL entities from retweet original, main tweet, then quote — order for expansion."""
    merged: list = []
    if getattr(tweet, "retweeted_tweet", None) and getattr(tweet, "type", None) == "Retweet":
        merged.extend(getattr(tweet.retweeted_tweet, "urls", None) or [])
    merged.extend(getattr(tweet, "urls", None) or [])
    quoted = getattr(tweet, "quoted_tweet", None) or getattr(tweet, "quote", None)
    if quoted:
        merged.extend(getattr(quoted, "urls", None) or [])
    return merged


def expand_short_urls_in_text(full_text: str, url_entities: list | None) -> str:
    """Replace t.co (etc.) with expanded_url in tweet text for RSS description."""
    if not full_text or not url_entities:
        return full_text
    out = full_text
    for ent in url_entities:
        if not isinstance(ent, dict):
            continue
        short = ent.get("url")
        exp = ent.get("expanded_url") or ent.get("expanded_URL")
        if not short or not exp:
            continue
        if short in out:
            out = out.replace(short, exp)
    return out


def _follow_tco_redirect(short_url: str) -> str:
    """Resolve a t.co URL to its final destination (fallback when entities lack expanded_url)."""
    try:
        import requests

        headers = {"User-Agent": "Mozilla/5.0 (compatible; XRSS/0.1; +https://github.com/thytu/XRSS)"}
        r = requests.head(short_url, allow_redirects=True, timeout=15, headers=headers)
        if r.status_code >= 400 or not r.url:
            r = requests.get(short_url, allow_redirects=True, timeout=15, headers=headers, stream=True)
            try:
                r.close()
            except Exception:
                pass
        return str(r.url)
    except Exception:
        logger.debug("t.co redirect resolve failed for %s", short_url, exc_info=True)
        return short_url


def follow_short_url(short_url: str) -> Optional[str]:
    """
    Resolve a short URL (t.co etc.) to its external destination.
    Returns None if the resolved URL is still on twitter.com / x.com or resolution failed.
    Intended to be called via asyncio.to_thread from async code.
    """
    resolved = _follow_tco_redirect(short_url)
    if resolved == short_url:
        return None
    try:
        host = urlparse(resolved).hostname or ""
    except ValueError:
        return None
    if not host or _is_internal_x_host(host):
        return None
    return resolved


def resolve_tco_redirects_in_text(full_text: str) -> tuple[str, Optional[str]]:
    """
    Expand remaining t.co links by following redirects.
    Returns (updated_text, last_external_url) for RSS <link> when entities were incomplete.
    """
    if not full_text or "t.co/" not in full_text:
        return full_text, None
    matches = list(_TCO_HTTP_URL.finditer(full_text))
    if not matches:
        return full_text, None

    cache: dict[str, str] = {}
    last_external: Optional[str] = None
    for m in matches:
        short = m.group(0)
        if short not in cache:
            cache[short] = _follow_tco_redirect(short)
        final = cache[short]
        try:
            host = urlparse(final).hostname or ""
        except ValueError:
            host = ""
        if host and not _is_internal_x_host(host):
            last_external = final

    out = full_text
    for short, final in cache.items():
        if short != final:
            out = out.replace(short, final)

    return out, last_external


async def enrich_feed_text_and_article_link(
    raw_text: str, url_entities: list | None
) -> tuple[str, Optional[str]]:
    """
    Expanded description + external article URL for RSS <link>.
    Uses API url_entities only — no live HTTP redirect following.
    """
    full_text = expand_short_urls_in_text(raw_text, url_entities)
    article_link = primary_article_url_for_rss(raw_text, url_entities)
    return full_text, article_link


def clean_tweet(tweet: str) -> str:
    """
    Clean and format tweet text by removing retweet prefixes.

    Args:
        tweet: The original tweet text to clean

    Returns:
        Cleaned tweet text with retweet prefixes removed if present

    Example:
        >>> clean_tweet("RT @user: This is the actual content")
        "This is the actual content"
        >>> clean_tweet("Regular tweet without RT")
        "Regular tweet without RT"
    """

    if tweet.startswith("RT @"):
        colon_index = tweet.find(":")
        if colon_index != -1:
            return tweet[colon_index + 2 :]
    return tweet


def clean_cookies(cookie_file: str = "cookies.json") -> None:
    """
    Clean up cookie file to prevent authentication issues.

    Args:
        cookie_file: Path to the cookie file (defaults to cookies.json)
    """

    # Create directory if it doesn't exist
    cookie_dir = os.path.dirname(cookie_file)
    if cookie_dir:  # Only create directory if path contains one
        os.makedirs(cookie_dir, exist_ok=True)

    if not os.path.exists(cookie_file):
        logger.warning(f"Cookie file not found: {cookie_file}")
        return

    try:
        with open(cookie_file, "r") as f:
            cookies = json.load(f)

        # Keep only the most recent ct0 cookie if multiple exist
        ct0_cookies = [c for c in cookies if isinstance(c, dict) and c.get("name") == "ct0"]

        if len(ct0_cookies) > 1:
            logger.warning("Found multiple ct0 cookies, removing all but the most recent")
            os.remove(cookie_file)

    except Exception as e:
        logger.error(f"Error cleaning cookies: {str(e)}")

        if os.path.exists(cookie_file):
            os.remove(cookie_file)
