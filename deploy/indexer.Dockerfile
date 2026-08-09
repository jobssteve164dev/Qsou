FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY deploy/requirements-indexer.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --no-compile -r /tmp/requirements.txt

COPY qsou_data /app/qsou_data
COPY config/sources.json /app/config/sources.json

RUN mkdir -p /var/lib/qsou

CMD ["python", "-m", "qsou_data.indexer"]
