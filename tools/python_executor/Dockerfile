# Dockerfile
FROM python:3.11-slim

# Install dependencies
RUN pip install --no-cache-dir fastapi uvicorn google-cloud-storage

# Copy app code
WORKDIR /app
COPY . /app

# Expose port for FastAPI
EXPOSE 8000

# Run FastAPI (module is main.py)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]