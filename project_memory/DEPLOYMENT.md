# DEPLOYMENT.md

Topology: GitHub is the source of truth. GitHub Actions runs quality gates (lint, tests, smoke eval) on every push, and on main it force-syncs the repo to a Hugging Face Docker Space that serves the FastAPI backend. Vercel builds `frontend/` and serves the Next.js UI, which calls the Space API. Everything below is on free tiers.

Placeholders used throughout, adjust if names differ:
- GitHub: `pavanbobba09/chartproof`
- HF Space: `trippy09/chartproof`  (API base: `https://trippy09-chartproof.hf.space`)
- Custom domain (optional): `chartproof.pavanbobba-developer.com`

## 1. One-time setup

1. Create the GitHub repo and push the scaffold.
2. On Hugging Face: New Space, owner `trippy09`, name `chartproof`, SDK: Docker, hardware: CPU basic (free), visibility: public.
3. Create an HF access token with write access to the Space (fine-grained: write on that repo is enough).
4. GitHub repo Settings -> Secrets and variables -> Actions -> New repository secret:
   - `HF_TOKEN`: the HF write token
   - `GROQ_API_KEY`: your Groq key (used by the smoke-eval job)
5. HF Space Settings -> Variables and secrets:
   - Secret `GROQ_API_KEY` (the backend reads it at runtime; it never reaches the browser)
   - Variable `ALLOWED_ORIGINS` = `https://chartproof.vercel.app,https://chartproof.pavanbobba-developer.com,http://localhost:3000` (adjust to your real Vercel URL)

## 2. GitHub Actions: evals on every push, auto-deploy on main

`.github/workflows/ci.yml`:

```yaml
name: CI and deploy

on:
  push:
    branches: [main]
  pull_request:
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - name: Install
        run: pip install -r backend/requirements.txt -r backend/requirements-dev.txt
      - name: Lint
        run: ruff check backend
      - name: Unit tests and deterministic checks
        run: pytest backend/tests -q

  smoke-eval:
    # Runs the 5-case eval suite with real LLM calls. Fork PRs are skipped
    # because they cannot receive repo secrets.
    needs: test
    if: github.event_name == 'push' || github.event.pull_request.head.repo.full_name == github.repository
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - name: Install
        run: pip install -r backend/requirements.txt
      - name: Build index
        run: python -m backend.index.build --data data --out .chroma
      - name: Run smoke eval with thresholds
        env:
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
        run: python -m evals.run --suite smoke --enforce-thresholds
      - name: Upload eval report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: eval-report
          path: evals/out/

  deploy:
    # Auto-sync to the Hugging Face Space only when main is green.
    needs: [test, smoke-eval]
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Push to Hugging Face Space
        env:
          HF_TOKEN: ${{ secrets.HF_TOKEN }}
        run: |
          git config user.name "github-actions"
          git config user.email "actions@users.noreply.github.com"
          git push --force https://trippy09:${HF_TOKEN}@huggingface.co/spaces/trippy09/chartproof HEAD:main
```

Notes:
- `evals.run --enforce-thresholds` must exit non-zero when any metric in `evals/thresholds.yaml` is missed. That is what makes "CI that runs evals" real: a regression blocks deploy.
- The deploy push is `--force` on purpose: the Space mirrors GitHub, GitHub history wins, and nobody commits to the Space directly.
- The Space rebuilds its Docker image automatically after every sync.

Optional nightly full eval, `.github/workflows/full-eval.yml`:

```yaml
name: Full eval

on:
  schedule:
    - cron: "0 6 * * *"
  workflow_dispatch:

jobs:
  full-eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - run: pip install -r backend/requirements.txt
      - run: python -m backend.index.build --data data --out .chroma
      - name: Full suite
        env:
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
        run: python -m evals.run --suite full
      - uses: actions/upload-artifact@v4
        with:
          name: full-eval-report
          path: evals/out/
```

## 3. Hugging Face Space (backend)

The Space needs two things at its repo root: a `README.md` with Space frontmatter, and a `Dockerfile`. Since we sync the whole GitHub repo, both live in the GitHub repo root.

Space frontmatter at the top of `README.md` (the rest of the README is the normal project README):

```yaml
---
title: ChartProof API
emoji: "\U0001FA7A"
colorFrom: purple
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---
```

`Dockerfile`:

```dockerfile
FROM python:3.11-slim

# HF Spaces runs containers as user 1000; create it and own the app dir
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface
WORKDIR /home/user/app

COPY --chown=user backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --user -r requirements.txt

# Pre-download the embedding model at build time so cold starts are fast
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

COPY --chown=user backend/ ./backend/
COPY --chown=user data/ ./data/
COPY --chown=user evals/ ./evals/

# Build the Chroma index into the image (free Space storage resets on restart,
# so never rely on runtime-writable persistence)
RUN python -m backend.index.build --data data --out ./chroma
ENV CHROMA_DIR=/home/user/app/chroma

EXPOSE 7860
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "7860"]
```

CORS in `backend/app.py`:

```python
import os
from fastapi.middleware.cors import CORSMiddleware

origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

Free-tier behavior to design around:
- Sleep: free Spaces pause after around 48 hours without traffic and cold start on the next visit. With the model and index baked into the image, a wake is container boot, well under a minute. Still, open the Space yourself before sending anyone the link.
- Storage: anything written at runtime (`runs/`, caches) is ephemeral. Fine for a demo; precomputed results ship inside the image from `data/precomputed/`.
- No file in the repo may exceed 10 MB without Git LFS on the HF side. Case JSONs and guideline text are tiny; the index is built in Docker, so this never triggers. If it ever does, move the offending artifact out of git.

## 4. Vercel (frontend)

1. Import the GitHub repo in Vercel, set Root Directory to `frontend/`, framework auto-detects Next.js. Hobby tier.
2. Environment variable: `NEXT_PUBLIC_API_BASE_URL` = `https://trippy09-chartproof.hf.space`.
3. Every push to main auto-deploys the frontend; PRs get preview URLs for free.
4. Optional custom domain: add `chartproof.pavanbobba-developer.com` in Vercel Domains, then create the CNAME record Vercel shows you at your DNS provider. Add the domain to `ALLOWED_ORIGINS` on the Space.

Keep all Groq calls server-side on the Space. The frontend only ever talks to your API, so no key can leak into the browser bundle.

## 5. Demo-day checklist

- [ ] Visit the Space 10 minutes before any call so it is warm
- [ ] Load the Vercel app, open one precomputed case: results should render instantly
- [ ] Press "run fresh analysis" once to confirm live pipeline plus Groq quota are healthy
- [ ] Check the CI badge is green and the latest eval report artifact looks right
- [ ] Test the link from your phone on cellular data
- [ ] Have the 2 minute video link ready as a fallback if the network dies

## 6. Troubleshooting

- Deploy job fails with a push rejection: someone committed to the Space directly. The `--force` push should prevent this; if histories still conflict, delete stray Space commits from the HF UI and re-run the job.
- Space stuck in Building: open the Space's Logs tab; the usual cause is a requirements pin conflict or the index build failing on a malformed case file (run `backend.index.build` locally to reproduce).
- 401/403 from the deploy job: the `HF_TOKEN` lacks write access to the Space or expired; regenerate and update the GitHub secret.
- Smoke eval flaking on 429s: Groq free-tier rate limit; the eval runner should retry with backoff. If it persists, lower smoke concurrency to 1.
- CORS errors in the browser: the exact Vercel URL (including preview URLs if you demo from one) must appear in `ALLOWED_ORIGINS` on the Space.
- Frontend shows stale API data: Vercel cached a fetch; use `cache: "no-store"` on API calls from the app.
