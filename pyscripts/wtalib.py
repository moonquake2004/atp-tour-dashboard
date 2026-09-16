"""
Shared helpers for the WTA dashboard data pipeline.

All data comes from the official WTA public JSON API that powers
wtatennis.com (https://api.wtatennis.com/tennis).  Nothing is scraped from HTML:
every record is the same payload the official site itself consumes.

The API is undocumented and rate-limited, so every request passes through a
politeness gate (bounded concurrency plus a minimum gap) and is retried with
exponential backoff.

Standard library only — no third-party packages.
"""

from __future__ import annotations

import http.client
import json
import os
import random
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.wtatennis.com/tennis"
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# Politeness gate
# ---------------------------------------------------------------------------

MAX_CONCURRENCY = int(os.environ.get("WTA_CONCURRENCY", "5"))
MIN_GAP = float(os.environ.get("WTA_GAP_MS", "90")) / 1000.0

# ---------------------------------------------------------------------------
# TLS
# ---------------------------------------------------------------------------


def _ssl_context() -> ssl.SSLContext:
    """
    Build a verifying TLS context.

    Python on macOS is often installed without a CA bundle, and a bare
    ``urlopen`` then fails with CERTIFICATE_VERIFY_FAILED.  Verification is always
    on; only the bundle location is discovered, in order of trust: an explicit
    environment override, certifi, then the platform stores.
    """
    candidates = [
        os.environ.get("SSL_CERT_FILE"),
        os.environ.get("REQUESTS_CA_BUNDLE"),
    ]
    try:
        import certifi  # noqa: PLC0415 - optional dependency

        candidates.append(certifi.where())
    except Exception:  # noqa: BLE001
        pass
    candidates += [
        "/etc/ssl/cert.pem",  # macOS system store
        "/opt/homebrew/etc/ca-certificates/cert.pem",
        "/opt/homebrew/etc/openssl@3/cert.pem",
        "/usr/local/etc/openssl@3/cert.pem",
        "/etc/pki/tls/certs/ca-bundle.crt",  # RHEL family
        "/etc/ssl/certs/ca-certificates.crt",  # Debian family
    ]

    context = ssl.create_default_context()
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            try:
                context.load_verify_locations(candidate)
                return context
            except ssl.SSLError:
                continue
    return context


SSL_CONTEXT = _ssl_context()

_gate = threading.Lock()
_slots = threading.Semaphore(MAX_CONCURRENCY)
_last_start = 0.0


def _throttle() -> None:
    """Serialise the spacing between request starts."""
    global _last_start
    with _gate:
        now = time.monotonic()
        wait = _last_start + MIN_GAP - now
        if wait > 0:
            time.sleep(wait)
            now = time.monotonic()
        _last_start = now


def sleep(seconds: float) -> None:
    time.sleep(seconds)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


class ApiError(RuntimeError):
    pass


def _fetch_json(url: str, headers: dict[str, str], timeout: float, *, read_retries: int = 4) -> object:
    """
    Fetch and decode JSON.

    urllib intermittently truncates large responses on macOS (IncompleteRead)
    even with retries inside the same call, so the body is read explicitly and
    in chunks over a plain HTTPSConnection.  That also lets a truncated read be
    retried without re-running the whole request pipeline.
    """
    import http.client

    parsed = urllib.parse.urlsplit(url)
    path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
    request_headers = dict(headers)
    request_headers.setdefault("Accept-Encoding", "identity")  # no gzip → no truncation
    request_headers.setdefault("Connection", "close")

    last_error: Exception | None = None
    for attempt in range(read_retries):
        if attempt:
            time.sleep(0.8 * attempt)
        # After the second failure of the Python stack, fall back to curl: it
        # handles the intermittent truncated reads on this host far better and
        # keeps a refresh from silently losing a handful of players.
        if attempt >= 2:
            try:
                return _curl_json(url, headers, timeout)
            except Exception as err:  # noqa: BLE001
                last_error = err
                continue
        conn = None
        try:
            conn = http.client.HTTPSConnection(parsed.netloc, timeout=timeout, context=SSL_CONTEXT)
            conn.request("GET", path, headers=request_headers)
            resp = conn.getresponse()
            if resp.status == 404:
                raise FileNotFoundError(path)
            if resp.status >= 400:
                raise urllib.error.HTTPError(url, resp.status, resp.reason, resp.headers, None)
            chunks = []
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                chunks.append(chunk)
            return json.loads(b"".join(chunks).decode("utf-8", "replace"))
        except FileNotFoundError:
            raise
        except urllib.error.HTTPError:
            raise
        except Exception as err:  # noqa: BLE001 — transient network failures
            last_error = err
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:  # noqa: BLE001
                    pass
    raise last_error if last_error else RuntimeError("unreachable")


def _curl_json(url: str, headers: dict[str, str], timeout: float) -> object:
    """Fetch JSON through curl, used as a fallback when urllib truncates."""
    import subprocess

    args = ["curl", "-sS", "--fail", "--max-time", str(int(timeout)),
            "--compressed", "-H", "Accept-Encoding: gzip"]
    for key, value in headers.items():
        args += ["-H", f"{key}: {value}"]
    args.append(url)
    result = subprocess.run(args, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"curl exited {result.returncode}: {result.stderr.decode()[:120]}")
    return json.loads(result.stdout.decode("utf-8", "replace"))


def api_get(
    path: str,
    params: dict | None = None,
    *,
    retries: int = 4,
    timeout: float = 45.0,
) -> object | None:
    """
    GET a path on the official API.

    Returns ``None`` for a 404 (the pipeline treats a missing record as an
    expected condition) and raises :class:`ApiError` after exhausting retries.
    """
    url = API + path
    if params:
        clean = {k: v for k, v in params.items() if v not in (None, "")}
        if clean:
            url += "?" + urllib.parse.urlencode(clean)

    headers = {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.wtatennis.com",
        "Referer": "https://www.wtatennis.com/",
    }

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        if attempt:
            time.sleep(0.4 * (2 ** (attempt - 1)) + random.random() * 0.25)
        with _slots:
            _throttle()
            try:
                return _fetch_json(url, headers, timeout)
            except urllib.error.HTTPError as err:
                if err.code == 404:
                    return None
                last_error = err
            except Exception as err:  # noqa: BLE001 — network errors vary widely
                last_error = err
    raise ApiError(f"GET {path} failed after {retries + 1} attempts: {last_error}")


# ---------------------------------------------------------------------------
# Data endpoints
# ---------------------------------------------------------------------------


def fetch_singles_rankings(max_rows: int = 300, at: str | None = None) -> list[dict]:
    """Official WTA singles ranking table. The API caps a page at 100 rows."""
    out: list[dict] = []
    page = 0
    while len(out) < max_rows:
        chunk = api_get(
            "/players/ranked",
            {
                "page": page,
                "pageSize": 100,
                "type": "rankSingles",
                "sort": "asc",
                "metric": "SINGLES",
                "at": at,
            },
        )
        if not isinstance(chunk, list) or not chunk:
            break
        out.extend(chunk)
        if len(chunk) < 100:
            break
        page += 1
    return out[:max_rows]


def fetch_doubles_rankings(max_rows: int = 100, at: str | None = None) -> list[dict]:
    out: list[dict] = []
    page = 0
    while len(out) < max_rows:
        chunk = api_get(
            "/players/ranked",
            {
                "page": page,
                "pageSize": 100,
                "type": "rankDoubles",
                "sort": "asc",
                "metric": "DOUBLES",
                "at": at,
            },
        )
        if not isinstance(chunk, list) or not chunk:
            break
        out.extend(chunk)
        if len(chunk) < 100:
            break
        page += 1
    return out[:max_rows]


def fetch_player_detailed(player_id: int) -> dict | None:
    return api_get(f"/players/{player_id}/detailed")


def fetch_player_season(player_id: int, year: int) -> dict | None:
    return api_get(f"/players/{player_id}/year/{year}")


def fetch_player_ranking_history(player_id: int, params: dict | None = None) -> dict | None:
    return api_get(f"/players/{player_id}/ranking", params or {})


def fetch_player_matches(player_id: int, params: dict | None = None) -> dict | None:
    return api_get(f"/players/{player_id}/matches", {"page": 0, "pageSize": 100, **(params or {})})


def fetch_head_to_head(a: int, b: int) -> dict | None:
    return api_get(f"/players/{a}/headtohead/{b}")


def fetch_tournaments(params: dict | None = None) -> dict | None:
    return api_get("/tournaments", params or {})


def fetch_event_matches(group_id: int, year: int) -> dict | None:
    return api_get(f"/tournaments/{group_id}/{year}/matches", {"page": 0, "pageSize": 500})


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------


def read_json(name: str, default=None):
    """Read a snapshot from ``data/``."""
    path = DATA_DIR / name
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(rel_path: str, value, *, indent: int | None = None) -> Path:
    """
    Write a snapshot and report its size.

    ``separators`` matches Node's ``JSON.stringify`` so the Python pipeline
    produces the same bytes as the implementation it replaces.
    """
    path = ROOT / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    if indent is None:
        body = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    else:
        body = json.dumps(value, ensure_ascii=False, indent=indent)
    path.write_text(body + "\n", encoding="utf-8")
    print(f"  ✓ {rel_path}  ({len(body.encode()) / 1024:.1f} KB)")
    return path


def log(step: str, message: str) -> None:
    print(f"\n[{step}] {message}", flush=True)


def run_pool(items: list, worker, *, workers: int = 4, label: str | None = None, every: int = 25) -> None:
    """
    Run ``worker(item)`` over ``items`` with bounded concurrency.

    Failures are reported and skipped rather than aborting the whole run, since a
    single missing player record should not fail a refresh.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(worker, item): item for item in items}
        for future in as_completed(futures):
            item = futures[future]
            try:
                future.result()
            except Exception as err:  # noqa: BLE001
                name = item.get("name", item) if isinstance(item, dict) else item
                print(f"  ! {name}: {err}", file=sys.stderr, flush=True)
            done += 1
            if label and every and done % every == 0:
                print(f"[{label}] {done}/{len(items)}…", flush=True)


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
