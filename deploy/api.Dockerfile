FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY deploy/requirements-api.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --no-compile -r /tmp/requirements.txt

COPY qsou_data /app/qsou_data
COPY config/sources.json /app/config/sources.json
COPY api-gateway /app/api-gateway

RUN mkdir -p /app/api-gateway/logs /var/lib/qsou

WORKDIR /app/api-gateway

EXPOSE 8000

CMD ["python", "-m", "qsou_data.start_api"]
