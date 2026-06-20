from young_stock.methodology import load_builtin_methodology


class FailingSession:
    def __init__(self):
        self.calls = []

    def get(self, url, timeout):
        self.calls.append((url, timeout))
        raise AssertionError("built-in methodology must not use the network")


def test_load_builtin_methodology_returns_young_guidance(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    session = FailingSession()

    result = load_builtin_methodology(session=session)

    assert result.updated is False
    assert result.version.startswith("young-")
    assert result.path.parent.name == "young-stock-cli"
    assert result.path.exists()
    assert "young-stock-cli 内置研究框架" in result.text
    assert "固定顺序" in result.text
    assert session.calls == []


def test_load_builtin_methodology_rewrites_legacy_external_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    legacy = tmp_path / "methodologies" / ("stock" + "-analysis")
    legacy.mkdir(parents=True)
    (legacy / "SKILL.md").write_text("# external\n", encoding="utf-8")

    result = load_builtin_methodology()

    assert result.path.parent.name == "young-stock-cli"
    assert "stock" + "-analysis" not in str(result.path)
    assert "young-stock-cli 内置研究框架" in result.path.read_text(encoding="utf-8")
