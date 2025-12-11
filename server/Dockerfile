# Use a lightweight Python base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for TTS and audio processing
RUN apt-get update && apt-get install -y \
    espeak-ng \
    libsndfile1 \
    ffmpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user (Hugging Face Spaces runs as user 1000)
RUN useradd -m -u 1000 user

# Set environment variables for cache to be writable
ENV MPLCONFIGDIR=/tmp/matplotlib
ENV TORCH_HOME=/tmp/torch
ENV HF_HOME=/tmp/huggingface

# Copy requirements first
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY --chown=user:user . .

# Ensure permissions for voices directory
RUN mkdir -p voices && chown -R user:user voices

# Switch to non-root user
USER user

# Expose the port (Hugging Face Spaces expects 7860)
EXPOSE 7860

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
