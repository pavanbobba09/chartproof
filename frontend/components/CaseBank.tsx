"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { CaseSummary } from "@/lib/api";

const PAGE_SIZE = 20;

type Props = { cases: CaseSummary[] };
type DifficultyFilter = "all" | "clear" | "borderline";
type DatasetFilter = "all" | CaseSummary["dataset_role"];

export function CaseBank({ cases }: Props) {
  const [query, setQuery] = useState("");
  const [difficulty, setDifficulty] = useState<DifficultyFilter>("all");
  const [dataset, setDataset] = useState<DatasetFilter>("all");
  const [page, setPage] = useState(1);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return cases.filter((item) => {
      const matchesQuery =
        !needle ||
        item.case_id.toLowerCase().includes(needle) ||
        item.target_dx.toLowerCase().includes(needle);
      const matchesDifficulty =
        difficulty === "all" || item.difficulty === difficulty;
      const matchesDataset =
        dataset === "all" || item.dataset_role === dataset;
      return matchesQuery && matchesDifficulty && matchesDataset;
    });
  }, [cases, dataset, difficulty, query]);

  useEffect(() => setPage(1), [dataset, difficulty, query]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const visible = filtered.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE
  );
  const clinicalCount = cases.filter(
    (item) => item.dataset_role === "clinical_scenario"
  ).length;

  return (
    <section className="space-y-4" aria-labelledby="case-bank-heading">
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <p className="text-xs uppercase tracking-wide text-slate-500">Total records</p>
          <p className="text-2xl font-semibold" data-testid="case-count">
            {cases.length}
          </p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <p className="text-xs uppercase tracking-wide text-slate-500">Clinical scenarios</p>
          <p className="text-2xl font-semibold">{clinicalCount}</p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <p className="text-xs uppercase tracking-wide text-slate-500">Volume variants</p>
          <p className="text-2xl font-semibold">{cases.length - clinicalCount}</p>
        </div>
      </div>

      <div className="grid gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-3">
        <label className="text-sm font-medium text-slate-700">
          Search
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Case ID or diagnosis"
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 font-normal"
          />
        </label>
        <label className="text-sm font-medium text-slate-700">
          Difficulty
          <select
            value={difficulty}
            onChange={(event) =>
              setDifficulty(event.target.value as DifficultyFilter)
            }
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 font-normal"
          >
            <option value="all">All difficulties</option>
            <option value="clear">Clear</option>
            <option value="borderline">Borderline</option>
          </select>
        </label>
        <label className="text-sm font-medium text-slate-700">
          Dataset purpose
          <select
            value={dataset}
            onChange={(event) => setDataset(event.target.value as DatasetFilter)}
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 font-normal"
          >
            <option value="all">All records</option>
            <option value="clinical_scenario">Clinical scenarios</option>
            <option value="volume_test">Volume testing</option>
          </select>
        </label>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full text-left text-sm">
          <caption id="case-bank-heading" className="sr-only">
            Synthetic chart case bank
          </caption>
          <thead className="bg-slate-100 text-slate-700">
            <tr>
              <th className="px-4 py-3 font-medium">Case</th>
              <th className="px-4 py-3 font-medium">Purpose</th>
              <th className="px-4 py-3 font-medium">Dx</th>
              <th className="px-4 py-3 font-medium">Difficulty</th>
              <th className="px-4 py-3 font-medium">Audit</th>
              <th className="px-4 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((item) => (
              <tr
                key={item.case_id}
                data-testid="case-row"
                className="border-t border-slate-100"
              >
                <td className="px-4 py-3 font-mono text-xs sm:text-sm">
                  {item.case_id}
                </td>
                <td className="px-4 py-3 text-xs">
                  {item.dataset_role === "clinical_scenario"
                    ? "clinical scenario"
                    : "volume test"}
                </td>
                <td className="px-4 py-3 capitalize">{item.target_dx}</td>
                <td className="px-4 py-3">{item.difficulty || "n/a"}</td>
                <td className="px-4 py-3">
                  {item.has_precomputed ? (
                    <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700">
                      ready
                    </span>
                  ) : (
                    <span className="text-xs text-slate-400">live only</span>
                  )}
                </td>
                <td className="space-x-2 whitespace-nowrap px-4 py-3">
                  <Link
                    href={`/audit/${item.case_id}`}
                    aria-label={`Audit ${item.case_id}`}
                    className="inline-flex rounded-md bg-brand-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600"
                  >
                    Audit
                  </Link>
                  <Link
                    href={`/training/${item.case_id}`}
                    aria-label={`Train with ${item.case_id}`}
                    className="inline-flex rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600"
                  >
                    Train
                  </Link>
                </td>
              </tr>
            ))}
            {!visible.length && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                  No cases match these filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm text-slate-600">
        <p aria-live="polite">
          Showing {visible.length} of {filtered.length} matching records
        </p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setPage((value) => Math.max(1, value - 1))}
            disabled={currentPage === 1}
            className="rounded border border-slate-300 bg-white px-3 py-1.5 disabled:opacity-40"
          >
            Previous
          </button>
          <span>
            Page {currentPage} of {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
            disabled={currentPage === totalPages}
            className="rounded border border-slate-300 bg-white px-3 py-1.5 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </div>
    </section>
  );
}
