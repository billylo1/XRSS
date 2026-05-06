"""Utility functions for XRSS."""

import json
import logging
import os
import sys
from typing import Optional

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
