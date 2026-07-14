from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CacheKey:
    schema_version: int
    capability: str
    source: str
    market: str
    symbol: str
    effective_date: str
    parameters: dict[str, Any] = field(default_factory=dict)

    @property
    def normalized_parameters_hash(self) -> str:
        raw = json.dumps(self.parameters or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass
class CacheRecord:
    requested_at: float
    as_of: str
    source: str
    capability: str
    schema_version: int
    stale: bool
    payload: Any


class JsonCacheV2:
    def __init__(self, root: Path | str, *, clock=time):
        self.root = Path(root)
        self.clock = clock

    def path_for(self, key: CacheKey) -> Path:
        return (
            self.root
            / str(key.schema_version)
            / _safe(key.effective_date)
            / _safe(key.capability)
            / f"{_safe(key.source)}_{_safe(key.market)}_{_safe(key.symbol)}_{key.normalized_parameters_hash}.json"
        )

    def load(self, key: CacheKey) -> CacheRecord | None:
        path = self.path_for(key)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if int(data.get("schema_version", -1)) != key.schema_version:
                return None
            if data.get("capability") != key.capability or data.get("source") != key.source:
                return None
            return CacheRecord(
                requested_at=float(data["requested_at"]),
                as_of=str(data["as_of"]),
                source=str(data["source"]),
                capability=str(data["capability"]),
                schema_version=int(data["schema_version"]),
                stale=bool(data["stale"]),
                payload=data.get("payload"),
            )
        except Exception:
            return None

    def save(self, key: CacheKey, record: CacheRecord, *, allow_empty: bool = False) -> bool:
        if not _cacheable_payload(record.payload, allow_empty=allow_empty):
            return False
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(record)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                json.dump(data, tmp, ensure_ascii=False, default=str)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_name, path)
            return True
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            return False

    def save_payload(
        self,
        key: CacheKey,
        payload: Any,
        *,
        source: str,
        as_of: str,
        stale: bool = False,
        allow_empty: bool = False,
    ) -> bool:
        record = CacheRecord(
            requested_at=float(self.clock.time()),
            as_of=as_of,
            source=source,
            capability=key.capability,
            schema_version=key.schema_version,
            stale=stale,
            payload=payload,
        )
        return self.save(key, record, allow_empty=allow_empty)


def _safe(value: str) -> str:
    return re.sub(r"[^\w\-.]", "_", str(value or "_"))


def _cacheable_payload(payload: Any, *, allow_empty: bool) -> bool:
    if isinstance(payload, dict) and payload.get("_error"):
        return False
    if allow_empty:
        return True
    if payload is None:
        return False
    if payload == {} or payload == [] or payload == "":
        return False
    if isinstance(payload, dict) and "data" in payload and payload.get("data") in ({}, [], "", None):
        return False
    return True
