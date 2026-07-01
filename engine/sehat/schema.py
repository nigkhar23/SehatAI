"""Canonical internal schema — THE SWAP POINT (audit must-fix #5).

The Feature, Scoring, Decision, Explainability and UI layers read ONLY these
Pydantic models. Both `MockSource` (Round 1) and `SandboxSource` (Round 2) map
their raw, source-specific shapes INTO these canonical models. A Jul-22 sandbox
schema surprise is therefore contained in ONE mapping function, not rippled
through the engine. That containment is the entire R1->R2 thesis.

Shapes are based on PUBLISHED specs so the mock matches the real ecosystem:
  * bank txns / DEPOSIT  -> Sahamati / Account Aggregator FI schema
  * gst_returns          -> GSTR-1 / GSTR-3B fields
  * epfo                 -> EPFO ECR (Electronic Challan-cum-Return)
  * consent              -> ReBIT consent artefact

Nothing here decides anything — these are pure data containers with light,
declarative validation. All scoring logic lives downstream.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, computed_field


# ---------------------------------------------------------------------------
# Enums — controlled vocabularies shared across sources.
# ---------------------------------------------------------------------------
class TxnType(str, Enum):
    CREDIT = "credit"
    DEBIT = "debit"


class Channel(str, Enum):
    UPI = "UPI"
    NEFT = "NEFT"
    RTGS = "RTGS"
    IMPS = "IMPS"
    CHEQUE = "CHEQUE"
    CASH = "CASH"
    ACH = "ACH"          # mandates / recurring auto-debits
    OTHER = "OTHER"


class TxnCategory(str, Enum):
    SALES = "sales"
    PURCHASE = "purchase"
    SALARY = "salary"
    RENT = "rent"
    UTILITIES = "utilities"
    LOAN_EMI = "loan_emi"        # observed recurring fixed debit, NOT parsed from free text
    TAX = "tax"
    DRAWINGS = "drawings"
    BOUNCE = "bounce"            # returned/failed payment marker
    OTHER = "other"


class GSTReturnType(str, Enum):
    GSTR1 = "GSTR-1"
    GSTR3B = "GSTR-3B"


class FilerCadence(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"      # QRMP / composition — different due dates


class RegType(str, Enum):
    """MSME constitution. Drives the drawings allowance and bureau expectation."""
    PROPRIETORSHIP = "proprietorship"
    PARTNERSHIP = "partnership"
    PVT_LTD = "pvt_ltd"
    LLP = "llp"
    NTC = "NTC"                  # new-to-credit umbrella tag used by the bank


class FIType(str, Enum):
    """Financial Information types in an AA consent artefact."""
    DEPOSIT = "DEPOSIT"
    GST_RETURNS = "GST_RETURNS"
    UPI = "UPI"
    EPFO = "EPFO"


class ProxyType(str, Enum):
    """Operational-proxy meters — physical-world activity signals for thin-file MSMEs.

    The Track-03 owner named these explicitly (electricity for a manufacturer; water
    / fuel for trading & logistics) as alternate data to read when the tax/UPI file is
    too thin to price. One generic `type` field covers every meter through a single
    downstream mechanism — add a member to ingest a new proxy without touching scoring.
    """
    ELECTRICITY = "electricity"
    WATER = "water"
    FUEL = "fuel"


# ---------------------------------------------------------------------------
# Core canonical records.
# ---------------------------------------------------------------------------
class CanonicalEntity(BaseModel):
    """The MSME being assessed."""
    id: str
    name: str
    sector: str = "general"
    state: str = "NA"
    reg_type: RegType = RegType.PROPRIETORSHIP
    gst_registered: bool = True
    udyam_vintage_months: int = Field(0, ge=0)


class CanonicalTxn(BaseModel):
    """One bank/AA statement line (Sahamati DEPOSIT-FI shape, canonicalised)."""
    date: date
    amount: float = Field(..., gt=0)             # always positive; direction is `type`
    type: TxnType
    balance_after: Optional[float] = None
    counterparty_id: Optional[str] = None
    counterparty: Optional[str] = None
    channel: Channel = Channel.OTHER
    category: TxnCategory = TxnCategory.OTHER
    narration: str = ""

    @computed_field  # type: ignore[misc]
    @property
    def signed_amount(self) -> float:
        return self.amount if self.type == TxnType.CREDIT else -self.amount


class CanonicalGSTReturn(BaseModel):
    """One GST return (GSTR-1/3B fields). `tax_paid` is the real signal, not just filing."""
    period: str                                   # "YYYY-MM"
    return_type: GSTReturnType = GSTReturnType.GSTR3B
    filer_cadence: FilerCadence = FilerCadence.MONTHLY
    turnover: float = Field(..., ge=0)
    tax_paid: float = Field(0.0, ge=0)
    is_nil: bool = False
    filed_on: Optional[date] = None
    due_on: Optional[date] = None

    @computed_field  # type: ignore[misc]
    @property
    def filed_on_time(self) -> Optional[bool]:
        if self.filed_on is None or self.due_on is None:
            return None
        return self.filed_on <= self.due_on


class CanonicalUPIMonth(BaseModel):
    """Monthly UPI aggregate (matches the bank's `upi_patterns` dataset shape)."""
    period: str                                   # "YYYY-MM"
    inflow_count: int = Field(0, ge=0)
    inflow_amount: float = Field(0.0, ge=0)
    outflow_count: int = Field(0, ge=0)
    outflow_amount: float = Field(0.0, ge=0)
    unique_payers: int = Field(0, ge=0)
    unique_payees: int = Field(0, ge=0)
    top1_payer_share: float = Field(0.0, ge=0, le=1)
    top3_payer_share: float = Field(0.0, ge=0, le=1)
    peak_day_share: float = Field(0.0, ge=0, le=1)


class CanonicalEPFO(BaseModel):
    """EPFO ECR-derived. `available=False` => sub-threshold micro MSME => NEUTRAL."""
    available: bool = False
    active: bool = False
    employee_count: int = Field(0, ge=0)
    monthly_contribution: float = Field(0.0, ge=0)
    since: Optional[str] = None                   # "YYYY-MM"


class ProxyPoint(BaseModel):
    """One period's reading of an operational meter."""
    period: str                                   # "YYYY-MM"
    value: float = Field(..., ge=0)               # consumption in the meter's `unit`


class OperationalProxy(BaseModel):
    """A monthly operational-meter series (electricity/water/fuel consumption).

    A SUPPLEMENTARY, presence-gated signal: physical-world activity that corroborates
    a thin tax/UPI file. Steady electricity says a manufacturer is still running at
    capacity; a sharp drop says a possible slowdown (the Track-03 owner's exact XAI
    example). It is NEVER a primary source and NEVER a model feature — see scoring.py
    and model_features.py. Absent => the downstream component simply never fires.
    """
    type: ProxyType
    unit: str = "kWh"                             # display unit (kWh / kL / L)
    series: list[ProxyPoint] = Field(default_factory=list)


class ConsentArtefact(BaseModel):
    """ReBIT-style consent. The engine refuses to score without a valid unexpired one."""
    consent_id: str
    consent_start: date
    consent_expiry: date
    fi_types: list[FIType]
    purpose_code: str = "101"
    purpose_text: str = "credit assessment"
    fetch_type: str = "PERIODIC"
    data_life_unit: str = "MONTH"
    data_life_value: int = 3
    consent_mode: str = "STORE"

    def is_valid_on(self, as_of: date) -> bool:
        return self.consent_start <= as_of <= self.consent_expiry

    def covers(self, required: list[FIType]) -> list[FIType]:
        """Return the required FI types NOT covered by this consent (empty == ok)."""
        granted = set(self.fi_types)
        return [t for t in required if t not in granted]


class BureauRecord(BaseModel):
    """Proprietor-level bureau/hygiene — the HARD-GATE inputs (mocked in R1).

    A thin FIRM file does not imply a thin PROPRIETOR file: most proprietors have
    a personal CIBIL record even when the business is credit-invisible. The gate
    reads this, not the firm's absence of a file.
    """
    bureau_file: bool = False                     # does a bureau record exist at all?
    cibil: Optional[int] = Field(None, ge=300, le=900)
    sma_status: Optional[int] = Field(None, ge=0, le=2)   # SMA-0/1/2; None == none
    recent_writeoff: bool = False
    settlement: bool = False
    willful_defaulter: bool = False
    enquiries_6m: int = Field(0, ge=0)


class LatentLabel(BaseModel):
    """Generator-only ground truth. NEVER shown on the card; drives validation.

    `true_propensity` is the hidden repayment propensity that drives BOTH the
    observable features (with noise) AND the seeded default label. Present only
    on synthetic records; absent on real applicants.
    """
    true_propensity: float = Field(..., ge=0, le=1)
    defaulted_12m: bool


class CanonicalRecord(BaseModel):
    """The complete canonical input for one entity — everything downstream reads.

    Optional sections (epfo, upi, bureau) being absent is a first-class state the
    sufficiency gate and missing-data policy handle explicitly; absence is never
    silently treated as a zero.
    """
    entity: CanonicalEntity
    consent: Optional[ConsentArtefact] = None
    txns: list[CanonicalTxn] = Field(default_factory=list)
    gst_returns: list[CanonicalGSTReturn] = Field(default_factory=list)
    upi: list[CanonicalUPIMonth] = Field(default_factory=list)
    epfo: Optional[CanonicalEPFO] = None
    bureau: Optional[BureauRecord] = None
    # Supplementary operational meters (electricity/water/fuel). Empty for nearly every
    # entity; present only on thin-file cases where physical activity corroborates a thin
    # tax/UPI file. Presence-gated downstream — an empty list scores byte-identically to
    # the field's absence (it never enters any sub-score component or model feature).
    operational_proxy: list[OperationalProxy] = Field(default_factory=list)
    # Present on synthetic cohort rows only; stripped before anything customer-facing.
    label: Optional[LatentLabel] = None

    @computed_field  # type: ignore[misc]
    @property
    def txn_months(self) -> int:
        """Distinct YYYY-MM buckets present in the txn history."""
        return len({(t.date.year, t.date.month) for t in self.txns})

    def for_scoring(self) -> "CanonicalRecord":
        """Return a copy with the latent label stripped — defence in depth so the
        label can never leak into features, scoring, or the audit record."""
        return self.model_copy(update={"label": None})
