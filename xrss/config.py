"""Configuration module for XRSS."""

import os

from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Twitter credentials
    twitter_username: str
    twitter_email: str
    twitter_password: str
    twitter_totp_secret: Optional[str] = None

    # Optional HTTP proxy for twikit when X/Cloudflare blocks your IP (set TWITTER_PROXY in env)
    twitter_proxy: Optional[str] = None

    # Redis configuration
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    cache_ttl: int = int(os.getenv("CACHE_TTL", 1800))  # 30 minutes
    background_refresh_interval: int = int(
        os.getenv("BACKGROUND_REFRESH_INTERVAL", 1500)
    )  # 25 minutes

    # Rate limiting
    max_concurrent_requests: int = int(os.getenv("MAX_CONCURRENT_REQUESTS", 2))
    request_delay: float = float(os.getenv("REQUEST_DELAY", 1.0))

    # Server settings
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", 8000))
    debug: bool = bool(os.getenv("DEBUG", False))

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_format: str = os.getenv(
        "LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # File paths
    cookies_file: str = os.getenv("COOKIES_FILE", "cookies.json")
