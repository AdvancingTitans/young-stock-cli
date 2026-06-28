from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = [ROOT / "README.md", ROOT / "CHANGELOG.md", *sorted((ROOT / "docs").rglob("*.md"))]
FORBIDDEN = (
    "U" + "ZI-Skill",
    "wbh" + "604",
    "stock" + "-analysis",
    "Agent" + "-Reach",
    "Her" + "mes",
    "Code" + "x",
    "Ka" + "mi",
    "Camo" + "fox",
    "tw93/" + "Ka" + "mi",
    "AdvancingTitans/" + "stock" + "-analysis",
    "/Users/",
    "/private/",
)


def _read(*paths: Path) -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in paths if path.exists())


def test_readme_covers_the_current_product_surface():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for phrase in (
        "Quiet personal research cockpit for the terminal.",
        "Requires Python 3.9+.",
        "uv tool install young-stock-cli",
        "uv tool install --upgrade young-stock-cli",
        "uv tool install --force 'young-stock-cli'",
        "python3 -m pip install --upgrade young-stock-cli",
        "young init",
        "young daily --format summary",
        "young daily --llm --lens all --debate-rounds 3",
        "young report",
        "young send",
        "young stock <symbol>",
        "young lhb <symbol>",
        "young fund <code>",
        "young flow",
        "young config models",
        "young config models --provider ollama --model llama3.1",
        "young config models --provider ark --api-base https://ark.cn-beijing.volces.com/api/coding/v3 --api-key-env ARK_API_KEY --model <model-id>",
        'curl -sS "$API_BASE/models"',
        "MODEL_API_KEY",
        "young config channel add|list|remove",
        "young diagnose --json",
        "young profile add-stock 600519 --buy-date 2026-01-15 --quantity 100",
        "自动分类",
        "category / evidence",
        "主题ETF",
        "创业板",
        "young portfolio create core",
        "young memory show|list|clear|reset",
        "young style set <name>",
        "young chat",
        "/daily [--llm] [--lens ...]",
        "/stock <symbol> [--llm] [--lens ...]",
        "/fund <code> [--llm] [--lens ...]",
        "young stock <symbol> 默认确定性数据源",
        "young daily 默认确定性数据源",
        "young stock <symbol> --llm",
        "young daily --llm",
        "只有显式 `--lens` 才会进入 lens",
        "young config models ... --fallback-model X --fallback-model Y",
        "https://api.kimi.com/coding/v1",
        "kimi-for-coding",
        "Kimi Coding Plan",
        "只在限流、额度、瞬时服务错误或明确模型不可用时切换",
        "认证、generic404、api_base 错误不切换",
        "Ark 先用 `--list` 核对 model ID",
        "/style list|set|show|clear",
        "docs/images/cover.png",
        "docs/images/demo-indices.png",
        "docs/images/demo-zt-pool.png",
        "docs/images/repo-overview.png",
    ):
        assert phrase in readme

    for lens in (
        "balanced",
        "buffett",
        "munger",
        "graham",
        "klarman",
        "lynch",
        "o_neil",
        "wood",
        "dalio",
        "soros",
        "livermore",
        "minervini",
        "simons",
        "duan_yongping",
        "zhang_kun",
        "feng_liu",
    ):
        assert lens in readme

    for card in (
        "DCF-lite",
        "Reverse DCF",
        "Comps",
        "IC Memo",
        "Due Diligence checklist",
        "VCP",
        "Rebalancing Review",
    ):
        assert card in readme

    for removed in (
        "young profile group create",
        "young profile group add",
        "稳健型",
        "成长型",
        "style：默认只给 `待观察`",
    ):
        assert removed not in readme


def test_changelog_is_short_and_current():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    for phrase in (
        "[0.3.1] - 2026-06-21",
        "young daily",
        "young config models",
        "--browser-fallback",
        "--rich-source",
        "M1–M7",
    ):
        assert phrase in changelog


def test_repository_docs_are_free_of_forbidden_terms():
    text = _read(*DOCS)

    for term in FORBIDDEN:
        assert term not in text


def test_stale_docs_are_removed():
    assert not (ROOT / "docs" / "promo-copy.md").exists()
    assert not (ROOT / "docs" / "superpowers").exists()


def test_package_version_is_next_patch_release():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    init_py = (ROOT / "src" / "young_stock" / "__init__.py").read_text(encoding="utf-8")

    version = init_py.split('__version__ = "', 1)[1].split('"', 1)[0]

    assert f'version = "{version}"' in pyproject
    assert 'requires-python = ">=3.9"' in pyproject
    assert '"Programming Language :: Python :: 3.9"' in pyproject
    assert version.count(".") == 2


def test_pdf_template_is_declared_as_package_data():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    template = ROOT / "src" / "young_stock" / "templates" / "equity-report.html"

    assert template.exists()
    assert "src/young_stock/templates/*.html" in pyproject
    assert '"weasyprint>=62"' in pyproject


def test_ci_covers_python_39():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert '"3.9"' in ci


def test_source_avoids_python_310_only_zip_strict():
    source = (ROOT / "src" / "young_stock" / "_core.py").read_text(encoding="utf-8")

    assert "strict=False" not in source
