FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install only essential runtime dependencies (libglib, OpenMP, ffmpeg, curl)
# Note: opencv-python-headless does NOT require libgl1/Mesa/OpenGL/LLVM, saving ~220MB
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgomp1 \
    ffmpeg \
    curl && \
    rm -rf /var/lib/apt/lists/*

# Security: Create non-root application user with home directory
RUN adduser --system --group --home /home/appuser appuser && \
    mkdir -p /home/appuser/.cache && \
    chown -R appuser:appuser /home/appuser

WORKDIR /app

# ---------- Builder stage ----------
FROM base AS builder

# Install build tools and binutils for stripping shared libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    binutils && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip

# Pre-install CPU-optimized PyTorch and torchvision using BuildKit cache mount
# Prevents 2.5GB+ CUDA bloat, avoids PyPI socket timeouts, and accelerates builds
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 60 --retries 5 --prefer-binary \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    torch torchvision

# Copy requirements and install remaining dependencies using BuildKit cache mount
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 60 --retries 5 --prefer-binary \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt

# Second-Stage Size Optimization:
# 1. Remove unnecessary sub-dependencies (polars, polars-runtime-32, nvidia-ml-py)
# 2. Reinstall opencv-python-headless cleanly and eliminate redundant opencv_python.libs
# 3. Strip unneeded test directories and C++ headers from PyTorch and site-packages
# 4. Strip debug symbols from all compiled shared libraries (.so)
# 5. Remove leftover bytecode caches (__pycache__)
RUN (pip uninstall -y polars polars-runtime-32 nvidia-ml-py || true) && \
    (pip install --no-deps --force-reinstall opencv-python-headless || true) && \
    rm -rf /usr/local/lib/python3.11/site-packages/opencv_python.libs \
           /usr/local/lib/python3.11/site-packages/torch/test \
           /usr/local/lib/python3.11/site-packages/torch/include && \
    find /usr/local/lib/python3.11/site-packages -type d \( -name 'tests' -o -name 'test' \) ! -path '*/torch/testing*' -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.11/site-packages -name '*.so*' -type f -exec strip --strip-unneeded {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.11/site-packages -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true

# Copy application source code (filtered by .dockerignore)
COPY . .

# Ensure upload directory exists and set permissions
RUN mkdir -p data/uploads && chown -R appuser:appuser /app

# ---------- Runtime stage ----------
FROM base AS runtime

WORKDIR /app

# Copy only the installed site-packages, binaries, and app source from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder --chown=appuser:appuser /app /app

# Security: Run as non-root user
USER appuser

ENV HOME=/home/appuser \
    HF_HOME=/home/appuser/.cache/huggingface \
    YOLO_CONFIG_DIR=/home/appuser/.cache/ultralytics

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
