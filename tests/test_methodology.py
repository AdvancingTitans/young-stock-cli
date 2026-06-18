import json
from types import SimpleNamespace

from young_stock.methodology import REFERENCE_PATHS, sync_stock_analysis_methodology


class FakeSession:
    def __init__(self, version="4.3.0"):
        self.version = version
        self.urls = []

    def get(self, url, timeout):
        self.urls.append(url)
        if url.endswith("SKILL.md"):
            text = f'---\nname: stock-analysis\nmetadata:\n  version: "{self.version}"\n---\n# 新版规范\n'
        else:
            text = f"# {url.rsplit('/', 1)[-1]}\n\n新版模板内容\n"
        return SimpleNamespace(
            status_code=200,
            text=text,
        )


def test_sync_stock_analysis_methodology_caches_new_remote_version(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    session = FakeSession()

    result = sync_stock_analysis_methodology(session=session)

    assert result.version == "4.3.0"
    assert result.updated is True
    assert result.path.read_text(encoding="utf-8").endswith("# 新版规范\n")
    assert len(session.urls) == 1 + len(REFERENCE_PATHS)
    manifest = json.loads((result.path.parent / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "4.3.0"
    assert set(manifest["sha256"]) == {"SKILL.md", *REFERENCE_PATHS}
    assert "新版模板内容" in result.text


def test_sync_does_not_replace_newer_local_version(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    local = tmp_path / "methodologies" / "stock-analysis"
    local.mkdir(parents=True)
    (local / "SKILL.md").write_text(
        '---\nmetadata:\n  version: "4.4.0"\n---\n# 本地新版\n',
        encoding="utf-8",
    )
    session = FakeSession(version="4.3.0")

    result = sync_stock_analysis_methodology(session=session)

    assert result.version == "4.4.0"
    assert result.updated is False
    assert result.path.read_text(encoding="utf-8").endswith("# 本地新版\n")
    assert len(session.urls) == 1
