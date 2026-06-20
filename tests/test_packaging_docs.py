from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_recommends_python_39_safe_install_commands():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Requires Python 3.9+." in readme
    assert "python3 -m pip install young-stock-cli" in readme
    assert "uv tool install young-stock-cli" in readme
    assert "uv tool install --force 'young-stock-cli'" in readme
    assert "young init" in readme
    assert "young config models" in readme
    assert "https://api.moonshot.cn/v1" in readme
    assert "Requires Python 3.10+." not in readme
    assert "```bash\npip3 install young-stock-cli" not in readme


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
