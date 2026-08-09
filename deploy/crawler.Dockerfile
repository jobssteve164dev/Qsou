FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/crawler

WORKDIR /app

COPY deploy/requirements-crawler.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY qsou_data /app/qsou_data
COPY config/sources.json /app/config/sources.json
COPY crawler/scrapy.cfg crawler/run_schedule.py /app/crawler/
COPY crawler/qsou_crawler/__init__.py crawler/qsou_crawler/settings.py crawler/qsou_crawler/middlewares.py crawler/qsou_crawler/items.py /app/crawler/qsou_crawler/
COPY crawler/qsou_crawler/adapters /app/crawler/qsou_crawler/adapters
COPY crawler/qsou_crawler/spiders/__init__.py crawler/qsou_crawler/spiders/source_adapter_spider.py /app/crawler/qsou_crawler/spiders/
COPY crawler/qsou_crawler/pipelines/__init__.py crawler/qsou_crawler/pipelines/data_processing_pipeline.py /app/crawler/qsou_crawler/pipelines/

RUN mkdir -p /app/crawler/logs /var/lib/qsou

WORKDIR /app/crawler

CMD ["python", "/app/crawler/run_schedule.py"]
