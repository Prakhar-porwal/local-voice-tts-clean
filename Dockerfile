# Stage 1: Build React Frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

COPY app/package.json app/package-lock.json ./
RUN npm ci

COPY app/ ./
# Build the app to /app/frontend/dist
RUN npm run build


# Stage 2: Python Backend
# Use official Coqui TTS CPU image (includes TTS pre-installed!)
# This prevents OOM errors because we don't need to compile TTS or Torch.
FROM ghcr.io/coqui-ai/tts-cpu as backend

WORKDIR /app

# Install system dependencies for audio processing
# (The base image might have some, but we ensure these are present)
USER root
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    espeak-ng \
    libsndfile1 \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user (optional but good practice)
RUN useradd -m -u 1000 user || true

# Copy frontend build from Stage 1 to static folder
COPY --from=frontend-builder /app/frontend/dist static/

# Copy server code
COPY requirements.txt .

# Install Python dependencies (FastAPI, etc.) but SKIP TTS and TORCH (already in base)
# We upgrade pip and install requirements excluding TTS and torch
RUN pip install --upgrade pip && \
    sed -i '/TTS/d' requirements.txt && \
    sed -i '/torch/d' requirements.txt && \
    pip install --no-cache-dir -r requirements.txt

# Fix permissions: Base image has TTS in /root/TTS (editable install)
# We need to make it readable for our non-root 'user'
RUN chmod 755 /root && \
    if [ -d "/root/TTS" ]; then chmod -R 755 /root/TTS; fi

# Copy the rest of the application code
COPY . .

# Fix permissions for app code
RUN chown -R user:user /app

# Switch to non-root user
USER user
ENV HOME=/home/user
ENV PATH="/home/user/.local/bin:$PATH"
ENV COQUI_TOS_AGREED=1

# Pre-download models (XTTS, VCTK) to bake them into the image
# This speeds up startup time
RUN python3 -c "from TTS.api import TTS; \
    print('Downloading VCTK...'); TTS('tts_models/en/vctk/vits'); \
    print('Downloading XTTS...'); TTS('tts_models/multilingual/multi-dataset/xtts_v2');"

# Create voices directory
RUN mkdir -p server/voices

# Expose port 7860 (Hugging Face Spaces default)
ENV PORT=7860
EXPOSE 7860

# Run the unified FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
