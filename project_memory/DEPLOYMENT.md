# Deployment

## Live topology

ChartProof's personal portfolio deployment runs entirely on Vercel Hobby:

| Surface | Project | Root | URL |
|---|---|---|---|
| Next.js UI | `chartproof` | `frontend/` | https://chartproof.vercel.app |
| FastAPI portfolio API | `chartproof-api` | repository root | https://chartproof-api.vercel.app |

Vercel Hobby is limited to personal, non-commercial use. The public deployment
contains synthetic records only and must never receive PHI.

## Why the public API is lightweight

The full backend includes Chroma, sentence-transformers, LangGraph, optional
Groq composition, runtime traces, and cache writes. That profile is appropriate
for local Docker and CI but is not a good fit for a free serverless function.

`app.py` therefore exports `backend.vercel_app`, a deliberately narrow adapter:

- health endpoint;
- 100-case listing and chart access;
- committed, CI-verified precomputed audit drafts;
- guarded server-side training grading;
- explicit `X-ChartProof-Mode: precomputed-portfolio` audit header;
- CORS restricted to the production UI and localhost.

The adapter accepts `fresh=true` for frontend compatibility but still returns a
result whose `source` is `precomputed`. It never claims that the retrieval/model
pipeline ran in the public free deployment.

The full application remains `backend.app`. CI builds its retrieval index, runs
the deterministic live smoke evaluation, and exercises the local production UI
and API together in Chrome.

## Environment variables

`chartproof-api`:

```text
ALLOWED_ORIGINS=https://chartproof.vercel.app,http://localhost:3000
```

`chartproof`:

```text
NEXT_PUBLIC_API_BASE_URL=https://chartproof-api.vercel.app
```

These values are public configuration, not secrets. No Groq key is required for
the public portfolio path.

## Manual deployment

The local Vercel projects are linked through ignored `.vercel/` directories.

```bash
# Deploy the API from the repository root.
npx --yes vercel@latest deploy --prod --yes

# Deploy the UI from frontend/.
cd frontend
npx --yes vercel@latest deploy --prod --yes
```

Git integration currently requires granting the Vercel GitHub app repository
access. Until that account-level permission is enabled, use the two explicit
deployment commands after a green `main` build.

## Verification

```bash
curl --fail https://chartproof-api.vercel.app/health
curl --fail https://chartproof-api.vercel.app/cases
cd frontend
E2E_BASE_URL=https://chartproof.vercel.app npm run test:e2e
```

The browser journey covers case count, pagination, filters, search, audit
evidence navigation, keyboard chart selection, training submission, and browser
console/page errors.

## Local/full-pipeline deployment

The repository Dockerfile continues to package the complete FastAPI pipeline:

```bash
docker build -t chartproof-api .
docker run --rm -p 7860:7860 chartproof-api
```

Use this profile when fresh retrieval/model execution is required. A paid or
organization-controlled container host can run the same image later without
changing the public portfolio contract.
