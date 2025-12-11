# Stage 1: Build React Frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

COPY app/package.json app/package-lock.json ./
RUN npm ci

COPY app/ ./
# Build the app to /app/frontend/dist
RUN npm run build


# Stage 2: Python Backend
# Use PyTorch base image to avoid installing torch from scratch (fixes OOM 137 error)
FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime

# Set working directory
WORKDIR /app

# Install system dependencies
# DEBIAN_FRONTEND=noninteractive prevents interactive prompts during build
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    espeak-ng \
    libsndfile1 \
    ffmpeg \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user (Hugging Face Spaces runs as user 1000)
RUN useradd -m -u 1000 user

# Set environment variables
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    MPLCONFIGDIR=/tmp/matplotlib \
    TORCH_HOME=/tmp/torch \
    HF_HOME=/tmp/huggingface \
    COQUI_TOS_AGREED=1 \
    PYTHONUNBUFFERED=1

# Install Python dependencies
COPY requirements.txt .
# We upgrade pip first, then install requirements.
# PyTorch is already in the base image, so pip should skip it or use the cached version.

# Set build variables to minimize memory usage
ENV MAX_JOBS=1
ENV OMP_NUM_THREADS=1

# Split installation to reduce peak memory usage
# 1. upgrade pip
# 2. install everything EXCEPT TTS from requirements.txt (using sed to filter it out temporarily)
# 3. install TTS separately (this is the heavy one)
RUN pip install --upgrade pip && \
    sed -i '/TTS/d' requirements.txt && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir "TTS==0.22.0"

# Copy source code
# We use COPY . . to avoid issues with missing directories
COPY . .

# Copy built frontend from Stage 1 to 'static' folder
COPY --from=frontend-builder /app/frontend/dist static/

# Fix permissions
RUN chown -R user:user /app

# Switch to non-root user
USER user

# Create cache directory
RUN mkdir -p /app/tts_cache

# Pre-download models to cache
RUN python3 -c "from TTS.api import TTS; \
    print('Downloading VCTK...'); TTS('tts_models/en/vctk/vits'); \
    print('Downloading XTTS...'); TTS('tts_models/multilingual/multi-dataset/xtts_v2');"

# Run the application
# Use specific port 7860 which is standard for Hugging Face Spaces
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
