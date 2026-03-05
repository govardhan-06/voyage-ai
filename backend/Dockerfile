# Voyage AI Backend
# Python 3.12 slim image for smaller size
FROM python:3.12-slim

# Prevent Python from writing pyc and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system deps only if needed (e.g. for bcrypt/cryptography)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency file first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Remove build deps to keep image smaller (optional)
RUN apt-get purge -y gcc libffi-dev 2>/dev/null || true \
    && apt-get autoremove -y 2>/dev/null || true

# Copy application code
COPY . .

# Expose the port uvicorn listens on
EXPOSE 8000

# Run as non-root user when possible (optional; uncomment if your app doesn't need root)
# RUN adduser --disabled-password --gecos '' appuser && chown -R appuser:appuser /app
# USER appuser

# Start the FastAPI app with uvicorn
# Use 0.0.0.0 so the server is reachable from outside the container
CMD ["uvicorn", "application:app", "--host", "0.0.0.0", "--port", "8000"]
