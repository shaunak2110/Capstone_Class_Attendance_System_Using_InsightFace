FROM python:3.11-slim

# Runtime libs (opencv-headless, onnxruntime) + build tools so insightface's
# Cython extension (mesh_core_cython) compiles from source on slim images.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgomp1 \
        curl \
        gcc \
        g++ \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

# HF Spaces runs containers as a non-root user (UID 1000). Create one and
# give it ownership of the app + cache dirs so InsightFace can download
# buffalo_l weights to ~/.insightface/ on first request.
RUN useradd -m -u 1000 appuser
ENV HOME=/home/appuser \
    PATH=/home/appuser/.local/bin:$PATH \
    PORT=7860 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --chown=appuser:appuser requirements.txt .
USER appuser
RUN pip install --user --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser . .

EXPOSE 7860

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
