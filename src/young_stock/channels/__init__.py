"""Delivery channel registry."""

from __future__ import annotations

from pathlib import Path

from ..artifacts import ReportArtifacts
from ..config import load_config
from .base import DeliveryResult
from .feishu import FeishuChannel


def send_report(trade_date: str | None, *, channel_name: str | None = None) -> list[DeliveryResult]:
    if not trade_date:
        raise ValueError("没有报告日期；请先运行 `young report`。")
    artifacts = ReportArtifacts(trade_date)
    markdown = ReportArtifacts.latest_markdown(trade_date)
    pdf = artifacts.path("report", "pdf")
    if markdown is None or not pdf.exists():
        raise ValueError(f"{trade_date} 缺少 Markdown/PDF；请先运行 `young report --date {trade_date}`。")
    configs = load_config(strict=False).get("channels", {}).get("feishu", {})
    selected = {
        name: config
        for name, config in configs.items()
        if channel_name is None or name == channel_name
    }
    if not selected:
        raise ValueError("未配置匹配的发送渠道；请运行 `young config channel add feishu --help`。")
    return [FeishuChannel(name, config).send(Path(markdown), pdf) for name, config in selected.items()]


__all__ = ["DeliveryResult", "send_report"]
