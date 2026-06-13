# roadTrip planner API — container image.
# Build from the repo root:  docker build -f backend/Dockerfile -t roadtrip-api .
# Run:                       docker run -p 8000:8000 roadtrip-api
FROM python:3.11-slim

# Don't buffer stdout/stderr; don't write .pyc files.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

WORKDIR /app

# Install dependencies first so the layer caches across code changes.
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# App code.
COPY backend ./backend

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen(f\"http://127.0.0.1:{os.environ.get('PORT','8000')}/health\").status==200 else 1)"

# Shell form so ${PORT} is expanded at runtime.
CMD uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT}
