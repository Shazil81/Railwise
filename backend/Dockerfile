FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt requirements-production.txt ./
RUN pip install --no-cache-dir -r requirements-production.txt \
    && groupadd --system railwise \
    && useradd --system --gid railwise --uid 10001 railwise \
    && mkdir /app/state && chown railwise:railwise /app/state
COPY manage.py ./
COPY railway_core ./railway_core
COPY bookings ./bookings
USER railwise
CMD ["celery", "-A", "railway_core", "worker", "--loglevel=INFO", "--concurrency=1", "-Q", "celery,railwise_notifications"]
