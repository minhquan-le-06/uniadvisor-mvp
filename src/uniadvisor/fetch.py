"""Polite, cached HTTP client for public admission pages.

- obeys robots.txt (a disallowed URL raises instead of being fetched)
- waits between requests to the same host
- caches every response on disk (data/raw/<host>/<key>.body + .meta.json), so re-runs
  and rebuilds never hit the site again unless refresh=True
- stores only public, aggregate admission data (cutoffs, tuition, score histograms), never
  per-candidate records
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.robotparser
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import httpx

from uniadvisor.paths import RAW

USER_AGENT = "Mozilla/5.0 (compatible; uniadvisor-student-project; non-commercial research)"


class BlockedByRobots(RuntimeError):
    pass


@dataclass
class Response:
    url: str
    status: int
    text: str
    fetched_at: str
    from_cache: bool

    def json(self):  # noqa: ANN201
        return json.loads(self.text)


class PoliteClient:
    def __init__(self, cache_dir: Path = RAW, delay: float = 1.5, refresh: bool = False, timeout: float = 40.0):
        self.cache_dir = cache_dir
        self.delay = delay
        self.refresh = refresh
        self._last: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept-Language": "vi,en;q=0.8"},
            follow_redirects=True,
            timeout=httpx.Timeout(timeout, connect=20.0),
        )
        self.requests_made = 0

    # ---- robots.txt -------------------------------------------------------
    def _robots_for(self, url: str) -> urllib.robotparser.RobotFileParser:
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.client.get(base + "/robots.txt")
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except httpx.HTTPError:
                rp.parse([])
            self._robots[base] = rp
        return self._robots[base]

    def allowed(self, url: str) -> bool:
        return self._robots_for(url).can_fetch(USER_AGENT, url)

    # ---- cache ------------------------------------------------------------
    def _key(self, url: str, params: dict | None) -> Path:
        full = url + ("?" + urlencode(sorted((params or {}).items())) if params else "")
        h = hashlib.sha1(full.encode("utf-8")).hexdigest()[:20]
        return self.cache_dir / urlsplit(url).netloc / h

    def get(self, url: str, params: dict | None = None, headers: dict | None = None) -> Response:
        key = self._key(url, params)
        body, meta = key.with_suffix(".body"), key.with_suffix(".meta.json")
        if not self.refresh and body.exists() and meta.exists():
            m = json.loads(meta.read_text(encoding="utf-8"))
            return Response(m["url"], m["status"], body.read_text(encoding="utf-8"), m["fetched_at"], True)

        full = url + ("?" + urlencode(params) if params else "")
        if not self.allowed(full):
            raise BlockedByRobots(full)
        host = urlsplit(url).netloc
        wait = self.delay - (time.monotonic() - self._last.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        last_err: Exception | None = None
        for attempt in range(4):
            try:
                r = self.client.get(url, params=params, headers=headers)
                self._last[host] = time.monotonic()
                self.requests_made += 1
                if r.status_code in (429, 500, 502, 503, 504):
                    time.sleep(2 ** (attempt + 1))
                    continue
                break
            except httpx.HTTPError as e:  # network hiccup: back off and retry
                last_err = e
                time.sleep(2 ** (attempt + 1))
        else:
            raise RuntimeError(f"failed to fetch {full}: {last_err}")

        fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        key.parent.mkdir(parents=True, exist_ok=True)
        if r.status_code == 200:
            body.write_text(r.text, encoding="utf-8")
            meta.write_text(json.dumps({"url": str(r.url), "status": r.status_code, "fetched_at": fetched_at}), encoding="utf-8")
        return Response(str(r.url), r.status_code, r.text, fetched_at, False)
