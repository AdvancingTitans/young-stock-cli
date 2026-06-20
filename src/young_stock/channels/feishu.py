"""Feishu webhook and App delivery adapters."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

from .base import DeliveryResult

FEISHU_BASE = "https://open.feishu.cn/open-apis"


class FeishuChannel:
    def __init__(self, name: str, config: dict[str, Any], *, session: Any = None):
        self.name = name
        self.config = config
        self.session = session or requests.Session()

    def _post(self, url: str, **kwargs: Any) -> dict[str, Any]:
        for attempt in range(3):
            try:
                response = self.session.post(url, timeout=20, **kwargs)
            except requests.RequestException as exc:
                if attempt < 2:
                    time.sleep(0.25 * (attempt + 1))
                    continue
                raise RuntimeError(f"Feishu network error: {exc.__class__.__name__}") from exc
            if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                time.sleep(0.25 * (attempt + 1))
                continue
            if response.status_code >= 400:
                raise RuntimeError(f"Feishu HTTP {response.status_code}")
            data = response.json()
            if data.get("code", 0) != 0:
                raise RuntimeError(f"Feishu API code {data.get('code')}")
            return data
        raise RuntimeError("Feishu request retries exhausted")

    def _preview(self, markdown: Path, pdf: Path | None, token: str | None = None) -> None:
        content = markdown.read_text(encoding="utf-8")[:3000]
        if pdf is None:
            delivery_note = "未检测到同名 PDF，本次仅发送 Markdown 摘要。"
        elif token:
            delivery_note = "同名 PDF 已检测到，将随后的文件消息一并发送。"
        else:
            delivery_note = "同名 PDF 已检测到，但 webhook 不支持附件上传。"
        text = f"{markdown.stem}\n\n{content}\n\n{delivery_note}"
        if token:
            self._send_message("text", {"text": text}, token)
        else:
            self._post(
                str(self.config["webhook"]),
                json={"msg_type": "text", "content": {"text": text}},
            )

    def _token(self) -> str:
        configured = str(self.config.get("tenant_access_token") or "")
        if configured:
            return configured
        data = self._post(
            f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": self.config["app_id"], "app_secret": self.config["app_secret"]},
        )
        token = str(data.get("tenant_access_token") or "")
        if not token:
            raise RuntimeError("Feishu token response missing tenant_access_token")
        return token

    def _upload(self, path: Path, token: str) -> str:
        with path.open("rb") as handle:
            data = self._post(
                f"{FEISHU_BASE}/im/v1/files",
                headers={"Authorization": f"Bearer {token}"},
                data={"file_type": "stream", "file_name": path.name},
                files={"file": (path.name, handle)},
            )
        key = str((data.get("data") or {}).get("file_key") or "")
        if not key:
            raise RuntimeError("Feishu upload response missing file_key")
        return key

    def _send_message(self, msg_type: str, content: dict[str, Any], token: str) -> None:
        receive_type = str(self.config.get("receive_id_type") or "chat_id")
        self._post(
            f"{FEISHU_BASE}/im/v1/messages?receive_id_type={receive_type}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "receive_id": self.config["receive_id"],
                "msg_type": msg_type,
                "content": json.dumps(content, ensure_ascii=False),
            },
        )

    def send(self, markdown: Path, pdf: Path | None) -> DeliveryResult:
        try:
            if self.config.get("webhook"):
                self._preview(markdown, pdf)
                if pdf is None:
                    detail = "已发送 Markdown 摘要；未检测到同名 PDF。"
                else:
                    detail = "已发送 Markdown 摘要；检测到同名 PDF，但 webhook 不支持附件上传。"
                return DeliveryResult("feishu", self.name, True, detail)
            token = self._token()
            self._preview(markdown, pdf, token)
            self._send_message("file", {"file_key": self._upload(markdown, token)}, token)
            if pdf is not None:
                self._send_message("file", {"file_key": self._upload(pdf, token)}, token)
                detail = "Markdown 与 PDF 已上传并发送。"
            else:
                detail = "Markdown 已上传并发送；未检测到同名 PDF。"
            return DeliveryResult("feishu", self.name, True, detail)
        except Exception as exc:
            return DeliveryResult("feishu", self.name, False, str(exc))
