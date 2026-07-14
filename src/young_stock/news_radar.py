"""RSS/Atom news radar with governance, dedupe, event aggregation and evidence compression."""

from __future__ import annotations

import email.utils
import html
import json
import os
import re
import tempfile
import time
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import timezone
from importlib import resources
from pathlib import Path
from typing import Any

from .health import SourceHealthBook
from .net.client import CircuitOpenError, ManagedHttpClient

DEFAULT_MAX_EVIDENCE_CHARS = 6000
DEFAULT_GLOBAL_CONCURRENCY = 6
_TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "spm"}
_EVENT_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "for",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "可能",
    "宣布",
    "最新",
    "报道",
}
_DEFAULT_DAILY_TRACKS = {"macro", "global_market"}
_STOCK_DIRECT_TRACKS = {"company", "industry", "supply_chain", "upstream", "downstream"}


@dataclass(frozen=True)
class NewsSource:
    id: str
    name: str
    url: str
    track: str
    country_or_language: str
    default_enabled: bool
    may_need_proxy: bool
    health_status: str


@dataclass
class FetchResult:
    source: NewsSource
    status: str
    items: list[dict[str, Any]]
    error: str | None = None
    from_cache: bool = False
    etag: str | None = None
    last_modified: str | None = None
    health: dict[str, Any] | None = None


def load_news_sources(path: str | Path | None = None) -> list[NewsSource]:
    if path is None:
        raw = resources.files("young_stock").joinpath("data/news_sources.json").read_text(encoding="utf-8")
    else:
        raw = Path(path).read_text(encoding="utf-8")
    rows = json.loads(raw)
    return [NewsSource(**row) for row in rows]


def select_news_sources(
    sources: list[NewsSource],
    *,
    mode: str,
    profile: dict[str, Any] | None = None,
    rich_source: bool = False,
    stock_context: dict[str, Any] | None = None,
) -> list[NewsSource]:
    if rich_source:
        return [source for source in sources if source.health_status != "disabled"]
    available = [source for source in sources if source.health_status != "disabled"]
    default_enabled = [source for source in available if source.default_enabled]
    if mode == "stock":
        keywords = _keyword_set(stock_context or {})
        tracks = set(_STOCK_DIRECT_TRACKS)
        tracks.update(_normalize_token(keyword) for keyword in keywords)
        tracks.add("macro")
        return [
            source
            for source in available
            if source.track in tracks or _normalize_token(source.track) in tracks
        ]
    profile_tracks = _profile_tracks(profile or {})
    allowed = set(_DEFAULT_DAILY_TRACKS) | {track for track in profile_tracks if track}
    return [
        source
        for source in available
        if (_normalize_token(source.track) in _DEFAULT_DAILY_TRACKS and source in default_enabled)
        or _normalize_token(source.track) in allowed - _DEFAULT_DAILY_TRACKS
    ]


class NewsRadar:
    def __init__(
        self,
        *,
        cache_dir: str | Path,
        client: ManagedHttpClient | None = None,
        global_concurrency: int = DEFAULT_GLOBAL_CONCURRENCY,
        health: SourceHealthBook | None = None,
        clock=time,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.client = client or ManagedHttpClient(timeout=10.0, max_attempts=3)
        self.global_concurrency = max(1, int(global_concurrency or 1))
        self.health = health or SourceHealthBook()
        self.clock = clock

    def fetch_sources(self, sources: list[NewsSource]) -> list[FetchResult]:
        if not sources:
            return []
        results: list[FetchResult] = []
        with ThreadPoolExecutor(max_workers=min(self.global_concurrency, len(sources))) as executor:
            futures = [executor.submit(self.fetch_source, source) for source in sources]
            for future in as_completed(futures):
                results.append(future.result())
        return results

    def fetch_source(self, source: NewsSource) -> FetchResult:
        started = self.clock.monotonic()
        cached = self._load_source_cache(source)
        headers: dict[str, str] = {
            "User-Agent": "young-stock-cli/0.3 news radar",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.1",
        }
        if cached.get("etag"):
            headers["If-None-Match"] = str(cached["etag"])
        if cached.get("last_modified"):
            headers["If-Modified-Since"] = str(cached["last_modified"])
        try:
            response = self.client.request("GET", source.url, headers=headers)
        except CircuitOpenError as exc:
            return self._finish(source, "circuit_open", [], started, error=str(exc))
        except Exception as exc:
            return self._finish(source, "error", [], started, error=str(exc))

        if response.status_code == 304:
            return self._finish(
                source,
                "not_modified",
                list(cached.get("items") or []),
                started,
                from_cache=True,
                etag=cached.get("etag"),
                last_modified=cached.get("last_modified"),
            )
        if response.status_code >= 400:
            return self._finish(source, f"http_{response.status_code}", [], started, error=response.text[:200])

        items = _parse_feed(response.text, source)
        etag = response.headers.get("ETag")
        last_modified = response.headers.get("Last-Modified")
        self._save_source_cache(source, {"etag": etag, "last_modified": last_modified, "items": items})
        return self._finish(source, "ok", items, started, etag=etag, last_modified=last_modified)

    def _finish(
        self,
        source: NewsSource,
        status: str,
        items: list[dict[str, Any]],
        started: float,
        *,
        error: str | None = None,
        from_cache: bool = False,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> FetchResult:
        ok = status in {"ok", "not_modified"}
        self.health.record(source.id, ok=ok, latency_ms=(self.clock.monotonic() - started) * 1000)
        return FetchResult(
            source=source,
            status=status,
            items=items,
            error=error,
            from_cache=from_cache,
            etag=etag,
            last_modified=last_modified,
            health=asdict(self.health.snapshot(source.id)),
        )

    def _cache_path(self, source: NewsSource) -> Path:
        return self.cache_dir / "news_radar" / f"{_safe_name(source.id)}.json"

    def _load_source_cache(self, source: NewsSource) -> dict[str, Any]:
        try:
            return json.loads(self._cache_path(source).read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_source_cache(self, source: NewsSource, payload: dict[str, Any]) -> None:
        path = self._cache_path(source)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                json.dump(payload, tmp, ensure_ascii=False)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_name, path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def build_news_evidence(
    raw_items: list[dict[str, Any]],
    *,
    mode: str,
    profile: dict[str, Any] | None = None,
    stock_context: dict[str, Any] | None = None,
    rich_source: bool = False,
    max_chars: int = DEFAULT_MAX_EVIDENCE_CHARS,
) -> dict[str, Any]:
    cleaned, duplicate_links = _clean_and_dedupe_links(raw_items)
    filtered = _filter_items(cleaned, mode=mode, profile=profile or {}, stock_context=stock_context or {}, rich_source=rich_source)
    events = _aggregate_events(filtered)
    compressed, truncated = _compress_events(events, max_chars=max_chars)
    return {
        "raw_count": len(raw_items),
        "cleaned_count": len(cleaned),
        "relevant_count": len(filtered),
        "duplicate_link_count": duplicate_links,
        "event_count": len(events),
        "events": events,
        "compressed": compressed,
        "truncated": truncated,
        "pipeline": ["raw", "clean", "dedupe", "aggregate_events", "relevance_filter", "compress_evidence"],
    }


def _parse_feed(text: str, source: NewsSource) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    items = root.findall(".//item")
    if items:
        return [_rss_item_to_dict(item, source) for item in items]
    entries = [element for element in root.iter() if _local_name(element.tag) == "entry"]
    return [_atom_entry_to_dict(entry, source) for entry in entries]


def _rss_item_to_dict(item: ET.Element, source: NewsSource) -> dict[str, Any]:
    return {
        "source": source.id,
        "source_name": source.name,
        "track": source.track,
        "title": _clean_text(_child_text(item, "title")),
        "url": _clean_text(_child_text(item, "link")),
        "published": _clean_text(_child_text(item, "pubDate") or _child_text(item, "date")),
        "content": _clean_html(_child_text(item, "description") or _child_text(item, "encoded")),
    }


def _atom_entry_to_dict(entry: ET.Element, source: NewsSource) -> dict[str, Any]:
    link = ""
    for child in entry:
        if _local_name(child.tag) == "link":
            link = child.attrib.get("href") or (child.text or "")
            if link:
                break
    return {
        "source": source.id,
        "source_name": source.name,
        "track": source.track,
        "title": _clean_text(_child_text(entry, "title")),
        "url": _clean_text(link),
        "published": _clean_text(_child_text(entry, "updated") or _child_text(entry, "published")),
        "content": _clean_html(_child_text(entry, "summary") or _child_text(entry, "content")),
    }


def _clean_and_dedupe_links(raw_items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    duplicates = 0
    for raw in raw_items:
        title = _clean_text(raw.get("title"))
        url = _canonical_url(raw.get("url") or raw.get("link"))
        if not title and not url:
            continue
        dedupe_key = url or f"title:{_title_key(title)}"
        if dedupe_key in seen:
            duplicates += 1
            continue
        seen.add(dedupe_key)
        published_at, time_status = _parse_time(raw.get("published") or raw.get("published_at") or raw.get("time"))
        content = _clean_html(raw.get("content") or raw.get("summary") or raw.get("description"))
        source_name = _clean_text(raw.get("source_name") or raw.get("source"))
        result.append(
            {
                "source": _clean_text(raw.get("source")),
                "source_name": source_name,
                "source_status": "ok" if source_name else "unconfirmed",
                "track": _normalize_token(raw.get("track") or "unknown"),
                "title": title,
                "url": url,
                "published_at": published_at,
                "time_status": time_status,
                "content_status": "ok" if content else "missing",
                "content": content,
            }
        )
    return result, duplicates


def _filter_items(
    items: list[dict[str, Any]],
    *,
    mode: str,
    profile: dict[str, Any],
    stock_context: dict[str, Any],
    rich_source: bool,
) -> list[dict[str, Any]]:
    if rich_source:
        return items
    if mode == "stock":
        direct_keywords = _keyword_set(stock_context)
        macro_keywords = direct_keywords
        kept = []
        for item in items:
            track = _normalize_token(item.get("track"))
            text = _search_text(item)
            if track in _STOCK_DIRECT_TRACKS and (not direct_keywords or _contains_any(text, direct_keywords)):
                kept.append(item)
            elif track == "macro" and _contains_any(text, macro_keywords):
                kept.append(item)
            elif _contains_any(text, direct_keywords):
                kept.append(item)
        return kept
    allowed = set(_DEFAULT_DAILY_TRACKS)
    allowed.update(_normalize_token(value) for value in _list_values(profile.get("industries")))
    allowed.update(_normalize_token(value) for value in _list_values(profile.get("themes")))
    return [item for item in items if _normalize_token(item.get("track")) in allowed]


def _aggregate_events(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda row: str(row.get("published_at") or ""), reverse=True):
        target = None
        item_tokens = _title_tokens(item.get("title"))
        for event in events:
            if _similar_tokens(item_tokens, event["_tokens"]):
                target = event
                break
        if target is None:
            target = {"title": item.get("title") or "未命名资讯", "_tokens": item_tokens, "items": []}
            events.append(target)
        target["items"].append(_public_item(item))
    for event in events:
        sources = sorted({item["source_name"] for item in event["items"] if item.get("source_name")})
        event["sources"] = sources
        event["source_count"] = len(sources)
        event["latest_published_at"] = max((str(item.get("published_at") or "") for item in event["items"]), default="") or None
        del event["_tokens"]
    return events


def _compress_events(events: list[dict[str, Any]], *, max_chars: int) -> tuple[dict[str, Any], bool]:
    compressed: dict[str, Any] = {"events": []}
    truncated = False
    for event in events:
        summary = {
            "title": event["title"],
            "sources": event["sources"],
            "latest_published_at": event["latest_published_at"],
            "items": [
                {
                    "url": item.get("url"),
                    "time_status": item.get("time_status"),
                    "content_status": item.get("content_status"),
                    "source_status": item.get("source_status"),
                }
                for item in event["items"][:3]
            ],
        }
        candidate = {"events": [*compressed["events"], summary]}
        if len(json.dumps(candidate, ensure_ascii=False)) > max_chars:
            truncated = True
            break
        compressed = candidate
    return compressed, truncated or len(compressed["events"]) < len(events)


def _public_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item.get(key)
        for key in (
            "source",
            "source_name",
            "source_status",
            "track",
            "title",
            "url",
            "published_at",
            "time_status",
            "content_status",
        )
    }


def _canonical_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return raw
    query = []
    for key, val in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
        lower = key.lower()
        if lower.startswith("utm_") or lower in _TRACKING_PARAMS:
            continue
        query.append((key, val))
    path = parsed.path.rstrip("/") or "/"
    return urllib.parse.urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            urllib.parse.urlencode(sorted(query)),
            "",
        )
    )


def _parse_time(value: Any) -> tuple[str | None, str]:
    text = str(value or "").strip()
    if not text:
        return None, "missing"
    try:
        parsed = email.utils.parsedate_to_datetime(text)
        if parsed is None:
            raise ValueError(text)
    except Exception:
        try:
            parsed = __import__("datetime").datetime.fromisoformat(text.replace("Z", "+00:00"))
        except Exception:
            return None, "parse_failed"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"), "ok"


def _keyword_set(values: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for key in ("company_keywords", "industry_keywords", "upstream_keywords", "downstream_keywords", "keywords"):
        result.update(str(value).lower() for value in _list_values(values.get(key)) if str(value).strip())
    return result


def _profile_tracks(profile: dict[str, Any]) -> set[str]:
    tracks = {_normalize_token(value) for value in _list_values(profile.get("industries"))}
    tracks.update(_normalize_token(value) for value in _list_values(profile.get("themes")))
    classifications = profile.get("classifications", {})
    stock_classes = classifications.get("stocks", {}) if isinstance(classifications, dict) else {}
    if isinstance(stock_classes, dict):
        for item in stock_classes.values():
            if not isinstance(item, dict):
                continue
            for key in ("category", "style", "asset_type"):
                tracks.update(_normalize_token(value) for value in _list_values(item.get(key)))
            tracks.update(_normalize_token(value) for value in _list_values(item.get("evidence")))
    expanded = set(tracks)
    for track in tracks:
        expanded.update(part for part in track.split() if part)
    return {track for track in expanded if track}


def _contains_any(text: str, keywords: set[str]) -> bool:
    if not keywords:
        return False
    lowered = text.lower()
    return any(keyword and keyword in lowered for keyword in keywords)


def _search_text(item: dict[str, Any]) -> str:
    return " ".join(str(item.get(key) or "") for key in ("title", "content", "track")).lower()


def _list_values(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _title_key(title: str) -> str:
    return " ".join(sorted(_title_tokens(title)))


def _title_tokens(title: Any) -> set[str]:
    text = _normalize_token(title)
    return {token for token in text.split() if token and token not in _EVENT_STOPWORDS}


def _similar_tokens(left: set[str], right: set[str]) -> bool:
    if not left or not right:
        return False
    overlap = len(left & right)
    return overlap / max(len(left), len(right)) >= 0.72


def _normalize_token(value: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\u4e00-\u9fff]+", " ", str(value or "").lower())).strip()


def _clean_text(value: Any) -> str:
    return html.unescape(re.sub(r"\s+", " ", str(value or "").strip()))


def _clean_html(value: Any) -> str:
    return _clean_text(re.sub(r"<[^>]+>", " ", str(value or "")))


def _child_text(element: ET.Element, name: str) -> str:
    for child in element.iter():
        if _local_name(child.tag) == name:
            return child.text or ""
    return ""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _safe_name(value: str) -> str:
    return re.sub(r"[^\w.-]", "_", value or "_")
