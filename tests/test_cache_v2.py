import json

from young_stock.cache_v2 import CacheKey, CacheRecord, JsonCacheV2


class FakeClock:
    def __init__(self):
        self.value = 1000.0

    def time(self):
        return self.value


def test_parameters_change_cache_key(tmp_path):
    cache = JsonCacheV2(tmp_path)
    left = CacheKey(
        schema_version=2,
        capability="board_list",
        source="eastmoney",
        market="cn",
        symbol="BK",
        effective_date="20260708",
        parameters={"limit": 20},
    )
    right = CacheKey(
        schema_version=2,
        capability="board_list",
        source="eastmoney",
        market="cn",
        symbol="BK",
        effective_date="20260708",
        parameters={"limit": 50},
    )

    assert cache.path_for(left) != cache.path_for(right)


def test_atomic_cache_write_leaves_no_temp_file(tmp_path):
    clock = FakeClock()
    cache = JsonCacheV2(tmp_path, clock=clock)
    key = CacheKey(2, "quote", "eastmoney", "cn", "600519", "20260708", {})
    record = CacheRecord(
        requested_at=clock.time(),
        as_of="2026-07-08",
        source="eastmoney",
        capability="quote",
        schema_version=2,
        stale=False,
        payload={"price": 123.4},
    )

    assert cache.save(key, record)

    assert cache.load(key).payload == {"price": 123.4}
    assert list(tmp_path.rglob("*.tmp")) == []


def test_empty_and_error_results_do_not_pollute_cache(tmp_path):
    cache = JsonCacheV2(tmp_path)
    key = CacheKey(2, "quote", "eastmoney", "cn", "600519", "20260708", {})

    assert not cache.save_payload(key, {}, source="eastmoney", as_of="2026-07-08")
    assert cache.load(key) is None
    assert not cache.save_payload(key, {"_error": "blocked"}, source="eastmoney", as_of="2026-07-08")
    assert cache.load(key) is None


def test_declared_empty_result_is_cached(tmp_path):
    cache = JsonCacheV2(tmp_path)
    key = CacheKey(2, "events", "eastmoney", "cn", "600519", "20260708", {})

    assert cache.save_payload(key, [], source="eastmoney", as_of="2026-07-08", allow_empty=True)

    record = cache.load(key)
    assert record is not None
    assert record.payload == []


def test_corrupt_cache_safely_degrades(tmp_path):
    cache = JsonCacheV2(tmp_path)
    key = CacheKey(2, "quote", "eastmoney", "cn", "600519", "20260708", {})
    path = cache.path_for(key)
    path.parent.mkdir(parents=True)
    path.write_text("{broken", encoding="utf-8")

    assert cache.load(key) is None


def test_wrong_effective_date_is_not_returned_as_today(tmp_path):
    cache = JsonCacheV2(tmp_path)
    old_key = CacheKey(2, "quote", "eastmoney", "cn", "600519", "20260707", {})
    today_key = CacheKey(2, "quote", "eastmoney", "cn", "600519", "20260708", {})

    cache.save_payload(old_key, {"price": 120}, source="eastmoney", as_of="2026-07-07")

    assert cache.load(today_key) is None


def test_record_schema_contains_required_fields(tmp_path):
    cache = JsonCacheV2(tmp_path)
    key = CacheKey(2, "quote", "eastmoney", "cn", "600519", "20260708", {"fields": ["price"]})
    cache.save_payload(key, {"price": 123}, source="eastmoney", as_of="2026-07-08")

    data = json.loads(cache.path_for(key).read_text(encoding="utf-8"))

    for field in ("requested_at", "as_of", "source", "capability", "schema_version", "stale", "payload"):
        assert field in data
