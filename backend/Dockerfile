# Use python:3.10-slim for a minimal footprint
FROM python:3.10-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies: ffmpeg is REQUIRED for yt-dlp to extract audio
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create and switch to the application directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Start the application using Uvicorn
# Render.com provides the $PORT environment variable automatically
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
