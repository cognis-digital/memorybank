"""Core engine for MEMORYBANK.

Stores memories as newline-delimited JSON (JSONL) in a single file so the bank
is portable and trivially diffable. Retrieval ranks candidates with a hybrid
score combining lexical relevance (token overlap, TF-weighted), importance,
and exponential recency decay — the same shape used by production agent-memory
systems, implemented with nothing but the standard library.
"""
from __future__ import annotations

import json
import math
import os
import re
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Iterable

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_DEFAULT_HALFLIFE_DAYS = 14.0

# Tiny English stopword set so common words don't dominate relevance.
_STOP = frozenset(
    "a an and are as at be but by for from has have if in into is it its of on "
    "or that the their then there these they this to was were will with".split()
)


class MemoryBankError(Exception):
    """Raised for invalid operations against a memory bank."""


def _tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP]


@dataclass
class Memory:
    """A single stored memory."""

    text: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    tags: list[str] = field(default_factory=list)
    importance: float = 1.0
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    access_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Memory":
        return cls(
            text=d["text"],
            id=d.get("id", uuid.uuid4().hex[:12]),
            tags=list(d.get("tags", [])),
            importance=float(d.get("importance", 1.0)),
            created_at=float(d.get("created_at", time.time())),
            accessed_at=float(d.get("accessed_at", time.time())),
            access_count=int(d.get("access_count", 0)),
        )


class MemoryBank:
    """A persistent, rankable store of agent memories backed by a JSONL file."""

    def __init__(self, path: str, halflife_days: float = _DEFAULT_HALFLIFE_DAYS):
        if halflife_days <= 0:
            raise MemoryBankError("halflife_days must be positive")
        self.path = path
        self.halflife_days = halflife_days
        self._memories: dict[str, Memory] = {}
        self._load()

    # ---- persistence ---------------------------------------------------
    def _load(self) -> None:
        self._memories.clear()
        if not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    m = Memory.from_dict(json.loads(line))
                except (json.JSONDecodeError, KeyError) as exc:
                    raise MemoryBankError(
                        f"corrupt memory at {self.path}:{lineno}: {exc}"
                    ) from exc
                self._memories[m.id] = m

    def _save(self) -> None:
        directory = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(directory, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            for m in self._memories.values():
                fh.write(json.dumps(m.to_dict(), sort_keys=True) + "\n")
        os.replace(tmp, self.path)

    # ---- mutations -----------------------------------------------------
    def add(
        self,
        text: str,
        tags: Iterable[str] | None = None,
        importance: float = 1.0,
    ) -> Memory:
        text = (text or "").strip()
        if not text:
            raise MemoryBankError("memory text must not be empty")
        if importance <= 0:
            raise MemoryBankError("importance must be positive")
        m = Memory(text=text, tags=sorted(set(tags or [])), importance=float(importance))
        self._memories[m.id] = m
        self._save()
        return m

    def forget(self, memory_id: str) -> Memory:
        m = self._memories.pop(memory_id, None)
        if m is None:
            raise MemoryBankError(f"no memory with id {memory_id!r}")
        self._save()
        return m

    def all(self) -> list[Memory]:
        return list(self._memories.values())

    # ---- scoring -------------------------------------------------------
    def _recency(self, m: Memory, now: float) -> float:
        age_days = max(0.0, (now - m.accessed_at) / 86400.0)
        return 0.5 ** (age_days / self.halflife_days)

    def _relevance(self, query_tokens: list[str], m: Memory) -> float:
        if not query_tokens:
            return 0.0
        mem_tokens = _tokenize(m.text) + [t.lower() for t in m.tags]
        if not mem_tokens:
            return 0.0
        counts: dict[str, int] = {}
        for t in mem_tokens:
            counts[t] = counts.get(t, 0) + 1
        qset = set(query_tokens)
        overlap = sum(counts[t] for t in qset if t in counts)
        if overlap == 0:
            return 0.0
        # Normalize by query size; dampen long memories via log length.
        norm = len(qset) * math.log1p(len(mem_tokens))
        return overlap / norm if norm else 0.0

    def search(
        self,
        query: str,
        limit: int = 5,
        tag: str | None = None,
        now: float | None = None,
        touch: bool = True,
    ) -> list[dict]:
        """Return the top memories for a query with score breakdowns."""
        if limit <= 0:
            raise MemoryBankError("limit must be positive")
        now = time.time() if now is None else now
        qtokens = _tokenize(query)
        scored: list[tuple[float, dict, Memory]] = []
        for m in self._memories.values():
            if tag is not None and tag not in m.tags:
                continue
            rel = self._relevance(qtokens, m)
            rec = self._recency(m, now)
            imp = math.log1p(m.importance)
            # Hybrid: relevance dominates, recency & importance modulate.
            score = (rel * 2.0) + (rec * 1.0) + (imp * 0.5)
            scored.append(
                (
                    score,
                    {
                        "id": m.id,
                        "text": m.text,
                        "tags": m.tags,
                        "importance": m.importance,
                        "score": round(score, 6),
                        "relevance": round(rel, 6),
                        "recency": round(rec, 6),
                    },
                    m,
                )
            )
        scored.sort(key=lambda x: (x[0], x[2].accessed_at), reverse=True)
        top = scored[:limit]
        if touch and top:
            for _, _, m in top:
                m.accessed_at = now
                m.access_count += 1
            self._save()
        return [row[1] for row in top]

    def stats(self, now: float | None = None) -> dict:
        now = time.time() if now is None else now
        mems = list(self._memories.values())
        tags: dict[str, int] = {}
        for m in mems:
            for t in m.tags:
                tags[t] = tags.get(t, 0) + 1
        return {
            "path": os.path.abspath(self.path),
            "count": len(mems),
            "tags": dict(sorted(tags.items())),
            "total_accesses": sum(m.access_count for m in mems),
            "halflife_days": self.halflife_days,
        }
