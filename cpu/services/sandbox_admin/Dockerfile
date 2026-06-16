FROM python:3.12-slim
WORKDIR /app

# Build context is workspace/services/ (set in docker-compose.override.yml)
# so we can reach both sandbox_admin/ and openclaw/ from here.
COPY sandbox_admin/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sandbox_admin/app.py .

# Bake the sandbox policy so production containers don't need a bind mount.
# In dev, docker-compose.override.yml mounts openclaw/ live over /policy/
# allowing policy edits without an image rebuild.
COPY openclaw/sandbox-policy.yaml /policy/sandbox-policy.yaml

EXPOSE 8099
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8099"]
