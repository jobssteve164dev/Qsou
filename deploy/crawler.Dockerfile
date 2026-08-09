FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/crawler

WORKDIR /app

COPY deploy/requirements-crawler.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY qsou_data /app/qsou_data
COPY config /app/config
COPY crawler /app/crawler

RUN mkdir -p /app/crawler/logs /var/lib/qsou

WORKDIR /app/crawler

CMD ["python", "/app/crawler/run_schedule.py"]
