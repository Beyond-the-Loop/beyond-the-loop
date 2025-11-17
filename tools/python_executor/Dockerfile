# Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . /app

# Expose port for FastAPI
EXPOSE 8000

# Run FastAPI (module is main.py)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]