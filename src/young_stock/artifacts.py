"""Report artifact paths and persistence."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .local_store import young_home


def market_session(now: datetime | None = None) -> str:
    now = now or datetime.now()
    minute = now.hour * 60 + now.minute
    if 9 * 60 <= minute < 9 * 60 + 30:
        return "早盘"
    if 11 * 60 + 30 <= minute < 13 * 60:
        return "午间"
    if 9 * 60 + 30 <= minute < 11 * 60 + 30 or 13 * 60 <= minute < 15 * 60:
        return "盘中"
    return "盘后"


@dataclass(frozen=True)
class ReportIdentity:
    trade_date: str
    session: str
    topic: str

    @property
    def prefix(self) -> str:
        safe_topic = "".join(character for character in self.topic if character.isalnum() or character in "-_")
        return f"{self.trade_date}-{self.session}-{safe_topic}"


@dataclass
class ReportArtifacts:
    trade_date: str

    def __post_init__(self) -> None:
        if len(self.trade_date) != 8 or not self.trade_date.isdigit():
            raise ValueError("trade_date must use YYYYMMDD")

    @property
    def directory(self) -> Path:
        path = young_home() / "reports" / self.trade_date
        path.mkdir(parents=True, exist_ok=True)
        return path

    def path(self, name: str, suffix: str) -> Path:
        safe = "".join(character for character in name if character.isalnum() or character in "-_")
        if not safe:
            raise ValueError("artifact name is empty")
        return self.directory / f"{safe}.{suffix.lstrip('.')}"

    def write_markdown(self, name: str, content: str) -> Path:
        path = self.path(name, "md")
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
        return path

    def write_report_markdown(self, identity: ReportIdentity, content: str) -> Path:
        return self.write_markdown(identity.prefix, content)

    def write_json(self, name: str, data: dict[str, Any]) -> Path:
        path = self.path(name, "json")
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    @classmethod
    def latest_markdown(cls, trade_date: str | None = None) -> Path | None:
        reports = young_home() / "reports"
        if trade_date:
            candidates = list((reports / trade_date).glob("*.md"))
        else:
            candidates = list(reports.glob("*/*.md"))
        identified = [
            path
            for path in candidates
            if re.match(r"^\d{8}-(?:早盘|盘中|午间|盘后)-.+\.md$", path.name)
        ]
        if identified:
            candidates = identified
        return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None

    @classmethod
    def latest_date(cls) -> str | None:
        reports = young_home() / "reports"
        dates = [
            path.name
            for path in reports.iterdir()
            if path.is_dir() and len(path.name) == 8 and path.name.isdigit()
        ] if reports.exists() else []
        return max(dates) if dates else None

    def write_metadata(self, data: dict[str, Any]) -> Path:
        payload = {"created_at": datetime.now().isoformat(timespec="seconds"), **data}
        return self.write_json("metadata", payload)
