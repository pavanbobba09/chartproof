"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ChartViewer } from "@/components/ChartViewer";
import {
  type Case,
  type EvidenceSpan,
  type TrainingGrade,
  getCase,
  gradeTraining,
} from "@/lib/api";

export default function TrainingPage() {
  const params = useParams();
  const caseId = String(params.caseId);
  const [chart, setChart] = useState<Case | null>(null);
  const [verdict, setVerdict] = useState<"supported" | "not_supported" | null>(
    null
  );
  const [selected, setSelected] = useState<EvidenceSpan[]>([]);
  const [grade, setGrade] = useState<TrainingGrade | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setChart(await getCase(caseId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "load failed");
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    void load();
  }, [load]);

  function toggleLine(docId: string, line: number) {
    setGrade(null);
    setSelected((prev) => {
      const exists = prev.find(
        (s) =>
          s.doc_id === docId && s.line_start === line && s.line_end === line
      );
      if (exists) {
        return prev.filter((s) => s !== exists);
      }
      return [
        ...prev,
        { doc_id: docId, line_start: line, line_end: line },
      ];
    });
  }

  async function onSubmit() {
    if (!verdict) {
      setError("Select a verdict first.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const g = await gradeTraining(caseId, {
        verdict,
        selected_spans: selected,
      });
      setGrade(g);
    } catch (e) {
      setError(e instanceof Error ? e.message : "grade failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <p className="text-slate-600">Loading chart…</p>;
  if (!chart) return <p className="text-red-700">{error || "Missing case"}</p>;

  return (
    <div className="space-y-4">
      <div>
        <Link href="/" className="text-sm text-brand-600 hover:underline">
          ← Cases
        </Link>
        <h1 className="mt-1 text-2xl font-semibold">Training · {caseId}</h1>
        <p className="text-sm text-slate-600">
          Choose a verdict and click chart lines as evidence. Answer key is
          revealed only after you submit.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <span className="text-sm font-medium text-slate-700">Your verdict:</span>
        {(["supported", "not_supported"] as const).map((v) => (
          <button
            key={v}
            type="button"
            onClick={() => {
              setVerdict(v);
              setGrade(null);
            }}
            className={`rounded-md px-3 py-1.5 text-sm font-medium ${
              verdict === v
                ? "bg-brand-600 text-white"
                : "border border-slate-300 text-slate-700 hover:bg-slate-50"
            }`}
          >
            {v}
          </button>
        ))}
        <span className="text-xs text-slate-500">
          {selected.length} line(s) selected
        </span>
        <button
          type="button"
          onClick={() => void onSubmit()}
          disabled={submitting || !verdict}
          className="ml-auto rounded-md bg-brand-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {submitting ? "Grading…" : "Submit"}
        </button>
      </div>

      {grade && (
        <div
          className={`rounded-xl border p-4 ${
            grade.verdict_correct
              ? "border-emerald-200 bg-emerald-50"
              : "border-amber-200 bg-amber-50"
          }`}
        >
          <h2 className="font-semibold text-slate-900">
            {grade.verdict_correct ? "Verdict correct" : "Verdict incorrect"} ·
            key = {grade.key_verdict}
          </h2>
          <p className="mt-1 text-sm text-slate-800">
            Evidence score: {(grade.evidence_score * 100).toFixed(0)}%
          </p>
          <p className="mt-2 text-sm text-slate-700">{grade.feedback}</p>
          {grade.missed_spans.length > 0 && (
            <div className="mt-3">
              <p className="text-xs font-semibold uppercase text-slate-600">
                Missed evidence
              </p>
              <ul className="mt-1 space-y-1 text-xs text-slate-700">
                {grade.missed_spans.map((m, i) => (
                  <li key={i}>
                    {m.criterion_id}: {m.span.doc_id} lines {m.span.line_start}-
                    {m.span.line_end}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <ChartViewer
        chart={chart}
        selectable
        selected={selected}
        onToggleLine={toggleLine}
        highlight={
          grade?.missed_spans[0]
            ? grade.missed_spans[0].span
            : null
        }
      />
    </div>
  );
}
