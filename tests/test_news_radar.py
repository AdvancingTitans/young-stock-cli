import json
import threading
from pathlib import Path

from young_stock.net.client import ManagedHttpClient
from young_stock.net.policy import DomainPolicy
from young_stock.news_radar import (
    NewsRadar,
    build_news_evidence,
    load_news_sources,
    select_news_sources,
)


class Response:
    def __init__(self, status_code=200, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.content = text.encode("utf-8")
        self.headers = headers or {}


class RecordingSession:
    def __init__(self, responses, delay=0.0):
        self.responses = list(responses)
        self.calls = []
        self.delay = delay
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def request(self, method, url, **kwargs):
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            if self.delay:
                threading.Event().wait(self.delay)
            self.calls.append((method, url, kwargs))
            return self.responses.pop(0)
        finally:
            with self.lock:
                self.active -= 1


def _rss(title="Fed holds rates", link="https://example.com/a?utm_source=x", pub_date="Wed, 08 Jul 2026 01:02:03 GMT"):
    return f"""<?xml version="1.0"?>
<rss><channel>
  <item>
    <title>{title}</title>
    <link>{link}</link>
    <pubDate>{pub_date}</pubDate>
    <description>Policy makers held rates steady.</description>
  </item>
</channel></rss>"""


def test_news_source_catalog_has_required_governance_fields():
    sources = load_news_sources()

    assert sources
    for source in sources:
        assert source.name
        assert source.url.startswith(("http://", "https://"))
        assert source.track
        assert source.country_or_language
        assert isinstance(source.default_enabled, bool)
        assert isinstance(source.may_need_proxy, bool)
        assert source.health_status in {"healthy", "degraded", "unknown", "disabled"}


def test_default_daily_sources_are_macro_global_and_holding_industries_only():
    sources = load_news_sources()

    selected = select_news_sources(
        sources,
        mode="daily",
        profile={"industries": ["semiconductor"], "stocks": ["NVDA"]},
        rich_source=False,
    )
    selected_tracks = {source.track for source in selected}

    assert {"macro", "global_market", "semiconductor"} <= selected_tracks
    assert "crypto" not in selected_tracks
    assert len(select_news_sources(sources, mode="daily", profile={}, rich_source=True)) > len(selected)


def test_daily_includes_holding_industry_sources_even_when_not_broadly_default():
    sources = load_news_sources()

    selected = select_news_sources(
        sources,
        mode="daily",
        profile={"industries": ["ai"]},
        rich_source=False,
    )

    assert "ai" in {source.track for source in selected}
    assert "crypto" not in {source.track for source in selected}


def test_deduplicates_canonical_links_and_aggregates_similar_titles():
    evidence = build_news_evidence(
        [
            {
                "source": "reuters",
                "source_name": "Reuters",
                "track": "macro",
                "title": "Fed holds rates, signals possible cuts",
                "url": "https://news.example.com/story?id=1&utm_source=rss#comments",
                "published": "2026-07-08T01:00:00Z",
                "content": "The Federal Reserve held rates steady.",
            },
            {
                "source": "reuters",
                "source_name": "Reuters",
                "track": "macro",
                "title": "Fed holds rates, signals possible cuts",
                "url": "https://news.example.com/story?id=1",
                "published": "2026-07-08T01:05:00Z",
                "content": "Duplicate syndicated copy.",
            },
            {
                "source": "bloomberg",
                "source_name": "Bloomberg",
                "track": "macro",
                "title": "Fed holds rates and signals possible cuts",
                "url": "https://bloomberg.example.com/fed-cuts",
                "published": "2026-07-08T01:04:00Z",
                "content": "A second outlet reported the same policy event.",
            },
        ],
        mode="daily",
        profile={"industries": []},
    )

    assert evidence["raw_count"] == 3
    assert evidence["cleaned_count"] == 2
    assert evidence["duplicate_link_count"] == 1
    assert len(evidence["events"]) == 1
    assert evidence["events"][0]["source_count"] == 2
    assert evidence["events"][0]["sources"] == ["Bloomberg", "Reuters"]


def test_fetch_uses_etag_last_modified_and_reuses_cache_on_304(tmp_path):
    session = RecordingSession(
        [
            Response(200, _rss(), headers={"ETag": '"abc"', "Last-Modified": "Wed, 08 Jul 2026 01:03:00 GMT"}),
            Response(304, "", headers={}),
        ]
    )
    client = ManagedHttpClient(session=session, max_attempts=1)
    radar = NewsRadar(cache_dir=tmp_path, client=client)
    source = load_news_sources()[0]
    source = source.__class__(
        id="test",
        name="Test RSS",
        url="https://example.com/feed.xml",
        track="macro",
        country_or_language="en",
        default_enabled=True,
        may_need_proxy=False,
        health_status="unknown",
    )

    first = radar.fetch_source(source)
    second = radar.fetch_source(source)

    assert first.status == "ok"
    assert second.status == "not_modified"
    assert second.from_cache is True
    assert second.items[0]["title"] == "Fed holds rates"
    assert session.calls[1][2]["headers"]["If-None-Match"] == '"abc"'
    assert session.calls[1][2]["headers"]["If-Modified-Since"] == "Wed, 08 Jul 2026 01:03:00 GMT"


def test_news_fetch_respects_per_domain_limit(tmp_path):
    session = RecordingSession([Response(200, _rss("A")), Response(200, _rss("B"))], delay=0.05)
    client = ManagedHttpClient(
        session=session,
        policies={"example.com": DomainPolicy(domain_group="example", max_concurrency=1)},
        max_attempts=1,
    )
    radar = NewsRadar(cache_dir=tmp_path, client=client, global_concurrency=2)
    cls = load_news_sources()[0].__class__
    sources = [
        cls("a", "A", "https://example.com/a.xml", "macro", "en", True, False, "unknown"),
        cls("b", "B", "https://example.com/b.xml", "macro", "en", True, False, "unknown"),
    ]

    radar.fetch_sources(sources)

    assert session.max_active == 1


def test_time_parse_failure_and_missing_content_are_marked_not_filled_in():
    evidence = build_news_evidence(
        [
            {
                "source": "mystery",
                "source_name": "Mystery Feed",
                "track": "global_market",
                "title": "Global markets react to unclear report",
                "url": "https://example.com/unclear",
                "published": "not-a-date",
                "content": "",
            }
        ],
        mode="daily",
        profile={},
    )

    item = evidence["events"][0]["items"][0]
    assert item["time_status"] == "parse_failed"
    assert item["content_status"] == "missing"
    assert item["published_at"] is None


def test_stock_news_keeps_company_industry_supply_chain_and_explicit_macro_only():
    evidence = build_news_evidence(
        [
            {"source": "a", "source_name": "A", "track": "company", "title": "NVIDIA announces new GPU", "url": "https://a/1", "published": "2026-07-08T01:00:00Z", "content": "NVIDIA product news."},
            {"source": "b", "source_name": "B", "track": "semiconductor", "title": "Semiconductor equipment orders rise", "url": "https://b/2", "published": "2026-07-08T01:00:00Z", "content": "Industry demand."},
            {"source": "c", "source_name": "C", "track": "supply_chain", "title": "TSMC expands advanced packaging", "url": "https://c/3", "published": "2026-07-08T01:00:00Z", "content": "Upstream capacity."},
            {"source": "d", "source_name": "D", "track": "macro", "title": "Fed rates weigh on semiconductor capex", "url": "https://d/4", "published": "2026-07-08T01:00:00Z", "content": "Macro event explicitly tied to the industry."},
            {"source": "e", "source_name": "E", "track": "macro", "title": "Oil shipping rates move higher", "url": "https://e/5", "published": "2026-07-08T01:00:00Z", "content": "Unrelated macro item."},
        ],
        mode="stock",
        stock_context={
            "company_keywords": ["NVIDIA"],
            "industry_keywords": ["semiconductor"],
            "upstream_keywords": ["TSMC"],
            "downstream_keywords": ["cloud capex"],
        },
    )

    titles = {event["title"] for event in evidence["events"]}
    assert "NVIDIA announces new GPU" in titles
    assert "Semiconductor equipment orders rise" in titles
    assert "TSMC expands advanced packaging" in titles
    assert "Fed rates weigh on semiconductor capex" in titles
    assert "Oil shipping rates move higher" not in titles


def test_news_evidence_respects_length_cap():
    evidence = build_news_evidence(
        [
            {
                "source": f"s{i}",
                "source_name": f"S{i}",
                "track": "macro",
                "title": f"Important macro event number {i}",
                "url": f"https://example.com/{i}",
                "published": "2026-07-08T01:00:00Z",
                "content": "Very long body " * 20,
            }
            for i in range(20)
        ],
        mode="daily",
        profile={},
        max_chars=240,
    )

    assert evidence["truncated"] is True
    assert len(json.dumps(evidence["compressed"], ensure_ascii=False)) <= 240


def test_news_cache_is_written_atomically(tmp_path):
    session = RecordingSession([Response(200, _rss())])
    radar = NewsRadar(cache_dir=tmp_path, client=ManagedHttpClient(session=session, max_attempts=1))
    cls = load_news_sources()[0].__class__
    source = cls("atomic", "Atomic", "https://example.com/a.xml", "macro", "en", True, False, "unknown")

    radar.fetch_source(source)

    cache_files = list(Path(tmp_path).rglob("*.json"))
    assert cache_files
    assert not list(Path(tmp_path).rglob("*.tmp"))
