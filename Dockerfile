FROM python:3.11-slim

# Install system dependencies (ffmpeg is essential for yt-dlp video processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency definition and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Set environment defaults
ENV PYTHONUNBUFFERED=1 \
    PORT=8080 \
    DB_PATH=/app/data/videobot.db

# Expose server port
EXPOSE 8080

# Run entry point
CMD ["python", "bot.py"]
