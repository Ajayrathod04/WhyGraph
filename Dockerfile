# Production Dockerfile for WhyGraph / RECALL
FROM python:3.11-slim

WORKDIR /app

# Install dependencies (only falkordb client)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code, synthetic seeds, and web assets
COPY whygraph/ ./whygraph/
COPY seed/ ./seed/
COPY web/ ./web/

# Cloud platforms like Render, Railway, Fly inject PORT
ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

# Start WhyGraph stdlib server
CMD ["python", "-m", "whygraph"]
