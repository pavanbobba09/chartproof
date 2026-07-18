"use client";

import type { Case, EvidenceSpan } from "@/lib/api";

type Props = {
  chart: Case;
  highlight?: EvidenceSpan | null;
  selectable?: boolean;
  selected?: EvidenceSpan[];
  onToggleLine?: (docId: string, line: number) => void;
};

function isHighlighted(
  docId: string,
  line: number,
  highlight?: EvidenceSpan | null
) {
  if (!highlight || highlight.doc_id !== docId) return false;
  return line >= highlight.line_start && line <= highlight.line_end;
}

function isSelected(docId: string, line: number, selected?: EvidenceSpan[]) {
  if (!selected) return false;
  return selected.some(
    (s) =>
      s.doc_id === docId && line >= s.line_start && line <= s.line_end
  );
}

export function ChartViewer({
  chart,
  highlight,
  selectable,
  selected,
  onToggleLine,
}: Props) {
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-600">
        <span className="font-medium text-slate-800">{chart.case_id}</span>
        {" · "}
        {chart.patient.age}
        {chart.patient.sex}
        {" · billed "}
        {chart.billed.icd10.join(", ")} / DRG {chart.billed.drg}
      </div>

      {chart.documents.map((doc) => (
        <section
          key={doc.doc_id}
          id={`doc-${doc.doc_id}`}
          className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"
        >
          <header className="border-b border-slate-100 bg-slate-50 px-4 py-2 text-sm font-medium text-slate-700">
            {doc.doc_type.replaceAll("_", " ")} · {doc.date} ·{" "}
            <span className="font-mono text-xs text-slate-500">{doc.doc_id}</span>
          </header>
          <ol className="divide-y divide-slate-50 font-mono text-xs sm:text-sm">
            {doc.lines.map((line, idx) => {
              const n = idx + 1;
              const hi = isHighlighted(doc.doc_id, n, highlight);
              const sel = isSelected(doc.doc_id, n, selected);
              return (
                <li
                  key={n}
                  id={`line-${doc.doc_id}-${n}`}
                  className={`flex gap-3 px-3 py-1.5 ${
                    hi ? "line-highlight" : sel ? "line-selected" : ""
                  } ${selectable ? "cursor-pointer hover:bg-slate-50" : ""}`}
                  onClick={() => selectable && onToggleLine?.(doc.doc_id, n)}
                >
                  <span className="w-8 shrink-0 select-none text-right text-slate-400">
                    {n}
                  </span>
                  <span className="whitespace-pre-wrap text-slate-800">{line}</span>
                </li>
              );
            })}
          </ol>
        </section>
      ))}

      <section className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h3 className="mb-2 text-sm font-semibold">Labs</h3>
          <ul className="space-y-1 text-xs text-slate-700">
            {chart.labs.map((l, i) => (
              <li key={i}>
                {l.name} {l.value} {l.unit}{" "}
                <span className="text-slate-400">{l.datetime}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h3 className="mb-2 text-sm font-semibold">Vitals</h3>
          <ul className="space-y-1 text-xs text-slate-700">
            {chart.vitals.map((v, i) => (
              <li key={i}>
                {v.name} {v.value} {v.unit}{" "}
                <span className="text-slate-400">{v.datetime}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  );
}

export function scrollToSpan(span: EvidenceSpan) {
  const el = document.getElementById(
    `line-${span.doc_id}-${span.line_start}`
  );
  el?.scrollIntoView({ behavior: "smooth", block: "center" });
}
