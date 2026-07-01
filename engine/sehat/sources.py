"""DataSource adapter seam — the R1->R2 swap point in code form.

`DataSource` is the abstract contract: given an entity id, return a
`CanonicalRecord`. `MockSource` (Round 1) serves pre-generated synthetic records.
`SandboxSource` (Round 2) will map real AA/GST sandbox payloads INTO the same
canonical models via an async consent state-machine — stubbed here so the shape
of the Round-2 work is visible and bounded.

The engine NEVER imports a concrete source directly; it depends on the abstract
`DataSource`. Swapping R1->R2 is constructing a different subclass.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

from sehat.schema import CanonicalRecord


class DataSource(ABC):
    """Abstract data source. Returns canonical records, nothing source-specific."""

    @abstractmethod
    def fetch(self, entity_id: str) -> CanonicalRecord:
        """Return the canonical record for one entity (raises KeyError if absent)."""

    @abstractmethod
    def list_ids(self) -> list[str]:
        """Return all available entity ids."""


class MockSource(DataSource):
    """Round-1 source: serves the pre-generated synthetic cohort from disk.

    The cohort is generated once by `scripts/generate_cohort.py` into a JSONL
    file (one CanonicalRecord per line). Persona records live in a separate dir
    so their inputs stay FROZEN — never regenerated, never tuned to fix a score.
    """

    def __init__(self, records_path: str | Path):
        self.records_path = Path(records_path)
        self._cache: dict[str, CanonicalRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.records_path.exists():
            raise FileNotFoundError(
                f"Cohort file {self.records_path} not found. "
                "Run `python scripts/generate_cohort.py` first."
            )
        with self.records_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = CanonicalRecord.model_validate_json(line)
                self._cache[rec.entity.id] = rec

    def fetch(self, entity_id: str) -> CanonicalRecord:
        return self._cache[entity_id]

    def list_ids(self) -> list[str]:
        return list(self._cache.keys())

    def all_records(self) -> list[CanonicalRecord]:
        return list(self._cache.values())


class PersonaSource(MockSource):
    """Loads frozen demo personas from a directory of one-record JSON files."""

    def __init__(self, persona_dir: str | Path):
        self.persona_dir = Path(persona_dir)
        self._cache = {}
        for path in sorted(self.persona_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            rec = CanonicalRecord.model_validate(data["record"] if "record" in data else data)
            self._cache[rec.entity.id] = rec
        # bypass MockSource._load (no JSONL); cache is populated directly above

    def _load(self) -> None:  # pragma: no cover - intentionally disabled
        pass


class SandboxSource(DataSource):  # pragma: no cover - Round 2 stub
    """Round-2 source: maps real sandbox payloads into canonical models.

    Designed as an async AA consent state-machine from day one (NOT a synchronous
    GET): request consent handle -> poll for consent id -> FIP data fetch ->
    map into CanonicalRecord. Filled in during the Jul 22-31 sandbox window; the
    canonical mapping is the only new code, by design.
    """

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "SandboxSource is wired in Round 2 (Jul 22-31). The R1 engine runs on "
            "MockSource; the swap is constructing this subclass against the same "
            "CanonicalRecord contract."
        )

    def fetch(self, entity_id: str) -> CanonicalRecord:
        raise NotImplementedError

    def list_ids(self) -> list[str]:
        raise NotImplementedError
