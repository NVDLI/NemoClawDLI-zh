# --- services/llm-client/Dockerfile ---
FROM python:3.11-slim

WORKDIR /app

# Install dependencies. Protobuf stays on the compatibility line used by generated
# binary OTLP/gRPC messages; JSON conversion is outside this service's runtime scope.
RUN pip install --no-cache-dir \
    "fastapi==0.138.2" \
    "starlette==1.3.1" \
    "uvicorn[standard]==0.49.0" \
    "httpx==0.28.1" \
    "pydantic==2.13.4" \
    "protobuf==5.29.6" \
    "opentelemetry-api==1.34.1" \
    "opentelemetry-sdk==1.34.1" \
    "opentelemetry-exporter-otlp-proto-grpc==1.34.1"

# Copy application
COPY llm_client.py observability.py bedrock_stream.py ./

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9000/health', timeout=5).read()"

ENTRYPOINT ["python", "llm_client.py"]
