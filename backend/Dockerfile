# RepurposeAI API
#
# Build from the REPOSITORY ROOT, not from backend/ -- the image needs both the
# service and the pipeline package it imports:
#
#     docker build -f backend/Dockerfile -t repurposeai-api .
#     docker run --rm -p 8000:8000 repurposeai-api
#
# Then: http://localhost:8000/docs
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first, so edits to the source don't invalidate the install layer.
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# The verified pipeline, then the service that wraps it.
COPY repurposeai/ repurposeai/
COPY backend/ backend/

WORKDIR /app/backend
EXPOSE 8000

# curl is not in the slim image; use the interpreter that is already here.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "repurpose_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
