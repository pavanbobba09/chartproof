"""Pydantic models for cases, keys, criteria, and API contracts (DATA_SPEC.md)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# Canonical lab / vital names (extend as criteria need them)
CANONICAL_LAB_NAMES: frozenset[str] = frozenset(
    {
        "lactate",
        "creatinine",
        "wbc",
        "platelets",
        "bilirubin",
        "gcs",
    }
)

CANONICAL_VITAL_NAMES: frozenset[str] = frozenset(
    {
        "map",
        "sbp",
        "temp",
        "spo2",
        "fio2",
        "hr",
        "rr",
    }
)

DocType = Literal[
    "history_and_physical",
    "progress_note",
    "nursing_note",
    "discharge_summary",
    "lab_report_narrative",
]

Verdict = Literal["supported", "not_supported"]
PipelineStatus = Literal["completed", "needs_review"]
EvidenceSide = Literal["for", "against"]
CriterionResultKind = Literal["met", "not_met", "unclear"]
AuditSource = Literal["precomputed", "cached", "live"]
Difficulty = Literal["clear", "borderline"]


class EvidenceSpan(BaseModel):
    """Line-range citation into a case document (1-based line numbers)."""

    doc_id: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)

    @model_validator(mode="after")
    def line_end_gte_start(self) -> EvidenceSpan:
        if self.line_end < self.line_start:
            raise ValueError("line_end must be >= line_start")
        return self

    def intersects(self, other: EvidenceSpan) -> bool:
        """True if same document and line ranges overlap (inclusive)."""
        if self.doc_id != other.doc_id:
            return False
        return self.line_start <= other.line_end and other.line_start <= self.line_end


class BilledCodes(BaseModel):
    icd10: list[str]
    drg: str


class Patient(BaseModel):
    age: int = Field(ge=0, le=120)
    sex: Literal["M", "F", "U"]


class Document(BaseModel):
    doc_id: str
    doc_type: DocType
    date: str
    lines: list[str]


class LabValue(BaseModel):
    name: str
    value: float
    unit: str
    datetime: str

    @field_validator("name")
    @classmethod
    def lowercase_name(cls, v: str) -> str:
        return v.lower()


class VitalValue(BaseModel):
    name: str
    value: float
    unit: str
    datetime: str

    @field_validator("name")
    @classmethod
    def lowercase_name(cls, v: str) -> str:
        return v.lower()


class Case(BaseModel):
    case_id: str
    target_dx: str
    billed: BilledCodes
    patient: Patient
    documents: list[Document]
    labs: list[LabValue] = Field(default_factory=list)
    vitals: list[VitalValue] = Field(default_factory=list)

    @model_validator(mode="after")
    def documents_nonempty(self) -> Case:
        if not self.documents:
            raise ValueError("case must have at least one document")
        return self


class PlantedEvidence(BaseModel):
    doc_id: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    side: EvidenceSide
    criterion_id: str

    @model_validator(mode="after")
    def line_end_gte_start(self) -> PlantedEvidence:
        if self.line_end < self.line_start:
            raise ValueError("line_end must be >= line_start")
        return self

    def as_span(self) -> EvidenceSpan:
        return EvidenceSpan(
            doc_id=self.doc_id,
            line_start=self.line_start,
            line_end=self.line_end,
        )


class AnswerKey(BaseModel):
    case_id: str
    verdict: Verdict
    difficulty: Difficulty
    planted_evidence: list[PlantedEvidence]
    key_rationale: str


class EvidenceItem(BaseModel):
    evidence_id: str
    side: EvidenceSide
    criterion_id: str
    span: EvidenceSpan
    text: str


class CriterionResult(BaseModel):
    criterion_id: str
    result: CriterionResultKind
    method: str
    evidence_ids: list[str] = Field(default_factory=list)


class AuditResult(BaseModel):
    case_id: str
    status: PipelineStatus
    verdict: Verdict | None
    confidence: float = Field(ge=0.0, le=1.0)
    rules_verdict: Verdict | None = None
    # Composer's draft verdict. Deterministic evidence-balance heuristic by
    # default (honest name: this is NOT an LLM output unless one is configured).
    draft_verdict: Verdict | None = None
    criteria_results: list[CriterionResult] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    letter_markdown: str = ""
    dropped_sentences: int = 0
    # Why QA forced needs_review (empty when status is completed). Reviewer-safe
    # reason codes, e.g. rules_draft_disagreement, low_confidence.
    force_reasons: list[str] = Field(default_factory=list)
    source: AuditSource = "live"
    trace_id: str | None = None


class TrainingGradeRequest(BaseModel):
    verdict: Verdict
    selected_spans: list[EvidenceSpan] = Field(default_factory=list)


class MissedSpan(BaseModel):
    span: EvidenceSpan
    criterion_id: str


class TrainingGradeResponse(BaseModel):
    verdict_correct: bool
    key_verdict: Verdict
    evidence_score: float = Field(ge=0.0, le=1.0)
    missed_spans: list[MissedSpan] = Field(default_factory=list)
    extra_spans: list[EvidenceSpan] = Field(default_factory=list)
    feedback: str


class CaseSummary(BaseModel):
    """Public case list entry; never includes answer-key fields."""

    case_id: str
    target_dx: str
    difficulty: Difficulty | None = None
    has_precomputed: bool = False


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "chartproof"
    version: str = "0.1.0"


class CriteriaKind(StrEnum):
    STRUCTURED = "structured"
    NARRATIVE = "narrative"
    ANY_OF = "any_of"
    ALL_OF = "all_of"


class CriteriaNode(BaseModel):
    """Recursive criteria tree node loaded from YAML."""

    id: str
    kind: CriteriaKind
    question: str | None = None
    metric: str | None = None
    op: str | None = None
    threshold: float | None = None
    window_hours: int | None = None
    children: list[CriteriaNode] = Field(default_factory=list)

    model_config = {"extra": "ignore"}


class CriteriaFile(BaseModel):
    dx: str
    display_name: str
    icd10_prefixes: list[str]
    source_note: str
    verdict_rule: str
    criteria: list[CriteriaNode]

    model_config = {"extra": "ignore"}


def spans_intersect(a: EvidenceSpan | dict[str, Any], b: EvidenceSpan | dict[str, Any]) -> bool:
    """Convenience wrapper used by evals and grading."""
    sa = a if isinstance(a, EvidenceSpan) else EvidenceSpan.model_validate(a)
    sb = b if isinstance(b, EvidenceSpan) else EvidenceSpan.model_validate(b)
    return sa.intersects(sb)
