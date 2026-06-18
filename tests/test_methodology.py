from types import SimpleNamespace

from young_stock.methodology import sync_stock_analysis_methodology


class FakeSession:
    def get(self, url, timeout):
        return SimpleNamespace(
            status_code=200,
            text='---\nname: stock-analysis\nmetadata:\n  version: "4.3.0"\n---\n# 新版规范\n',
        )


def test_sync_stock_analysis_methodology_caches_new_remote_version(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))

    result = sync_stock_analysis_methodology(session=FakeSession())

    assert result.version == "4.3.0"
    assert result.updated is True
    assert result.path.read_text(encoding="utf-8").endswith("# 新版规范\n")
