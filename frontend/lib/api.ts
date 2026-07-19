const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export type CaseSummary = {
  case_id: string;
  target_dx: string;
  difficulty?: string | null;
  has_precomputed: boolean;
};

export type EvidenceSpan = {
  doc_id: string;
  line_start: number;
  line_end: number;
};

export type Document = {
  doc_id: string;
  doc_type: string;
  date: string;
  lines: string[];
};

export type Case = {
  case_id: string;
  target_dx: string;
  billed: { icd10: string[]; drg: string };
  patient: { age: number; sex: string };
  documents: Document[];
  labs: { name: string; value: number; unit: string; datetime: string }[];
  vitals: { name: string; value: number; unit: string; datetime: string }[];
};

export type EvidenceItem = {
  evidence_id: string;
  side: string;
  criterion_id: string;
  span: EvidenceSpan;
  text: string;
};

export type AuditResult = {
  case_id: string;
  status: string;
  verdict: string | null;
  confidence: number;
  rules_verdict?: string | null;
  draft_verdict?: string | null;
  criteria_results: {
    criterion_id: string;
    result: string;
    method: string;
    evidence_ids: string[];
  }[];
  evidence: EvidenceItem[];
  letter_markdown: string;
  dropped_sentences: number;
  force_reasons?: string[];
  source: string;
  trace_id?: string | null;
};

export type TrainingGrade = {
  verdict_correct: boolean;
  key_verdict: string;
  evidence_score: number;
  missed_spans: { span: EvidenceSpan; criterion_id: string }[];
  extra_spans: EvidenceSpan[];
  feedback: string;
};

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${path}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export function getCases() {
  return apiFetch<CaseSummary[]>("/cases");
}

export function getCase(caseId: string) {
  return apiFetch<Case>(`/cases/${caseId}`);
}

export function getAudit(caseId: string) {
  return apiFetch<AuditResult>(`/audit/${caseId}`);
}

export function postAudit(caseId: string, fresh = false) {
  const q = fresh ? "?fresh=true" : "";
  return apiFetch<AuditResult>(`/audit/${caseId}${q}`, { method: "POST" });
}

export function gradeTraining(
  caseId: string,
  body: { verdict: string; selected_spans: EvidenceSpan[] }
) {
  return apiFetch<TrainingGrade>(`/training/${caseId}/grade`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export { API_BASE };
