"""FastAPI app — the HTTP surface the deployed card and portfolio view consume.

Endpoints (all GET, read-only — the demo serves frozen personas):
  GET /                  -> liveness + version banner
  GET /personas          -> list of demo personas (id, name, tagline, headline)
  GET /assess/{id}       -> full Explanation for one persona (card payload)
  GET /portfolio         -> book-level rollup (persona summary + cohort band stats)
  GET /validation        -> the held-out validation report (the spine slide)

Hard rules baked in (from the audit):
  * ZERO live LLM calls. Narration is read from the frozen persona JSON's
    `narration.by_code` cache and RE-GROUNDED against live values in explain.py;
    anything stale falls back to its deterministic template. The app never imports
    an Anthropic client.
  * The engine never calls Date.now(); a fixed assessment timestamp is used so a
    persona's card is byte-stable across requests.
  * Every assessment is appended to an immutable audit log (governance trail).
  * CORS allows the Vercel origin (configurable via SEHAT_CORS_ORIGINS).
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from sehat.audit import AuditLog
from sehat.config import SCORECARD_VERSION
from sehat.engine import assess
from sehat.explain import explain_assessment
from sehat.schema import CanonicalRecord

# The engine never calls Date.now(); pin a stable assessment timestamp so each
# persona's card (and its audit hash) is reproducible request-to-request.
ASSESS_TIMESTAMP = "2026-06-29T00:00:00Z"

ENGINE_DIR = Path(__file__).resolve().parent.parent
PERSONA_DIR = ENGINE_DIR / "personas"
ARTIFACTS_DIR = ENGINE_DIR / "artifacts"
AUDIT_LOG_PATH = Path(os.environ.get("SEHAT_AUDIT_LOG", str(ARTIFACTS_DIR / "audit_log.jsonl")))


# ---------------------------------------------------------------------------
# Persona loading (record + frozen narration cache).
# ---------------------------------------------------------------------------
class _Persona:
    __slots__ = ("id", "key", "name", "tagline", "record", "narration_cache", "model_explain")

    def __init__(self, path: Path):
        data = json.loads(path.read_text(encoding="utf-8"))
        self.record = CanonicalRecord.model_validate(data["record"])
        self.id = self.record.entity.id
        self.key = path.stem                      # e.g. "2_thin_file_hero"
        self.name = self.record.entity.name
        self.tagline = data.get("tagline", "")
        self.narration_cache = (data.get("narration") or {}).get("by_code", {})
        # Frozen champion/challenger/SHAP block (pregenerate_model_explain.py). Absent
        # until the models are trained+frozen; the card then simply omits the cross-check.
        self.model_explain = data.get("model_explain")


@lru_cache(maxsize=1)
def _personas() -> dict[str, _Persona]:
    out: dict[str, _Persona] = {}
    for path in sorted(PERSONA_DIR.glob("*.json")):
        p = _Persona(path)
        out[p.id] = p
    return out


def _load_json_or_none(path: Path) -> Optional[dict]:
    """Read a JSON artifact, returning None on missing OR malformed file so an
    endpoint degrades to 503 instead of 500 if an ops replace corrupts it."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


@lru_cache(maxsize=1)
def _validation_report() -> Optional[dict]:
    return _load_json_or_none(ARTIFACTS_DIR / "validation_report.json")


@lru_cache(maxsize=1)
def _weight_fit() -> Optional[dict]:
    return _load_json_or_none(ARTIFACTS_DIR / "weight_fit.json")


@lru_cache(maxsize=1)
def _model_card() -> Optional[dict]:
    """The hybrid model card: champion vs challenger vs FHS AUC + agreement + IV ranking."""
    return _load_json_or_none(ARTIFACTS_DIR / "model_card.json")


@lru_cache(maxsize=1)
def _segmentation() -> Optional[dict]:
    """Descriptive segmentation of the validation slice (band/bad-rate by sector/state/
    vintage/constitution). Read-only artifact from scripts/segment_cohort.py; None if absent."""
    return _load_json_or_none(ARTIFACTS_DIR / "segmentation_report.json")


@lru_cache(maxsize=16)
def _explain(entity_id: str) -> dict:
    """Assess a persona once, cache the UI-ready explanation, log the audit record.

    NOTE: the returned dict is cached BY REFERENCE. Callers must treat it as
    read-only (extract scalars / build new structures) — never mutate it in place,
    or the mutation persists to the cache and breaks per-request reproducibility.
    All current consumers (list_personas/portfolio) only read.
    """
    persona = _personas().get(entity_id)
    if persona is None:
        raise KeyError(entity_id)
    assessment = assess(persona.record, timestamp=ASSESS_TIMESTAMP)
    try:
        AuditLog(AUDIT_LOG_PATH).append(assessment.audit)
    except OSError:
        pass  # logging is best-effort; never block a response on disk
    explanation = explain_assessment(
        assessment, narration_cache=persona.narration_cache,
        model_explain=persona.model_explain,
    )
    payload = explanation.to_dict()
    # Attach a small entity header + sub-score breakdown the card needs.
    score = assessment.score
    payload["entity"] = {
        "id": persona.id, "key": persona.key, "name": persona.name,
        "sector": persona.record.entity.sector, "state": persona.record.entity.state,
        "reg_type": persona.record.entity.reg_type.value,
        "vintage_months": persona.record.entity.udyam_vintage_months,
        "tagline": persona.tagline,
    }
    payload["subscores"] = [
        {"name": n, "value": round(s.value, 1), "available": s.available,
         "weight": score.effective_weights.get(n, 0.0), "reweighted": s.reweighted}
        for n, s in score.subscores.items()
    ]
    f = assessment.features
    payload["coverage"] = {
        "fraction": round(f.coverage_fraction(), 2),
        "has_txns": f.has_txns,
        "has_gst": f.has_gst,
        "has_upi": f.has_upi,
        "epfo_applicable": f.has_epfo_applicable,
        "txn_months": f.txn_months,
        "gst_returns": f.gst_returns,
        "has_proxy": f.has_proxy,
        "proxy_type": f.proxy_type,
    }
    # Operational-proxy panel data (sparkline + the engine-derived trend/break the
    # reason code is built from). Present only when the entity carries a meter series;
    # null otherwise, so the card simply omits the panel (presence-gated, like the score).
    proxies = persona.record.operational_proxy
    if proxies:
        p0 = proxies[0]
        payload["operational_proxy"] = {
            "type": p0.type.value,
            "unit": p0.unit,
            "series": [{"period": pt.period, "value": pt.value} for pt in p0.series],
            "trend_pct": f.proxy_trend_pct,
            "recent_break_pct": f.proxy_recent_break_pct,
            "recent_window_months": f.proxy_recent_window_months,
        }
    else:
        payload["operational_proxy"] = None
    payload["bureau_thin_file"] = not (
        persona.record.bureau is not None and persona.record.bureau.bureau_file
    )
    payload["scorecard_version"] = SCORECARD_VERSION
    payload["audit"] = {
        "input_hash": assessment.audit.input_hash,
        "record_hash": assessment.audit.record_hash,
        "scorecard_version": assessment.audit.scorecard_version,
        "consent_id": assessment.audit.consent_id,
        "blocking_gate": assessment.audit.blocking_gate,
        "timestamp": assessment.audit.timestamp,
    }
    return payload


# ---------------------------------------------------------------------------
# App.
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Sehat — MSME Financial Health Card",
    version=SCORECARD_VERSION,
    description="Deterministic, validated, governed credit-decisioning engine "
                "for credit-invisible MSMEs (IDBI Innovate 2026, Track 03).",
)

_origins_env = os.environ.get("SEHAT_CORS_ORIGINS", "")
_allow_origins = [o.strip() for o in _origins_env.split(",") if o.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict:
    return {
        "service": "sehat-engine",
        "scorecard_version": SCORECARD_VERSION,
        "personas": len(_personas()),
        "validation_available": _validation_report() is not None,
        "model_card_available": _model_card() is not None,
        "endpoints": ["/personas", "/assess/{id}", "/portfolio", "/validation",
                      "/model_card", "/segmentation"],
    }


@app.get("/personas")
def list_personas() -> dict:
    items = []
    for pid in _personas():
        exp = _explain(pid)
        items.append({
            "id": pid,
            "key": exp["entity"]["key"],
            "name": exp["entity"]["name"],
            "sector": exp["entity"]["sector"],
            "tagline": exp["entity"]["tagline"],
            "fhs": exp["fhs"],
            "band": exp["band"],
            "decision": exp["decision"],
            "indicative_limit": exp["indicative_limit"],
            "thin_file": exp["bureau_thin_file"],
        })
    # Stable order by persona file key (1_, 2_, ...).
    items.sort(key=lambda x: x["key"])
    return {"personas": items, "scorecard_version": SCORECARD_VERSION}


@app.get("/assess/{entity_id}")
def assess_persona(entity_id: str) -> dict:
    try:
        return _explain(entity_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown persona id {entity_id!r}")


@app.get("/validation")
def validation() -> dict:
    report = _validation_report()
    if report is None:
        raise HTTPException(
            status_code=503,
            detail="validation_report.json not found — run scripts/fit_and_validate.py",
        )
    wf = _weight_fit()
    return {"report": report, "weight_fit": wf, "model_card": _model_card(),
            "scorecard_version": SCORECARD_VERSION}


@app.get("/model_card")
def model_card() -> dict:
    """The hybrid model card: champion (WOE+logit) vs challenger (monotone GBM) vs the
    deterministic FHS — AUC, approve-agreement, and the learned Information-Value ranking."""
    mc = _model_card()
    if mc is None:
        raise HTTPException(
            status_code=503,
            detail="model_card.json not found — run scripts/train_models.py",
        )
    return {"model_card": mc, "scorecard_version": SCORECARD_VERSION}


@app.get("/portfolio")
def portfolio() -> dict:
    """Bank-side rollup: the demo personas as a mini-book + the cohort band stats."""
    persona_rows = []
    counts = {"approve": 0, "refer": 0, "decline": 0}
    total_exposure = 0.0
    for pid in _personas():
        exp = _explain(pid)
        counts[exp["decision"]] = counts.get(exp["decision"], 0) + 1
        total_exposure += exp["indicative_limit"]
        persona_rows.append({
            "id": pid, "name": exp["entity"]["name"], "sector": exp["entity"]["sector"],
            "fhs": exp["fhs"], "band": exp["band"], "decision": exp["decision"],
            "indicative_limit": exp["indicative_limit"], "thin_file": exp["bureau_thin_file"],
        })
    persona_rows.sort(key=lambda x: (-x["fhs"]))

    report = _validation_report()
    cohort = None
    if report is not None:
        cohort = {
            "n_test": report.get("n_test"),
            "base_default_rate": report.get("base_default_rate"),
            "auc": report.get("auc"),
            "ks": report.get("ks"),
            "gini": report.get("gini"),
            "bands": report.get("bands"),
            "lift": report.get("lift"),
            "bad_rate_monotone": report.get("bad_rate_monotone"),
        }

    return {
        "demo_book": {
            "personas": persona_rows,
            "decision_counts": counts,
            "total_indicative_exposure": round(total_exposure, 0),
        },
        "cohort": cohort,
        "segmentation": _segmentation(),
        "scorecard_version": SCORECARD_VERSION,
    }


@app.get("/segmentation")
def segmentation() -> dict:
    """The unified score cut by segment (sector/state/vintage/constitution) over the
    same held-out validation slice — descriptive, not a new scored sub-model."""
    seg = _segmentation()
    if seg is None:
        raise HTTPException(
            status_code=503,
            detail="segmentation_report.json not found — run scripts/segment_cohort.py",
        )
    return {"segmentation": seg, "scorecard_version": SCORECARD_VERSION}
