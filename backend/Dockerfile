# Use official lightweight Python runtime
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install curl for container health checking
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy backend application source
COPY backend/ /app/

# Copy dashboard static files
COPY dashboard/ /app/dashboard/

# Expose FastAPI default port
EXPOSE 8000

# Run uvicorn server binding to 0.0.0.0 for external LAN access
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
