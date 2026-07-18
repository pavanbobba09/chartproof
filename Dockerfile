FROM python:3.11-slim

# HF Spaces runs containers as user 1000; create it and own the app dir
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface \
    PYTHONPATH=/home/user/app \
    PYTHONUNBUFFERED=1
WORKDIR /home/user/app

# System deps for sentence-transformers / chromadb wheels where needed
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
USER user

COPY --chown=user backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --user -r requirements.txt

# Pre-download the embedding model at build time so cold starts are fast
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

COPY --chown=user backend/ ./backend/
COPY --chown=user data/ ./data/
COPY --chown=user evals/ ./evals/
COPY --chown=user pyproject.toml ./pyproject.toml

# Build the Chroma index into the image (free Space storage resets on restart,
# so never rely on runtime-writable persistence for the index)
RUN python -m backend.index.build --data data --out ./chroma
ENV CHROMA_DIR=/home/user/app/chroma

# Runtime dirs for ephemeral traces/caches (empty is fine)
RUN mkdir -p /home/user/app/runs/cache

EXPOSE 7860
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "7860"]
