"""Sehat — deterministic, validated, governed MSME Financial Health Card engine.

IDBI Innovate 2026, Track 03. The score and the credit decision are 100%
deterministic, rule/stat-based and auditable; the LLM only narrates canonical
reason codes, never decides. See CLAUDE.md and docs/ for the full charter.
"""

from sehat.config import SCORECARD_VERSION

__all__ = ["SCORECARD_VERSION"]
