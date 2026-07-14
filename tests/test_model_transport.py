import json
import os
import stat
import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner

from young_stock.cli import cli
from young_stock.config import load_config, save_config
from young_stock.llm import LLMError, LLMNotConfigured
from young_stock.model_transport.registry import model_transport_for_config, transport_ids
from young_stock.reports import generate_llm_daily_report


def _fake_cli(tmp_path: Path, name: str = "codex") -> Path:
    executable = tmp_path / name
    executable.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json
            import os
            import signal
            import sys
            import time

            if "--version" in sys.argv or "--help" in sys.argv:
                if os.environ.get("FAKE_VERSION_FAIL"):
                    print("broken version", file=sys.stderr)
                    sys.exit(2)
                print("fake-cli 1.0")
                sys.exit(0)

            marker = os.environ.get("FAKE_MARKER")
            if marker:
                with open(marker, "w", encoding="utf-8") as handle:
                    json.dump({"cwd": os.getcwd(), "argv": sys.argv}, handle)

            if os.environ.get("FAKE_SLEEP"):
                def _term(_signum, _frame):
                    term_marker = os.environ.get("FAKE_TERM_MARKER")
                    if term_marker:
                        Path = __import__("pathlib").Path
                        Path(term_marker).write_text("terminated", encoding="utf-8")
                    sys.exit(143)
                signal.signal(signal.SIGTERM, _term)
                while True:
                    time.sleep(1)

            prompt = sys.stdin.read()
            if os.environ.get("FAKE_NOT_LOGGED_IN"):
                print("not logged in: run auth login", file=sys.stderr)
                sys.exit(1)
            if os.environ.get("FAKE_NONZERO"):
                print("boom stderr diagnostic", file=sys.stderr)
                sys.exit(7)
            if os.environ.get("FAKE_EMPTY"):
                sys.exit(0)
            if os.environ.get("FAKE_STDERR"):
                print("minor stderr diagnostic", file=sys.stderr)
            print("transport ok")
            print(prompt.splitlines()[-1] if prompt.strip() else "")
            """
        ),
        encoding="utf-8",
    )
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    return executable


def test_transport_registry_defaults_old_config_to_api(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    save_config({"schema_version": 1, "llm": {"provider": "deepseek", "model": "deepseek-chat"}})

    config = load_config()["llm"]

    assert load_config()["schema_version"] == 2
    assert config["transport"] == "api"
    assert type(model_transport_for_config(config)).__name__ == "ApiTransport"
    assert "api" in transport_ids()
    assert "subscription-cli" in transport_ids()


def test_cli_config_models_can_persist_subscription_cli_transport(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))

    result = CliRunner().invoke(
        cli,
        [
            "config",
            "models",
            "--transport",
            "subscription-cli",
            "--provider",
            "codex",
            "--model",
            "gpt-5",
        ],
    )

    assert result.exit_code == 0
    assert "transport=subscription-cli" in result.output
    llm = load_config()["llm"]
    assert llm["transport"] == "subscription-cli"
    assert llm["provider"] == "codex"
    assert llm["model"] == "gpt-5"
    assert "api_key" not in llm


def test_subscription_cli_transport_success_uses_temp_cwd_and_cleans_up(monkeypatch, tmp_path):
    fake = _fake_cli(tmp_path)
    marker = tmp_path / "marker.json"
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_MARKER", str(marker))
    transport = model_transport_for_config(
        {"transport": "subscription-cli", "provider": "codex", "model": "test-model", "timeout": 5}
    )

    result = transport.chat([{"role": "user", "content": "Evidence and Prompt are ready"}])

    assert result.content.startswith("transport ok")
    assert result.transport == "subscription-cli"
    assert result.provider == "codex"
    assert result.model == "test-model"
    recorded = json.loads(marker.read_text(encoding="utf-8"))
    assert Path(recorded["cwd"]).name.startswith("young-model-")
    assert not Path(recorded["cwd"]).exists()
    assert "--dangerously-bypass-approvals-and-sandbox" not in recorded["argv"]
    assert fake.name in recorded["argv"][0]


def test_subscription_cli_transport_rejects_missing_or_unverifiable_cli(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    transport = model_transport_for_config({"transport": "subscription-cli", "provider": "codex", "model": "test"})

    with pytest.raises(LLMNotConfigured, match="未安装|无法验证"):
        transport.chat([{"role": "user", "content": "hi"}])

    _fake_cli(tmp_path)
    monkeypatch.setenv("FAKE_VERSION_FAIL", "1")
    with pytest.raises(LLMNotConfigured, match="无法验证"):
        transport.chat([{"role": "user", "content": "hi"}])


def test_subscription_cli_transport_surfaces_login_failure_and_stderr(monkeypatch, tmp_path):
    _fake_cli(tmp_path)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ.get('PATH', '')}")
    transport = model_transport_for_config({"transport": "subscription-cli", "provider": "codex", "model": "test"})

    monkeypatch.setenv("FAKE_NOT_LOGGED_IN", "1")
    with pytest.raises(LLMNotConfigured) as login_error:
        transport.chat([{"role": "user", "content": "hi"}])
    assert "登录" in str(login_error.value)
    assert "not logged in" in str(login_error.value)

    monkeypatch.delenv("FAKE_NOT_LOGGED_IN")
    monkeypatch.setenv("FAKE_NONZERO", "1")
    with pytest.raises(LLMError) as nonzero_error:
        transport.chat([{"role": "user", "content": "hi"}])
    assert "exit code 7" in str(nonzero_error.value)
    assert "boom stderr diagnostic" in str(nonzero_error.value)


def test_subscription_cli_transport_handles_empty_output_stderr_and_timeout(monkeypatch, tmp_path):
    _fake_cli(tmp_path)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ.get('PATH', '')}")
    transport = model_transport_for_config({"transport": "subscription-cli", "provider": "codex", "model": "test", "timeout": 1})

    monkeypatch.setenv("FAKE_STDERR", "1")
    result = transport.chat([{"role": "user", "content": "hi"}])
    assert result.content

    monkeypatch.delenv("FAKE_STDERR")
    monkeypatch.setenv("FAKE_EMPTY", "1")
    with pytest.raises(LLMError, match="空"):
        transport.chat([{"role": "user", "content": "hi"}])

    monkeypatch.delenv("FAKE_EMPTY")
    term_marker = tmp_path / "terminated.txt"
    monkeypatch.setenv("FAKE_SLEEP", "1")
    monkeypatch.setenv("FAKE_TERM_MARKER", str(term_marker))
    with pytest.raises(LLMError, match="超时"):
        transport.chat([{"role": "user", "content": "hi"}])
    assert term_marker.read_text(encoding="utf-8") == "terminated"


def test_llm_report_metadata_records_transport_provider_and_model(monkeypatch):
    monkeypatch.setattr(
        "young_stock.reports.review_investment_output",
        lambda markdown, evidence: {"structured_candidate": False},
    )

    class FakeTransport:
        def chat(self, messages):
            return type(
                "Result",
                (),
                {
                    "content": "# 深度复盘\n\n==结构性偏强==\n\n证据、风险、行动建议、观察清单齐备。",
                    "provider": "codex",
                    "model": "test-model",
                    "transport": "subscription-cli",
                    "usage": {},
                },
            )()

    evidence = {
        "_meta": {"trade_date": "20260618", "quality_score": 85, "missing_modules": []},
        "modules": {"M1": {"available": True}},
    }

    _, metadata = generate_llm_daily_report(evidence, FakeTransport())

    assert metadata["transport"] == "subscription-cli"
    assert metadata["provider"] == "codex"
    assert metadata["model"] == "test-model"
