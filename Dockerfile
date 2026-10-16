# ========================================================
# Dockerfile for TitanPDF & HSE Report Studio on Google Cloud Run
# ========================================================

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860 \
    HOST=0.0.0.0

# Install essential system dependencies (fonts for Chinese and Vietnamese, image processing libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    fonts-dejavu \
    fonts-wqy-microhei \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY core/ /app/core/
COPY static/ /app/static/
COPY data/ /app/data/
COPY server.py /app/

# Expose port (Hugging Face Spaces standard port is 7860)
EXPOSE 7860

# Run TitanPDF FastAPI server
CMD ["python", "server.py"]
