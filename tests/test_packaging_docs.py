import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READMES = sorted(ROOT.glob("README*.md"))
DOCS = [*READMES, ROOT / "CHANGELOG.md", *sorted((ROOT / "docs").rglob("*.md"))]
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
    english = (ROOT / "README.md").read_text(encoding="utf-8")
    chinese = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")

    for phrase in (
        "young-stock-cli 0.3.16",
        "uv tool install young-stock-cli",
        "uv tool install --upgrade young-stock-cli",
        "uv tool install --force 'young-stock-cli'",
        "uv tool install --upgrade 'young-stock-cli[pdf]'",
        "uv tool install --force '.[pdf]'",
        "python3 -m pip install --upgrade young-stock-cli",
        "python3 -m pip install --upgrade 'young-stock-cli[pdf]'",
        "young init",
        "young daily --format summary",
        "young daily --llm --lens all --debate-rounds 3",
        "young report",
        "young send",
        "young send --dry-run",
        "young send --yes",
        "young stock <symbol>",
        "young lhb <symbol>",
        "young fund <code>",
        "young flow",
        "young config models",
        "young config models --provider ollama --model llama3.1 --api-base http://localhost:11434/v1",
        "young config providers",
        "subscription-cli",
        "young config channel add|list|remove",
        "young diagnose --json",
        "young profile add-stock 600519 --buy-date 2026-01-15 --quantity 100",
        "young portfolio create core",
        "young memory show|list|clear|reset",
        "young style set <name>",
        "young chat",
        "/daily [--llm] [--lens ...]",
        "/stock <symbol> [--llm] [--lens ...]",
        "/fund <code> [--llm] [--lens ...]",
        "young stock <symbol> --llm",
        "young daily --llm",
        "young config models ... --fallback-model X --fallback-model Y",
        "/style list|set|show|clear",
        "docs/images/cover.png",
        "docs/images/demo-indices.png",
        "docs/images/demo-zt-pool.png",
        "requested_date",
        "as_of",
        "read-only",
    ):
        assert phrase in english
        assert phrase in chinese

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
        assert lens in english
        assert lens in chinese

    for card in (
        "DCF-lite",
        "Reverse DCF",
        "Comps",
        "IC Memo",
        "Due Diligence checklist",
        "VCP",
        "Rebalancing Review",
    ):
        assert card in english
        assert card in chinese

    for removed in (
        "young profile group create",
        "young profile group add",
        "稳健型",
        "成长型",
        "style：默认只给 `待观察`",
    ):
        assert removed not in english
        assert removed not in chinese

    assert "Quiet personal research cockpit for the terminal." in english
    assert "终端里的个人投研驾驶舱" in chinese
    assert "README.zh-CN.md" in english
    assert "README.md" in chinese


def test_english_readme_has_no_mixed_chinese_body_copy():
    english = (ROOT / "README.md").read_text(encoding="utf-8")
    body = "\n".join(
        line for line in english.splitlines() if "img.shields.io/badge/README-" not in line
    )

    assert not re.search(r"[\u3400-\u9fff]", body)


def test_changelog_is_short_and_current():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    for phrase in (
        "[0.3.16] - 2026-07-15",
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
    assert 'pdf = ["weasyprint>=62"]' in pyproject
    assert '"weasyprint>=62"' in pyproject


def test_ci_covers_python_39():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert '"3.9"' in ci


def test_source_avoids_python_310_only_zip_strict():
    source = (ROOT / "src" / "young_stock" / "_core.py").read_text(encoding="utf-8")

    assert "strict=False" not in source
