# Dockerfile — Minimal Flask/FFmpeg runtime; user data and credentials are never copied.
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=production
WORKDIR /app
# Install decoder tools and locked Python dependencies before copying source.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements-lock.txt /app/backend/requirements-lock.txt
RUN pip install --no-cache-dir -r /app/backend/requirements-lock.txt
COPY backend/app /app/backend/app
COPY backend/cloud_run.py /app/backend/cloud_run.py
COPY fixtures /app/fixtures
# Use an unprivileged process and Cloud Run's disposable filesystem.
RUN useradd --uid 10001 --create-home appuser
USER 10001
EXPOSE 8080
CMD ["python", "backend/cloud_run.py"]
