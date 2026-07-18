export function StatusBadge({
  status,
  verdict,
}: {
  status: string;
  verdict?: string | null;
}) {
  const isReview = status === "needs_review";
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span
        className={`rounded-full px-2.5 py-1 text-xs font-medium ${
          isReview
            ? "bg-amber-100 text-amber-900"
            : "bg-emerald-100 text-emerald-900"
        }`}
      >
        {status}
      </span>
      {verdict && (
        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-800">
          draft: {verdict}
        </span>
      )}
      {!verdict && isReview && (
        <span className="text-xs text-slate-500">human review required</span>
      )}
    </div>
  );
}
