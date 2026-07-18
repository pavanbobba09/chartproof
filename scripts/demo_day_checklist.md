# Demo-day checklist (Phase 5)

## Before the call (T-10 min)

1. Open the API Space so it cold-starts: `https://trippy09-chartproof.hf.space/health`
2. Open the Vercel frontend (set after deploy).
3. Confirm CI green on `main`: https://github.com/pavanbobba09/chartproof/actions
4. Optional: open one precomputed case; results should render instantly.

## During the demo

1. Case list loads from API.
2. Open **Audit** on `sepsis_001` (precomputed, instant letter + evidence).
3. Click an evidence row; chart scrolls and highlights lines.
4. Optional: **Run fresh analysis** once (may be slow / rate-limited on free tier).
5. Open **Train** on any case: pick verdict, click lines, submit, show feedback.

## Fallback

- If live Space is cold or rate-limited, stay on precomputed audits.
- Local fallback: `uvicorn` + `npm run dev` from the README.
- Video link placeholder in README when recorded.

## Secrets / config

| Where | Key |
|-------|-----|
| GitHub Actions | `HF_TOKEN` (write to Space), optional `GROQ_API_KEY` for live smoke later |
| HF Space secrets | `GROQ_API_KEY` (only if live compose uses Groq) |
| HF Space variables | `ALLOWED_ORIGINS` = Vercel URL(s) + `http://localhost:3000` |
| Vercel env | `NEXT_PUBLIC_API_BASE_URL` = `https://trippy09-chartproof.hf.space` |
