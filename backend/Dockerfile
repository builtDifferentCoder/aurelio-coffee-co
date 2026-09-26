FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Install system utilities if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code and knowledge base markdown files
COPY app/ ./app/
COPY data/knowledge_base/ ./data/knowledge_base/

# Ensure data/chroma_db directory is created and writable for fresh rebuild on container start
RUN mkdir -p data/chroma_db && chmod -R 777 data/chroma_db

EXPOSE 8000

# Run ingestion to build Chroma DB fresh, then launch Uvicorn on dynamic $PORT
CMD ["sh", "-c", "python -m app.rag.ingest && uvicorn app.main:app --host 0.0.0.0 --port $PORT"]
