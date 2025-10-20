FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy shared modules first
COPY shared /app/shared

# Copy service requirements and install
COPY services/presentation/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY services/presentation/ .

# Expose port
EXPOSE 8005

# Run the service
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8005"]
