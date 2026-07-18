import Link from "next/link";
import { getCases } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  let cases: Awaited<ReturnType<typeof getCases>> = [];
  let error: string | null = null;
  try {
    cases = await getCases();
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load cases";
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Case bank</h1>
        <p className="mt-1 text-slate-600">
          Pick a synthetic inpatient chart for audit assist or training mode.
          Outputs are drafts only; a human makes the final determination.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          Could not reach the API. Start the backend on port 8000 and set{" "}
          <code className="rounded bg-red-100 px-1">NEXT_PUBLIC_API_BASE_URL</code>.
          <div className="mt-1 font-mono text-xs">{error}</div>
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-100 text-slate-700">
            <tr>
              <th className="px-4 py-3 font-medium">Case</th>
              <th className="px-4 py-3 font-medium">Dx</th>
              <th className="px-4 py-3 font-medium">Difficulty</th>
              <th className="px-4 py-3 font-medium">Precomputed</th>
              <th className="px-4 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {cases.map((c) => (
              <tr key={c.case_id} className="border-t border-slate-100">
                <td className="px-4 py-3 font-mono text-xs sm:text-sm">
                  {c.case_id}
                </td>
                <td className="px-4 py-3 capitalize">{c.target_dx}</td>
                <td className="px-4 py-3">{c.difficulty || "n/a"}</td>
                <td className="px-4 py-3">
                  {c.has_precomputed ? (
                    <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700">
                      ready
                    </span>
                  ) : (
                    <span className="text-xs text-slate-400">live only</span>
                  )}
                </td>
                <td className="px-4 py-3 space-x-2">
                  <Link
                    href={`/audit/${c.case_id}`}
                    className="inline-flex rounded-md bg-brand-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-700"
                  >
                    Audit
                  </Link>
                  <Link
                    href={`/training/${c.case_id}`}
                    className="inline-flex rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Train
                  </Link>
                </td>
              </tr>
            ))}
            {!cases.length && !error && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                  No cases found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
