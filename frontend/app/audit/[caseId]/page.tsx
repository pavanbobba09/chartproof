"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChartViewer, scrollToSpan } from "@/components/ChartViewer";
import { StatusBadge } from "@/components/StatusBadge";
import {
  type AuditResult,
  type Case,
  type EvidenceSpan,
  getAudit,
  getCase,
  postAudit,
} from "@/lib/api";

const REVIEW_REASON_LABELS: Record<string, string> = {
  rules_draft_disagreement:
    "The deterministic rules verdict and the draft verdict disagree.",
  unknown_verdict: "A verdict could not be determined from the chart.",
  dropped_uncited_sentences:
    "Draft sentences without valid citations were removed.",
  low_confidence: "Confidence is below the review threshold.",
};

const CRITERION_RESULT_STYLES: Record<string, string> = {
  met: "bg-emerald-100 text-emerald-800",
  not_met: "bg-rose-100 text-rose-800",
  unclear: "bg-amber-100 text-amber-800",
};

export default function AuditPage() {
  const params = useParams();
  const caseId = String(params.caseId);
  const [chart, setChart] = useState<Case | null>(null);
  const [audit, setAudit] = useState<AuditResult | null>(null);
  const [highlight, setHighlight] = useState<EvidenceSpan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [freshBusy, setFreshBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const c = await getCase(caseId);
      setChart(c);
      try {
        const a = await getAudit(caseId);
        setAudit(a);
      } catch {
        const a = await postAudit(caseId, false);
        setAudit(a);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "load failed");
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function runFresh() {
    setFreshBusy(true);
    setError(null);
    try {
      const a = await postAudit(caseId, true);
      setAudit(a);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "fresh analysis failed";
      if (msg.includes("503") || msg.toLowerCase().includes("rate-limited")) {
        setError(
          "Live analysis is temporarily unavailable (rate limit or index warming). " +
            "The precomputed draft above remains valid for demo; try again in a minute."
        );
      } else {
        setError(msg);
      }
    } finally {
      setFreshBusy(false);
    }
  }

  function jumpTo(span: EvidenceSpan) {
    setHighlight(span);
    scrollToSpan(span);
  }

  function jumpToEvidenceId(evidenceId: string) {
    const item = audit?.evidence.find((e) => e.evidence_id === evidenceId);
    if (item) jumpTo(item.span);
  }

  if (loading) {
    return <p className="text-slate-600">Loading audit…</p>;
  }
  if (error && !chart) {
    return <p className="text-red-700">{error}</p>;
  }
  if (!chart) return null;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link href="/" className="text-sm text-brand-600 hover:underline">
            ← Cases
          </Link>
          <h1 className="mt-1 text-2xl font-semibold">Audit · {caseId}</h1>
          <p className="text-sm text-slate-600">
            Machine draft for auditor review. Not a payment decision.
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          {audit && (
            <StatusBadge status={audit.status} verdict={audit.verdict} />
          )}
          <button
            type="button"
            onClick={() => void runFresh()}
            disabled={freshBusy}
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            {freshBusy ? "Running…" : "Run fresh analysis"}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          {error}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="max-h-[80vh] space-y-3 overflow-y-auto pr-1">
          <ChartViewer chart={chart} highlight={highlight} />
        </div>

        <div className="space-y-4">
          {audit && (
            <>
              {audit.status === "needs_review" &&
                (audit.force_reasons?.length ?? 0) > 0 && (
                  <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 shadow-sm">
                    <h2 className="mb-1 text-sm font-semibold text-amber-900">
                      Why this draft needs human review
                    </h2>
                    <ul className="list-disc pl-5 text-sm text-amber-900">
                      {audit.force_reasons?.map((code) => (
                        <li key={code}>
                          {REVIEW_REASON_LABELS[code] ?? code}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

              {audit.criteria_results.length > 0 && (
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <h2 className="mb-2 text-sm font-semibold text-slate-800">
                    Criteria checklist
                  </h2>
                  <ul className="space-y-1.5">
                    {audit.criteria_results.map((c) => (
                      <li
                        key={c.criterion_id}
                        className="flex flex-wrap items-center gap-2 text-sm"
                      >
                        <span
                          className={`rounded px-1.5 py-0.5 text-xs font-semibold ${
                            CRITERION_RESULT_STYLES[c.result] ??
                            "bg-slate-100 text-slate-700"
                          }`}
                        >
                          {c.result}
                        </span>
                        <span className="font-medium text-slate-800">
                          {c.criterion_id}
                        </span>
                        <span className="text-xs text-slate-400">
                          {c.method}
                        </span>
                        {c.evidence_ids.map((eid) => (
                          <button
                            key={eid}
                            type="button"
                            onClick={() => jumpToEvidenceId(eid)}
                            className="rounded border border-slate-200 bg-slate-50 px-1 font-mono text-xs text-brand-600 hover:bg-amber-50"
                            title="Jump to cited chart lines"
                          >
                            {eid}
                          </button>
                        ))}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <h2 className="mb-2 text-sm font-semibold text-slate-800">
                  Evidence table
                </h2>
                <p className="mb-2 text-xs text-slate-500">
                  source: {audit.source} · confidence{" "}
                  {(audit.confidence * 100).toFixed(0)}% · rules{" "}
                  {audit.rules_verdict ?? "n/a"} · draft{" "}
                  {audit.draft_verdict ?? "n/a"}
                </p>
                <div className="overflow-x-auto">
                  <table className="min-w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-600">
                      <tr>
                        <th className="px-2 py-1">#</th>
                        <th className="px-2 py-1">Side</th>
                        <th className="px-2 py-1">Criterion</th>
                        <th className="px-2 py-1">Lines</th>
                        <th className="px-2 py-1">Excerpt</th>
                      </tr>
                    </thead>
                    <tbody>
                      {audit.evidence.map((e) => (
                        <tr
                          key={e.evidence_id}
                          className="cursor-pointer border-t border-slate-100 hover:bg-amber-50"
                          onClick={() => jumpTo(e.span)}
                        >
                          <td className="px-2 py-1 font-mono">{e.evidence_id}</td>
                          <td className="px-2 py-1">{e.side}</td>
                          <td className="px-2 py-1">{e.criterion_id}</td>
                          <td className="px-2 py-1 font-mono">
                            {e.span.doc_id}:{e.span.line_start}-{e.span.line_end}
                          </td>
                          <td className="max-w-xs truncate px-2 py-1">{e.text}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <h2 className="mb-2 text-sm font-semibold text-slate-800">
                  Rationale letter (draft)
                </h2>
                <div className="prose-letter text-sm text-slate-800">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {audit.letter_markdown}
                  </ReactMarkdown>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
