"""HTTP helpers with an on-disk cache, retries and polite rate limiting.

Framework already caches loader *outputs*, but the raw API responses are cached
here too: a FIPE price for a given reference month never changes, so each one
is fetched exactly once, and an interrupted first build resumes where it
stopped instead of starting over.
"""

from __future__ import annotations

import atexit
import hashlib
import os
import sys
import time
from datetime import timedelta
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = Path(os.environ.get("CDC_CACHE_DIR", ROOT / "data_cache"))
USER_AGENT = "car-depreciation-curves/0.1 (build-time data loader; python-httpx)"
# Offline mode: serve everything from the cache, whatever its age, and never touch
# the network. Used in CI, where FIPE answers 403 to GitHub's runners.
OFFLINE = os.environ.get("CDC_OFFLINE", "") not in ("", "0", "false")

# Status codes worth retrying: rate limiting and transient server errors.
RETRY_STATUS = {429, 500, 502, 503, 504}


class NotFound(Exception):
    """The resource does not exist."""


def log(*args: object) -> None:
    """Loaders write data to stdout, so all diagnostics must go to stderr."""
    print(*args, file=sys.stderr, flush=True)


class RateLimiter:
    """Fixed-interval limiter: at most ``per_minute`` calls per minute.

    It adapts, because FIPE doesn't publish its limit and it varies with load:
    every 429 makes it 25% slower (down to ``floor`` calls per minute), and
    every 50 successful calls in a row make it 10% faster again (up to the
    initial rate).
    """

    def __init__(self, per_minute: int, floor: int = 20):
        self.interval = self.min_interval = 60.0 / per_minute
        self.max_interval = 60.0 / floor
        self._last = 0.0
        self._ok = 0

    @property
    def per_minute(self) -> float:
        return 60.0 / self.interval

    def slow_down(self) -> None:
        self.interval = min(self.interval * 1.25, self.max_interval)
        self._ok = 0

    def success(self) -> None:
        self._ok += 1
        if self._ok >= 50:
            self.interval = max(self.interval / 1.1, self.min_interval)
            self._ok = 0

    def wait(self) -> None:
        now = time.monotonic()
        sleep_for = self._last + self.interval - now
        if sleep_for > 0:
            time.sleep(sleep_for)
        self._last = time.monotonic()


def _cache_path(url: str, params: dict | None, data: dict | None, suffix: str) -> Path:
    key = url + "?" + "&".join(f"{k}={v}" for k, v in sorted((params or {}).items()))
    if data is not None:
        key += "#" + "&".join(f"{k}={v}" for k, v in sorted(data.items()))
    digest = hashlib.sha256(key.encode()).hexdigest()[:20]
    return CACHE_DIR / digest[:2] / f"{digest}{suffix}"


def cached(url: str, *, params: dict | None = None, data: dict | None = None, suffix: str = ".bin") -> bool:
    """Whether a response is already on disk (used to report how much a build will download)."""
    return _cache_path(url, params, data, suffix).exists()


def cached_path(url: str, *, params: dict | None = None, data: dict | None = None, suffix: str = ".bin") -> Path | None:
    """Where ``fetch`` stored this request, or None if it was never downloaded.

    ``suffix`` must match the one passed to ``fetch``. Ignores ``max_age``.
    """
    path = _cache_path(url, params, data, suffix)
    return path if path.exists() else None


# One client for the whole process: FIPE answers thousands of tiny requests, and
# re-using the TLS connection roughly halves the time per request.
_client: httpx.Client | None = None


def _get_client(timeout: float) -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(follow_redirects=True, timeout=timeout)
        atexit.register(_client.close)
    return _client


def fetch(
    url: str,
    *,
    params: dict | None = None,
    data: dict | None = None,
    headers: dict | None = None,
    max_age: timedelta | None = timedelta(days=7),
    suffix: str = ".bin",
    limiter: RateLimiter | None = None,
    retries: int = 5,
    timeout: float = 120.0,
) -> bytes:
    """GET ``url`` (or POST ``data`` as a form) and return the body, using the disk cache when fresh.

    The form ``data`` is part of the cache key; ``headers`` are not, so secrets
    never end up in file names. ``max_age=None`` caches forever. ``limiter`` is
    only consulted for real network calls, so cached builds run at full speed.
    """
    path = _cache_path(url, params, data, suffix)
    if path.exists() and (OFFLINE or max_age is None or time.time() - path.stat().st_mtime < max_age.total_seconds()):
        return path.read_bytes()
    if OFFLINE:
        raise RuntimeError(
            f"CDC_OFFLINE is set but {url} {data or params or ''} is not in {CACHE_DIR}. "
            "Run the build locally (without CDC_OFFLINE) to download it, then commit data_cache/."
        )

    hdrs = {"User-Agent": USER_AGENT} | (headers or {})
    delay = 5.0
    for attempt in range(1, retries + 1):
        if limiter:
            limiter.wait()
        try:
            client = _get_client(timeout)
            if data is None:
                resp = client.get(url, params=params, headers=hdrs)
            else:
                # FIPE rejects body-less POSTs with "411 Length Required".
                resp = client.post(url, params=params, data=data or {"_": ""}, headers=hdrs)
            if resp.status_code == 404:
                raise NotFound(f"{resp.status_code} for {url}")
            if resp.status_code == 403:
                # Not transient: FIPE refuses some networks outright (GitHub Actions
                # runners, for one), so retrying only wastes time.
                raise PermissionError(
                    f"403 Forbidden from {url}: this network is blocked by the server. "
                    "Download the data from another network and build with CDC_OFFLINE=1."
                )
            if resp.status_code in RETRY_STATUS:
                raise httpx.HTTPStatusError(f"{resp.status_code}", request=resp.request, response=resp)
            resp.raise_for_status()
            body = resp.content
            if limiter:
                limiter.success()
            break
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            if attempt == retries:
                raise
            if limiter and getattr(getattr(exc, "response", None), "status_code", None) == 429:
                limiter.slow_down()
            retry_after = getattr(getattr(exc, "response", None), "headers", {}).get("Retry-After")
            wait = float(retry_after) if retry_after and retry_after.isdigit() else delay
            log(f"  retry {attempt}/{retries} for {url} in {wait:.0f}s ({exc})")
            time.sleep(wait)
            delay *= 2

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(body)
    tmp.replace(path)
    return body
