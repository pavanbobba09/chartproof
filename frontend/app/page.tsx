import { getCases } from "@/lib/api";
import { CaseBank } from "@/components/CaseBank";

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

      <div className="rounded-lg border border-violet-200 bg-violet-50 p-4 text-sm text-violet-950">
        <span className="font-semibold">Honest evaluation boundary:</span>{" "}
        clinical quality is measured on 15 independently generated scenarios.
        The other 85 records are deterministic variants for workflow and volume
        testing, not additional clinical evidence.
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          Could not reach the API. Start the backend on port 8000 and set{" "}
          <code className="rounded bg-red-100 px-1">NEXT_PUBLIC_API_BASE_URL</code>.
          <div className="mt-1 font-mono text-xs">{error}</div>
        </div>
      )}

      {!error && <CaseBank cases={cases} />}
    </div>
  );
}
