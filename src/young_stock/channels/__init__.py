"""Delivery channel registry."""

from __future__ import annotations

from pathlib import Path

from ..artifacts import ReportArtifacts
from ..config import load_config
from .base import DeliveryResult
from .feishu import FeishuChannel


def send_report(trade_date: str | None, *, channel_name: str | None = None) -> list[DeliveryResult]:
    bundle = ReportArtifacts.latest_delivery_artifacts(trade_date)
    if bundle is None:
        if trade_date:
            raise ValueError(f"{trade_date} 缺少可发送的 Markdown；请先生成对应日报或 LLM Markdown。")
        raise ValueError("未找到可发送的 Markdown；请先生成日报或 LLM Markdown。")
    configs = load_config(strict=False).get("channels", {}).get("feishu", {})
    selected = {
        name: config
        for name, config in configs.items()
        if channel_name is None or name == channel_name
    }
    if not selected:
        raise ValueError("未配置匹配的发送渠道；请运行 `young config channel add feishu --help`。")
    return [FeishuChannel(name, config).send(Path(bundle.markdown), bundle.pdf) for name, config in selected.items()]


__all__ = ["DeliveryResult", "send_report"]
