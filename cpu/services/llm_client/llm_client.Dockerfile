# --- services/llm-client/Dockerfile ---
FROM python:3.11-slim

WORKDIR /app

# Install dependencies. Protobuf stays on its compatibility line; BDSA-2025-123809
# is reachability-guarded and time-boxed in the vulnerability waiver registry.
RUN pip install --no-cache-dir \
    "fastapi>=0.138.1" \
    "starlette>=1.3.1" \
    uvicorn[standard] \
    httpx \
    pydantic \
    "protobuf>=5.29.6,<6" \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-exporter-otlp-proto-grpc

# Copy application
COPY llm_client.py observability.py bedrock_stream.py ./

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9000/health', timeout=5).read()"

ENTRYPOINT ["python", "llm_client.py"]
