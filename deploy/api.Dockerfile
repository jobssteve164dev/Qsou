FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY deploy/requirements-api.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --no-compile -r /tmp/requirements.txt

COPY qsou_data /app/qsou_data
COPY config/sources.json /app/config/sources.json
COPY alembic.ini /app/alembic.ini
COPY migrations /app/migrations
COPY scripts/migrate_file_objects_to_s3.py /app/scripts/migrate_file_objects_to_s3.py
COPY deploy/database-migrate /app/deploy/database-migrate
COPY api-gateway /app/api-gateway

RUN chmod 0755 /app/deploy/database-migrate \
    && mkdir -p /app/api-gateway/logs /var/lib/qsou

WORKDIR /app/api-gateway

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
